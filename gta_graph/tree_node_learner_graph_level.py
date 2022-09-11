import numpy as np
from typing import List, NamedTuple
from gta_graph.tree_node_graph_level import TrainedTreeNode
from gta_graph.aggregator_graph_level import Aggregator, graph_level_aggregators
from gta_graph.graph_data_graph_level import GraphData
from sklearn.tree import DecisionTreeRegressor


class TreeNodeLearnerParams(NamedTuple):
    walk_lens: List[int] = [0, 1, 2],
    max_attention_depth: int = 2,
    aggregators: List[Aggregator] = graph_level_aggregators,
    max_number_of_leafs: int = 10,
    min_leaf_size: int = 10,
    min_gain: float = 0.0,
    attention_types: List[int] = [1, 2, 3, 4, 5],


class TreeNodeLearner:
    def __init__(self,
                 params: TreeNodeLearnerParams,
                 active: List[int],
                 parent: "TreeNodeLearner" = None):

        self.params = params
        self.active = active
        self.parent = parent

        self.available_attentions = None
        self.potential_gain = None
        self.lte = None
        self.gt = None
        self.walk_len = None
        self.attention_depth = None
        self.attention_position = None
        self.active_attention_index = None
        self.attention_type = None
        self.aggregator = None
        self.feature_index = None
        self.value_as_leaf = None
        self.features_dimension = None
        self.trained_tree_node = None
        self.generated_attentions = None

        self.active_lte_ = None
        self.active_gt_ = None
        self.latent_feature_index_ = None
        self.thresh_ = None
        self.lte_value_ = None
        self.gt_value_ = None

    def get_available_attentions_indices(self):
        """
        This function translate the available attention sets to their indices in the following order:
        (-1,-1) is the set of all vertices
        (i,j) is the attention generated at the node of distance i from the current node,
         where j is 0 for the left (leq) attention generated and 1 for the right attention generated
        :return: the set of indices of the available attention sets.
        """

        attention_indices = [(-1, -1)]
        p = self
        for i in range(0, self.params.max_attention_depth):
            if p.parent is None:
                break
            p = p.parent
            att = [(i, j) for j in range(0, len(p.generated_attentions[0]))]
            attention_indices += att
        return attention_indices

    def set_available_attentions_for_graph(self, graph: "GraphData", graph_index: int):
        p = self
        available_attentions = []
        for _ in range(0, self.params.max_attention_depth):
            if p.parent is None:
                break
            p = p.parent
            available_attentions = p.generated_attentions[graph_index] + available_attentions
        available_attentions = [list(range(0, graph.get_number_of_nodes()))] + available_attentions
        self.available_attentions[graph_index] = available_attentions

    def find_best_split(self, X: List[GraphData], y: np.array):
        labels = y[self.active]
        self.value_as_leaf = np.mean(labels)
        self.features_dimension = X[0].get_number_of_features()
        if len(self.active) < self.params.min_leaf_size:
            self.potential_gain = 0.0
            return 0.0
        self.available_attentions = [[] for _ in range(0, len(X))]
        latent_feature_vectors = []
        for graph_index in self.active:
            graph = X[graph_index]
            self.set_available_attentions_for_graph(graph, graph_index)
            available_attentions = self.available_attentions[graph_index]
            latent_feature_vector = graph.get_latent_feature_vector(walk_lens=self.params.walk_lens,
                                                                    available_attentions=available_attentions,
                                                                    aggregators=self.params.aggregators,
                                                                    attention_types=self.params.attention_types)
            latent_feature_vectors.append(latent_feature_vector)
        data = np.array(latent_feature_vectors)
        stump = DecisionTreeRegressor(max_depth=1)
        stump.fit(data, labels)
        if len(stump.tree_.value) < 3:
            return 0
        self.latent_feature_index_ = stump.tree_.feature[0]
        self.thresh_ = stump.tree_.threshold[0]
        self.lte_value_ = stump.tree_.value[1][0][0]
        self.gt_value_ = stump.tree_.value[2][0][0]
        feature_values = data[:, self.latent_feature_index_]
        active_lte_local = np.where(feature_values <= self.thresh_)[0].tolist()
        self.active_lte_ = [self.active[i] for i in active_lte_local]
        active_gt_local = np.where(feature_values > self.thresh_)[0].tolist()
        self.active_gt_ = [self.active[i] for i in active_gt_local]
        self.potential_gain = len(
            active_gt_local) * self.gt_value_ * self.gt_value_ + len(
            active_lte_local) * self.lte_value_ * self.lte_value_ - len(self.active) * \
                              stump.tree_.value[0][0][0] * \
                              stump.tree_.value[0][0][0]
        return self.potential_gain

    def apply_best_split(self, X: List[GraphData], y: np.array):
        lte_node = TreeNodeLearner(params=self.params,
                                   active=self.active_lte_,
                                   parent=self)
        lte_node.value_as_leaf = np.mean(y[self.active_lte_])

        gt_node = TreeNodeLearner(params=self.params,
                                  active=self.active_gt_,
                                  parent=self)
        gt_node.value_as_leaf = np.mean(y[self.active_gt_])

        self.gt = gt_node
        self.lte = lte_node

        # update split attributes
        available_attention_indices = self.get_available_attentions_indices()
        sizes = [len(self.params.walk_lens), len(available_attention_indices), len(self.params.attention_types),
                 len(self.params.aggregators), X[0].get_number_of_features()]
        walk_len_index, active_attention_index, attention_type_index, aggregator_index, feature_index = X[0].get_index(
            self.latent_feature_index_, sizes)
        self.active_attention_index = active_attention_index
        self.walk_len = self.params.walk_lens[walk_len_index]
        selected_attention_indices = available_attention_indices[active_attention_index]
        self.attention_depth = selected_attention_indices[0]
        self.attention_position = selected_attention_indices[1]
        self.attention_type = self.params.attention_types[attention_type_index]
        self.aggregator = self.params.aggregators[aggregator_index]
        self.feature_index = feature_index

        self.generated_attentions = [[] for _ in range(0, len(X))]
        for i in self.active:
            g = X[i]
            _, generated_attentions, _ = g.latent_feature_to_feature_components(
                index_in_latent_feature_vector=self.latent_feature_index_, walk_lens=self.params.walk_lens,
                available_attentions=self.available_attentions[i], aggregators=self.params.aggregators,
                thresh=self.thresh_,
                attention_types=self.params.attention_types)
            self.generated_attentions[i] = generated_attentions

    def fit(self, X: List[GraphData], y: np.array):
        tiny = np.finfo(float).tiny
        min_gain = self.params.min_gain
        if min_gain <= tiny:
            min_gain = tiny
        leafs = [self]
        total_gain = 0
        potential_gains = [self.find_best_split(X, y)]
        for _ in range(1, self.params.max_number_of_leafs):
            index_max = np.argmax(potential_gains)
            gain = potential_gains[index_max]
            if gain < min_gain:
                break
            leaf_to_split = leafs.pop(index_max)
            potential_gains.pop(index_max)
            leaf_to_split.apply_best_split(X, y)
            lte = leaf_to_split.lte
            gt = leaf_to_split.gt
            potential_gains += [lte.find_best_split(X, y), gt.find_best_split(X, y)]
            leafs += [lte, gt]
            total_gain += gain

        l2 = 0
        for leaf in leafs:
            labels = y[leaf.active]
            l2 += sum((leaf.value_as_leaf - labels) ** 2)
        return l2, total_gain

    def predict(self, g: GraphData):
        attentions_cache = [[list(range(0, g.get_number_of_nodes()))]]
        histogram = np.zeros(g.get_number_of_nodes())
        p = self
        while p.lte is not None:
            attentions = []
            for a in attentions_cache:
                attentions += a

            score, new_attentions, selected_attention = g.latent_feature_to_feature_components(
                index_in_latent_feature_vector=p.latent_feature_index_, walk_lens=p.params.walk_lens,
                available_attentions=attentions, aggregators=p.params.aggregators, thresh=p.thresh_,
                attention_types=p.params.attention_types)
            histogram[selected_attention] += 1
            if len(attentions_cache) > p.max_attention_depth:
                if len(attentions_cache) > 1:
                    attentions_cache.pop(1)
            attentions_cache.append(new_attentions)
            if score <= p.thresh_:
                p = p.lte
            else:
                p = p.gt
        return p.value_as_leaf, histogram

    def build_trained_tree_and_get_root(self):
        if self.gt is None:
            self.trained_tree_node = TrainedTreeNode(gt=None, lte=None, feature_index=-1, thresh=0,
                                                     value_as_leaf=self.value_as_leaf, walk_len=-1,
                                                     active_attention_index=-1,
                                                     max_attention_depth=self.params.max_attention_depth,
                                                     aggregator=None,
                                                     attention_type=self.attention_type)
        else:

            self.trained_tree_node = TrainedTreeNode(gt=None, lte=None, feature_index=self.feature_index,
                                                     thresh=self.thresh_, value_as_leaf=self.value_as_leaf,
                                                     walk_len=self.walk_len,
                                                     active_attention_index=self.active_attention_index,
                                                     max_attention_depth=self.params.max_attention_depth,
                                                     aggregator=self.aggregator,
                                                     attention_type=self.attention_type)

            self.trained_tree_node.lte = self.lte.build_trained_tree_and_get_root()
            self.trained_tree_node.gt = self.gt.build_trained_tree_and_get_root()

        return self.trained_tree_node

    def print_tree(self, indent=""):
        if self.gt is None:
            print(indent, "-->", self.value_as_leaf)
        else:
            print(indent, "f%d _thresh %3f depth %2d aggregator %5s" % (
                self.feature_index, self.thresh_, self.walk_len, self.aggregator.get_name()))
            self.lte.print_tree(indent + "  ")
            self.gt.print_tree(indent + "  ")
