from sklearn.base import BaseEstimator, RegressorMixin
import numpy as np
from gta_graph.gta_graph_level import GTAGraph
from gta_node.gta_node_level import GTANode
from typing import List


class GTA(BaseEstimator, RegressorMixin):
    def __init__(self,
                 classifier: bool = True,
                 max_attention: int = 1,
                 max_walk_len: int = 1,
                 min_leaf_size: int = 10,
                 random_state: np.generic = None,
                 max_number_of_leafs: int = 10,
                 min_gain: float = 0.0,
                 attention_types: List[int] = [1, 4],
                 is_graph_task: bool = True):

        self.classifier = classifier
        self.max_attention = max_attention
        self.max_walk_len = max_walk_len
        self.min_leaf_size = min_leaf_size
        self.random_state = random_state
        self.max_number_of_leafs = max_number_of_leafs
        self.min_gain = min_gain
        self.is_graph_task = is_graph_task

        walk_lens = list(range(0, max_walk_len + 1))
        if is_graph_task:
            self.model = GTAGraph(max_attention_depth=max_attention,
                                  walk_lens=walk_lens,
                                  min_leaf_size=min_leaf_size,
                                  max_number_of_leafs=max_number_of_leafs,
                                  attention_types=attention_types)

        else:
            self.model = GTANode(max_attention_depth=max_attention,
                                 walk_lens=walk_lens,
                                 min_leaf_size=min_leaf_size,
                                 max_number_of_leafs=max_number_of_leafs,
                                 attention_types=attention_types)

    def fit(self, X, y):
        return self.model.fit(X, y)

    def predict(self, X, y):
        return self.model.predict(X, y)

    def get_params(self, deep=True):
        """
        Get parameters for this estimator.
        Parameters
        ----------
        deep : bool, default=True
            If True, will return the parameters for this estimator and
            contained subobjects that are estimators.
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
            # Simple optimization to gain speed (inspect is slow)
            return self
        valid_params = self.get_params(deep=True)

        nested_params = defaultdict(dict)  # grouped by prefix
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
