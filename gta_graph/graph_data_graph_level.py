import numpy as np
from numpy.linalg import matrix_power
from typing import List
from gta_graph.aggregator_graph_level import Aggregator
from scipy import sparse


class GraphData:
    def __init__(self, adj_mat: np.array, features: np.array, label: float):
        n1, n2 = np.shape(adj_mat)
        if n1 != n2:
            raise ValueError("graph must be a square matrix")
        t1, t2 = np.shape(features)
        if n1 != t1:
            raise ValueError("the number of rows of features does not match the number of nodes in the graph")

        self.adj_mat = adj_mat
        self.features = features
        self.label = label
        self.adj_powers = np.NAN

    def compute_walks(self, max_walk_len):
        walks = []
        for walk_len in range(max_walk_len + 1):
            walks.append(np.linalg.matrix_power(self.adj_mat, walk_len))
        self.adj_powers = np.array(walks)

    def propagate_with_attention(self, walk_len, attention_set, attention_type):
        n_nodes = len(self.features)
        not_in_attention = list(set(range(n_nodes)) - set(attention_set))
        if attention_type == 1:  # zero-out columns
            # adj_copy = np.copy(self.adj_mat)
            # ad = np.linalg.matrix_power(adj_copy, graph_depth)
            masked_ad = self.adj_powers[walk_len].copy()
            for i in not_in_attention:
                masked_ad[:, i] = 0
            return np.matmul(masked_ad, self.features)[attention_set, :]
        elif attention_type == 2:  # zero-out rows
            # features_copy = np.copy(self.features)
            # if len(not_in_attention) > 0:
            #     # np.put(features_copy, not_in_attention, 0,axis=1)
            #     features_copy[not_in_attention, :] = 0
            #     # propagated_features = np.matmul(np.fill_diagonal(np.linalg.matrix_power(self.adj_mat, graph_depth), 0), self.features)
            propagated_features = np.matmul(np.linalg.matrix_power(self.adj_mat, walk_len), self.features)
            return propagated_features[attention_set, :]
        elif attention_type == 3:
            # adj_copy = np.copy(self.adj_mat)
            # ad = np.linalg.matrix_power(adj_copy, graph_depth)
            masked_ad = self.adj_powers[walk_len].copy()
            for i in not_in_attention:
                masked_ad[:, i] = 0
                masked_ad[i, :] = 0
            return np.matmul(masked_ad, self.features)[attention_set, :]
        elif attention_type == 4:
            # adj_copy = np.copy(self.adj_mat)
            # ad = np.linalg.matrix_power(adj_copy, graph_depth)
            ad = self.adj_powers[walk_len]
            diag = ad.diagonal()
            masked_ad = np.zeros_like(ad)
            np.fill_diagonal(masked_ad, diag)
            return np.matmul(masked_ad, self.features)[attention_set, :]
        elif attention_type == 5:
            # adj_copy = np.copy(self.adj_mat)
            # ad = np.linalg.matrix_power(adj_copy, graph_depth)
            ad = self.adj_powers[walk_len]
            diag = ad.diagonal().copy()
            diag[not_in_attention] = 0
            masked_ad = np.zeros_like(ad)
            np.fill_diagonal(masked_ad, diag)
            return np.matmul(masked_ad, self.features)[attention_set, :]
        else:
            print('Invalid attention type ' + str(attention_type) + '. Valid attentions for graph-level tasks are 1-5')
            return None

    # def propagate(self, depth : int) -> np.array:
    #     return (np.matmul(np.linalg.matrix_power(self.adj_mat, depth), self.features))

    def get_latent_feature_vector(self, walk_lens: List[int],
                                  available_attentions: List[np.array],
                                  aggregators: List[Aggregator],
                                  attention_types: List[int] = [1, 2, 3, 4, 5]) -> np.array:
        latent_feature_vector = []
        # attention_types = [1, 2, 3, 4, 5]
        for walk_len in walk_lens:
            for attention in available_attentions:
                for attention_type in attention_types:
                    # if attention == []:
                    # print("!!!")
                    # p = self.propagate(depth)[attention, :]
                    # pa = self.propagate_with_attention(depth, attention)
                    pa = self.propagate_with_attention(walk_len, attention, attention_type)
                    # if ((p==pa) == False):
                    #     print(p==pa)
                    # pa = p[attention, :]
                    for agg in aggregators:
                        for cola in pa.T:
                            if attention == []:
                                latent_feature_vector.append(agg.get_score(np.empty(0)))
                            else:
                                latent_feature_vector.append(agg.get_score(cola))
        return np.array(latent_feature_vector)

    @staticmethod
    def get_index(latent_feature_index: int,
                  sizes: List[int]) -> List[int]:
        """
        Translate the chosen index of the latent feature vector for each example to the chosen walk len, attention_depth, feature and aggregator
        :param latent_feature_index: the chosen "latent feature" index
        :param sizes: #walks_lens, #available_attetnions, # attention_types, #aggregators, #features
        :return: a list with the sizes in the following order:  walk_len, attention index in available attentions, attention_type_index, aggregator index, feature index
        """

        indices = []
        for n in range(0, len(sizes)):
            s = sizes[len(sizes) - 1 - n]
            i = latent_feature_index % s  # location in block
            latent_feature_index = int((latent_feature_index - i) / s)  # block index ( in one higher level)
            indices.insert(0, i)
        return indices

    def get_number_of_nodes(self):
        return np.shape(self.adj_mat)[0]

    def get_number_of_features(self):
        return np.shape(self.features)[1]

    def latent_feature_to_feature_components(self, index_in_latent_feature_vector: int,
                                             walk_lens: List[int],
                                             available_attentions: List[np.array],
                                             aggregators: List[Aggregator],
                                             thresh: float = 0,
                                             attention_types: List[int] = [1, 2, 3, 4, 5]) -> np.generic:
        sizes = [len(walk_lens), len(available_attentions), len(attention_types), len(aggregators),
                 self.features.shape[1]]
        walk_len_index, attention_index, attention_type_index, aggregator_index, feature_index = self.get_index(
            latent_feature_index=index_in_latent_feature_vector, sizes=sizes)
        walk_len = walk_lens[walk_len_index]
        attention_set = available_attentions[attention_index]
        attention_type = attention_types[attention_type_index]
        agg = aggregators[aggregator_index]

        # p = self.propagate(depth)[attention, :] #gives different results than propagate_with_attention if attention=[]
        # pa = self.propagate_with_attention(depth, attention)
        pa = self.propagate_with_attention(walk_len, attention_set, attention_type)
        # pa = p[attention, :]
        # col = p[:, col_index]
        cola = pa[:, feature_index]
        if attention_set == []:  # then the score returned should be -1000!
            cola = np.empty(0)
        return agg.get_score(cola), agg.get_generated_attentions(cola, thresh), attention_set

    # def get_attentions(self, index_in_feature_vector : int,
    #                     threshold: np.generic,
    #                     depths: List[int],
    #                     attentions: List[np.array],
    #                     aggregators: List[split_criteria]) -> List[List[int]]:
    #
    #     depth_index, attention_index, aggregator_index, col_index = \
    #         self.get_index(index_in_feature_vector, [len(depths), len(attentions), len(aggregators), self.features.shape[1]])
    #     depth = depths[depth_index]
    #     attention = attentions[attention_index]
    #     agg = aggregators[aggregator_index]
    #     p = self.propagate(depth)[attention, :]
    #     # p = self.propagate_with_attention(attention, depth)
    #     # pa = p[attention, :]
    #     col = p[:, col_index]
    #     local_attention = agg.get_attention(col, threshold)
    #     return([[attention[i] for i in local] for local in local_attention])

    def get_label(self):
        return self.label


