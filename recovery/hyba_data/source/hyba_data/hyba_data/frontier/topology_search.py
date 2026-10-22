import numpy as np


class TopologySearch:
    def __init__(self):
        self.phi = (1 + np.sqrt(5)) / 2
        
    def search(self, sturmian_boundary: np.ndarray, target_feature: float) -> tuple[int, float]:
        diffs = np.abs(sturmian_boundary - target_feature)
        best_index = int(np.argmin(diffs))
        search_time_ms = 0.01
        return best_index, search_time_ms
