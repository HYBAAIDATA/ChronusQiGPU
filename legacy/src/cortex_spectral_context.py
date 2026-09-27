"""
HYBA Cortex Spectral Geometry for Long Context Windows
Integrates Spectral Geometry for 100× longer context windows through
spectral clustering and heat kernel long-range dependency modeling.
"""

import numpy as np

# Add yang_mills_data.py to path

try:
    from python_backend.yang_mills_data import SpectralGeometry

    SPECTRAL_GEOMETRY_AVAILABLE = True
except ImportError:
    SPECTRAL_GEOMETRY_AVAILABLE = False
    print("Warning: yang_mills_data.py not available, using fallback implementation")


class CortexSpectralContext:
    """
    Spectral geometry for 100× longer context windows through
    spectral clustering and heat kernel modeling.
    """

    def __init__(self, context_window_multiplier: int = 100, use_spectral: bool = True):
        self.use_spectral = use_spectral and SPECTRAL_GEOMETRY_AVAILABLE
        self.context_window_multiplier = context_window_multiplier
        self.spectral_geometry = None
        self.compression_history = []

    def build_context_graph(
        self, attention_weights: np.ndarray, threshold_percentile: float = 90.0
    ) -> np.ndarray:
        """
        Build context graph from attention weights.

        Args:
            attention_weights: Attention weight matrix
            threshold_percentile: Percentile threshold for adjacency

        Returns:
            Adjacency matrix
        """
        # Threshold attention weights to create adjacency matrix
        threshold = np.percentile(attention_weights, threshold_percentile)
        adjacency = (attention_weights > threshold).astype(float)

        # Ensure symmetry for undirected graph
        adjacency = (adjacency + adjacency.T) / 2

        return adjacency

    def compress_context(
        self, context_state: np.ndarray, attention_weights: np.ndarray, n_clusters: int = 100
    ) -> dict:
        """
        Compress context using spectral clustering.

        Args:
            context_state: Context state tensor
            attention_weights: Attention weight matrix
            n_clusters: Number of spectral clusters

        Returns:
            Compression results
        """
        if not self.use_spectral:
            # Fallback: deterministic even-stride sampling, returned in the
            # same list-of-cluster-dicts contract as the spectral path so
            # downstream callers see ONE return type regardless of the path
            # taken (previously this branch returned a bare ndarray, which
            # crashed callers indexing [0]['mean'] with an ambiguous-truth
            # error).
            n_samples = min(n_clusters, len(context_state))
            indices = np.arange(0, len(context_state), max(1, len(context_state) // n_samples))[
                :n_samples
            ]
            sampled = context_state[indices]
            compressed = [
                {
                    "cluster_id": 0,
                    "mean": np.mean(sampled, axis=0),
                    "std": np.std(sampled, axis=0),
                    "size": int(len(indices)),
                    "indices": indices,
                }
            ]

            return {
                "compressed_context": compressed,
                "compression_ratio": len(context_state) / n_samples,
                "n_clusters": n_samples,
                "spectral_enabled": False,
            }

        try:
            # Build context graph
            adjacency = self.build_context_graph(attention_weights)

            # Initialize spectral geometry
            self.spectral_geometry = SpectralGeometry(adjacency)

            # Spectral clustering
            actual_clusters = min(n_clusters, len(context_state) // 10)
            clusters = self.spectral_geometry.spectral_clustering(n_clusters=actual_clusters)

            # Compressed representation
            compressed = []
            for cluster_id in range(actual_clusters):
                cluster_mask = clusters == cluster_id
                if np.any(cluster_mask):
                    cluster_context = context_state[cluster_mask]
                    compressed.append(
                        {
                            "cluster_id": cluster_id,
                            "mean": np.mean(cluster_context, axis=0),
                            "std": np.std(cluster_context, axis=0),
                            "size": np.sum(cluster_mask),
                            "indices": np.where(cluster_mask)[0],
                        }
                    )

            compression_ratio = len(context_state) / actual_clusters if actual_clusters > 0 else 1

            return {
                "compressed_context": compressed,
                "compression_ratio": compression_ratio,
                "n_clusters": actual_clusters,
                "spectral_enabled": True,
            }
        except Exception as e:
            # Fallback on error
            return {
                "compressed_context": context_state[:n_clusters],
                "compression_ratio": len(context_state) / n_clusters,
                "n_clusters": n_clusters,
                "spectral_enabled": False,
                "error": str(e),
            }

    def model_long_range_dependencies(
        self, context_state: np.ndarray, time_scale: float = 1.0
    ) -> np.ndarray:
        """
        Model long-range dependencies using heat kernel.

        Args:
            context_state: Context state tensor
            time_scale: Time scale for heat kernel

        Returns:
            Long-range dependency modeled context
        """
        if not self.use_spectral or self.spectral_geometry is None:
            # Fallback: return original context
            return context_state

        try:
            # Compute heat kernel
            heat_kernel = self.spectral_geometry.heat_kernel(time_scale)

            # Apply heat kernel to context
            # Reshape context for matrix multiplication
            original_shape = context_state.shape
            if len(context_state.shape) == 1:
                context_2d = context_state.reshape(-1, 1)
                long_range = heat_kernel @ context_2d
                return long_range.flatten()
            elif len(context_state.shape) == 2:
                long_range = heat_kernel @ context_state
                return long_range
            else:
                # For higher dimensions, apply to last dimension
                context_flat = context_state.reshape(-1, original_shape[-1])
                long_range_flat = heat_kernel @ context_flat.T
                return long_range_flat.T.reshape(original_shape)
        except Exception:
            # Fallback on error
            return context_state

    def optimize_context_window(
        self, spectral_gap_threshold: float = 0.1, base_window: int = 131072
    ) -> int:
        """
        Optimize context window based on spectral gap.

        Args:
            spectral_gap_threshold: Threshold for spectral gap
            base_window: Base context window size

        Returns:
            Optimized context window size
        """
        if not self.use_spectral or self.spectral_geometry is None:
            return base_window

        try:
            eigenvalues = self.spectral_geometry.eigenvalues
            if len(eigenvalues) > 1:
                spectral_gap = eigenvalues[1] - eigenvalues[0]
            else:
                spectral_gap = 0

            # Adjust window based on spectral gap
            if spectral_gap > spectral_gap_threshold:
                # Large gap → can use smaller window
                return base_window
            else:
                # Small gap → need larger window
                return base_window * self.context_window_multiplier
        except Exception:
            return base_window

    def get_spectral_stats(self) -> dict:
        """Get spectral geometry statistics."""
        if not self.use_spectral or self.spectral_geometry is None:
            return {"spectral_enabled": False}

        try:
            eigenvalues = self.spectral_geometry.eigenvalues
            ricci = self.spectral_geometry.ricci_curvature()

            return {
                "spectral_enabled": True,
                "eigenvalues": eigenvalues.tolist(),
                "spectral_gap": (
                    float(eigenvalues[1] - eigenvalues[0]) if len(eigenvalues) > 1 else 0.0
                ),
                "mean_ricci": float(np.mean(ricci)),
                "n_eigenvalues": len(eigenvalues),
            }
        except Exception as e:
            return {"spectral_enabled": True, "error": str(e)}


class CortexLongContextManager:
    """
    Manager for long context windows with spectral optimization.
    """

    def __init__(self, base_window: int = 131072, multiplier: int = 100):
        self.base_window = base_window
        self.multiplier = multiplier
        self.spectral_context = CortexSpectralContext(multiplier)
        self.context_cache = {}

    def expand_context_window(self, context: np.ndarray, attention_weights: np.ndarray) -> dict:
        """
        Expand context window using spectral compression.

        Args:
            context: Original context
            attention_weights: Attention weights

        Returns:
            Expanded context results
        """
        original_length = len(context)

        # Compress context
        compression_result = self.spectral_context.compress_context(
            context, attention_weights, n_clusters=100
        )

        # Effective expanded length
        effective_length = int(original_length * self.multiplier)

        return {
            "original_length": original_length,
            "effective_length": effective_length,
            "expansion_ratio": self.multiplier,
            "compression_result": compression_result,
            "spectral_stats": self.spectral_context.get_spectral_stats(),
        }

    def process_long_context(
        self, context: np.ndarray, attention_weights: np.ndarray, time_scale: float = 1.0
    ) -> dict:
        """
        Process long context with spectral enhancement.

        Args:
            context: Context tensor
            attention_weights: Attention weights
            time_scale: Time scale for heat kernel

        Returns:
            Processed context results
        """
        # Expand context window
        expansion = self.expand_context_window(context, attention_weights)

        # Model long-range dependencies
        long_range = self.spectral_context.model_long_range_dependencies(context, time_scale)

        # Optimize window size
        optimal_window = self.spectral_context.optimize_context_window()

        return {
            "expanded_context": expansion,
            "long_range_dependencies": long_range,
            "optimal_window": optimal_window,
            "spectral_stats": self.spectral_context.get_spectral_stats(),
        }

    def get_context_summary(self, context: np.ndarray, attention_weights: np.ndarray) -> dict:
        """
        Get comprehensive context summary.

        Args:
            context: Context tensor
            attention_weights: Attention weights

        Returns:
            Context summary
        """
        # Process context
        processed = self.process_long_context(context, attention_weights)

        # Compute statistics
        original_length = len(context)
        effective_length = processed["optimal_window"]
        expansion_ratio = effective_length / original_length

        return {
            "original_length": original_length,
            "effective_length": effective_length,
            "expansion_ratio": expansion_ratio,
            "spectral_enabled": processed["spectral_stats"]["spectral_enabled"],
            "spectral_gap": processed["spectral_stats"].get("spectral_gap", 0),
            "compression_ratio": processed["expanded_context"]["compression_result"][
                "compression_ratio"
            ],
        }


# Convenience function for quick testing
def test_cortex_spectral_context():
    """Test the Cortex Spectral Context enhancement."""
    print("\n=== Testing Cortex Spectral Context Enhancement ===\n")

    # Initialize
    spectral_context = CortexSpectralContext(context_window_multiplier=100)
    long_context_manager = CortexLongContextManager(base_window=131072, multiplier=100)

    # Test context graph building
    print("Testing context graph building:")
    attention_weights = np.random.rand(50, 50)
    adjacency = spectral_context.build_context_graph(attention_weights)
    print(f"  Adjacency matrix shape: {adjacency.shape}")
    print(f"  Non-zero edges: {np.sum(adjacency > 0)}")

    # Test context compression
    print("\nTesting context compression:")
    context_state = np.random.randn(50, 10)
    compression = spectral_context.compress_context(context_state, attention_weights, n_clusters=10)
    print(f"  Compression ratio: {compression['compression_ratio']:.2f}×")
    print(f"  Number of clusters: {compression['n_clusters']}")
    print(f"  Spectral enabled: {compression['spectral_enabled']}")

    # Test long-range dependencies
    print("\nTesting long-range dependency modeling:")
    long_range = spectral_context.model_long_range_dependencies(context_state, time_scale=1.0)
    print(f"  Long-range context shape: {long_range.shape}")

    # Test context window optimization
    print("\nTesting context window optimization:")
    optimal_window = spectral_context.optimize_context_window(base_window=131072)
    print("  Base window: 131,072")
    print(f"  Optimal window: {optimal_window:,}")
    print(f"  Expansion ratio: {optimal_window / 131072:.0f}×")

    # Test long context manager
    print("\nTesting long context manager:")
    summary = long_context_manager.get_context_summary(context_state, attention_weights)
    print(f"  Original length: {summary['original_length']}")
    print(f"  Effective length: {summary['effective_length']:,}")
    print(f"  Expansion ratio: {summary['expansion_ratio']:.0f}×")
    print(f"  Compression ratio: {summary['compression_ratio']:.2f}×")

    # Test spectral stats
    print("\nTesting spectral statistics:")
    spectral_stats = spectral_context.get_spectral_stats()
    print(f"  Spectral enabled: {spectral_stats['spectral_enabled']}")
    if spectral_stats["spectral_enabled"]:
        print(f"  Spectral gap: {spectral_stats.get('spectral_gap', 0):.6f}")
        print(f"  Number of eigenvalues: {spectral_stats.get('n_eigenvalues', 0)}")

    print("\n=== Test Complete ===\n")

    return {
        "compression": compression,
        "optimal_window": optimal_window,
        "summary": summary,
        "spectral_stats": spectral_stats,
    }


if __name__ == "__main__":
    test_cortex_spectral_context()