class SparseGraphData(GraphData):
    def __init__(self, adj_mat: np.array, features: np.array, label: np.generic = np.NAN):
        super().__init__(adj_mat, features, label)
        self.sparse_adj = sparse.csr_matrix(adj_mat)
        self.sparse_features = sparse.csr_matrix(features)
        self.sparse_adj_powers = np.NAN

    def compute_walks(self, max_walk_len):
        walks = []
        for walk_len in range(max_walk_len + 1):
            powered = self.sparse_adj ** walk_len
            if not (type(powered) == sparse.csr_matrix):
                powered = powered.tocsr()
            walks.append(powered)
        self.sparse_adj_powers = np.array(walks)

    def propagate_with_attention(self, graph_depth, attention_set, attention_type=2):
        n_nodes = self.get_number_of_nodes()
        not_in_attention = np.array(list(set(range(n_nodes)) - set(attention_set)))
        if attention_type == 1:
            masked_sparse_power = self.sparse_adj_powers[graph_depth].tolil()
            for i in not_in_attention:
                masked_sparse_power[:, i] = 0  # maybe can be optimized
            propagated_features = masked_sparse_power * self.sparse_features
            return propagated_features.toarray()
        elif attention_type == 5:
            masked_sparse_power = self.sparse_adj_powers[graph_depth].tolil()
            # TODO: mask diagonal
            propagated_features = masked_sparse_power * self.sparse_features
            return propagated_features.toarray()

        else:
            print('Invalid attention type ' + str(attention_type) + '. Valid attentions for graph-level tasks are 1-5')
            return None
