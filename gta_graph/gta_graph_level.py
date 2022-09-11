from gta_graph.tree_node_learner_graph_level import TreeNodeLearner, TreeNodeLearnerParams
from gta_graph.aggregator_graph_level import Aggregator, graph_level_aggregators
from gta_graph.graph_data_graph_level import GraphData
from typing import List
import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin
from collections import defaultdict
from scipy.stats import rankdata


################################################################
###                                                          ###
### Note that line 124 of boosting.py in starboost should    ###
### be changed to:                                           ###
###   y_pred[:, i] += self.learning_rate * direction[:, i]   ###
###                                                          ###
### The same fix should be applied in line 179               ###
### /usr/local/lib/python3.8/dist-packages/starboost/        ###
###                                                          ###
################################################################

class GTAGraph(BaseEstimator, RegressorMixin):
    def __init__(self,
                 walk_lens: List[int] = [0, 1, 2],
                 max_attention_depth: int = 2,
                 aggregators: List[Aggregator] = graph_level_aggregators,
                 max_number_of_leafs: int = 10,
                 min_gain: float = 0.0,
                 min_leaf_size: int = 10,
                 attention_types: List[int] = [1, 2, 3, 4, 5],
                 ):
        self.walk_lens = walk_lens
        self.max_attention_depth = max_attention_depth
        self.aggregators = aggregators
        self.max_number_of_leafs = max_number_of_leafs
        self.min_gain = min_gain
        self.min_leaf_size = min_leaf_size
        self.attention_types = attention_types
        self.trained_tree_ = None
        self.train_L2 = None
        self.train_total_gain = None
        self.tree_learner_ = None

    def get_params(self, deep=True):
        """
        Get parameters for this estimator.
        Parameters
        ----------
        deep : bool, default=True
            If True, will return the parameters for this estimator and
            contained sub-objects that are estimators.
        Returns
        -------
        params : dict
            Parameter names mapped to their values.
        """
        out = dict()
        for key in self._get_param_names():
            value = getattr(self, key)
            if deep and hasattr(value, "get_params"):
                deep_items = value.get_params().items()
                out.update((key + "__" + k, val) for k, val in deep_items)
            out[key] = value
        return out

    def set_params(self, **params):
        """
        Set the parameters of this estimator.
        The method works on simple estimators as well as on nested objects
        (such as :class:`~sklearn.pipeline.Pipeline`). The latter have
        parameters of the form ``<component>__<parameter>`` so that it's
        possible to update each component of a nested object.
        Parameters
        ----------
        **params : dict
            Estimator parameters.
        Returns
        -------
        self : estimator instance
            Estimator instance.
        """
        if not params:
            return self
        valid_params = self.get_params(deep=True)

        nested_params = defaultdict(dict)
        for key, value in params.items():
            key, delim, sub_key = key.partition("__")
            if key not in valid_params:
                raise ValueError(
                    "Invalid parameter %s for estimator %s. "
                    "Check the list of available parameters "
                    "with `estimator.get_params().keys()`." % (key, self)
                )

            if delim:
                nested_params[key][sub_key] = value
            else:
                setattr(self, key, value)
                valid_params[key] = value

        for key, sub_params in nested_params.items():
            valid_params[key].set_params(**sub_params)

        return self

    def fit(self, X: List[GraphData], y: np.array):
        if isinstance(X, np.ndarray):
            X = X[0, :].tolist()

        if len(X) != len(y):
            raise ValueError("Size of X and y mismatch")
        params = TreeNodeLearnerParams(
            walk_lens=self.walk_lens,
            max_attention_depth=self.max_attention_depth,
            aggregators=self.aggregators,
            max_number_of_leafs=self.max_number_of_leafs,
            min_gain=self.min_gain,
            min_leaf_size=self.min_leaf_size,
            attention_types=self.attention_types,
        )
        self.tree_learner_ = TreeNodeLearner(params, list(range(0, len(X))), None)
        self.train_L2, self.train_total_gain = self.tree_learner_.fit(X, y)
        self.trained_tree_ = self.tree_learner_.build_trained_tree_and_get_root()
        return self

    def predict(self, X: List[GraphData]):
        if isinstance(X, np.ndarray):
            X = X[0, :].tolist()
        predictions = [self.trained_tree_.predict(x)[0] for x in X]
        array = np.array(predictions)
        if array.ndim == 1:
            array = array.reshape(-1, 1)
        array.reshape(-1, 1)
        return array

    def nodes_scores(self, g: GraphData):

        num_of_nodes = g.get_number_of_nodes()
        pred = self.trained_tree_.predict(g)
        pred_val = pred[0]
        histogram = pred[1]
        rank_ties = rankdata(histogram) * 10
        nodes_scores = np.zeros(num_of_nodes)
        for i in range(num_of_nodes):
            nodes_scores[i] = (2.0 ** -(rank_ties[i])) * np.abs(pred_val)
        return np.array(nodes_scores)

    def print(self):
        self.trained_tree_.print_tree()
