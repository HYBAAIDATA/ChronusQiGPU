"""
HYBA Cortex Topological Context Awareness
Integrates Topological Analytics for semantic context understanding
with persistent homology and Betti number analysis.
"""

import numpy as np

# Add yang_mills_data.py to path

try:
    from python_backend.yang_mills_data import TopologicalAnalytics

    TOPOLOGICAL_ANALYTICS_AVAILABLE = True
except ImportError:
    TOPOLOGICAL_ANALYTICS_AVAILABLE = False
    print("Warning: yang_mills_data.py not available, using fallback implementation")


class CortexTopologicalContext:
    """
    Topological context awareness for semantic understanding using
    persistent homology and Betti number analysis.
    """

    def __init__(self, manifold_dimension: int = 5, use_topological: bool = True):
        self.use_topological = use_topological and TOPOLOGICAL_ANALYTICS_AVAILABLE
        self.manifold_dimension = manifold_dimension
        self.context_history = []

        # Initialize Topological Analytics if available
        if self.use_topological:
            self.topological_analytics = TopologicalAnalytics(manifold_dimension=manifold_dimension)
        else:
            self.topological_analytics = None

    def analyze_context_topology(self, context_state: np.ndarray, epsilon: float = 0.5) -> dict:
        """
        Analyze topological structure of context.

        Args:
            context_state: Context state tensor
            epsilon: Distance threshold for simplicial complex construction

        Returns:
            Dictionary of topological features
        """
        if not self.use_topological:
            # Fallback: compute basic statistics
            return {
                "betti_numbers": {"b0": 1, "b1": 0, "b2": 0},
                "euler_characteristic": 1,
                "topological_complexity": np.linalg.norm(context_state),
                "topology_enabled": False,
            }

        try:
            # Construct simplicial complex
            self.topological_analytics.construct_simplicial_complex(context_state, epsilon)

            # Compute persistent homology
            homology = self.topological_analytics.compute_persistent_homology(
                context_state, epsilon
            )

            return {
                "betti_numbers": homology["betti_numbers"],
                "euler_characteristic": homology["euler_characteristic"],
                "topological_complexity": homology["topological_complexity"],
                "topology_enabled": True,
            }
        except Exception as e:
            # Fallback on error
            return {
                "betti_numbers": {"b0": 1, "b1": 0, "b2": 0},
                "euler_characteristic": 1,
                "topological_complexity": np.linalg.norm(context_state),
                "topology_enabled": False,
                "error": str(e),
            }

    def get_context_signature(self, context_state: np.ndarray, epsilon: float = 0.5) -> dict:
        """
        Get topological signature for context matching.

        Args:
            context_state: Context state tensor
            epsilon: Distance threshold for simplicial complex construction

        Returns:
            Topological signature dictionary
        """
        topology = self.analyze_context_topology(context_state, epsilon)

        return {
            "b0": topology["betti_numbers"]["b0"],  # Connected components
            "b1": topology["betti_numbers"]["b1"],  # Loops/holes
            "b2": topology["betti_numbers"]["b2"],  # Voids/cavities
            "euler": topology["euler_characteristic"],
            "complexity": topology["topological_complexity"],
            "topology_enabled": topology["topology_enabled"],
        }

    def match_contexts(
        self, query_context: np.ndarray, database: list, epsilon: float = 0.5
    ) -> list:
        """
        Match contexts based on topological signatures.

        Args:
            query_context: Query context state
            database: List of context entries with topological signatures
            epsilon: Distance threshold for simplicial complex construction

        Returns:
            Sorted list of matches with distances
        """
        query_sig = self.get_context_signature(query_context, epsilon)
        matches = []

        for ctx in database:
            db_sig = ctx.get("topological_signature", {})

            # Compute topological distance
            distance = self._compute_topological_distance(query_sig, db_sig)

            matches.append(
                {"context": ctx, "distance": distance, "similarity": 1.0 / (1.0 + distance)}
            )

        return sorted(matches, key=lambda x: x["distance"])

    def _compute_topological_distance(self, sig1: dict, sig2: dict) -> float:
        """Compute distance between two topological signatures."""
        if not sig1 or not sig2:
            return float("inf")

        # Weighted distance based on Betti numbers and complexity
        b0_dist = abs(sig1.get("b0", 0) - sig2.get("b0", 0))
        b1_dist = abs(sig1.get("b1", 0) - sig2.get("b1", 0))
        b2_dist = abs(sig1.get("b2", 0) - sig2.get("b2", 0))
        euler_dist = abs(sig1.get("euler", 0) - sig2.get("euler", 0))
        complexity_dist = abs(sig1.get("complexity", 0) - sig2.get("complexity", 0))

        # Normalize and weight
        distance = (
            0.3 * b0_dist
            + 0.3 * b1_dist
            + 0.2 * b2_dist
            + 0.1 * euler_dist
            + 0.1 * (complexity_dist / (sig1.get("complexity", 1) + 1e-10))
        )

        return distance

    def record_context(self, context_state: np.ndarray, metadata: dict = None):
        """
        Record context for future analysis.

        Args:
            context_state: Context state tensor
            metadata: Optional metadata dictionary
        """
        signature = self.get_context_signature(context_state)

        entry = {
            "context_state": context_state,
            "topological_signature": signature,
            "metadata": metadata or {},
            "timestamp": len(self.context_history),
        }

        self.context_history.append(entry)

    def get_context_clusters(self, n_clusters: int = 5) -> dict:
        """
        Cluster contexts based on topological signatures.

        Args:
            n_clusters: Number of clusters to create

        Returns:
            Dictionary of cluster assignments
        """
        if len(self.context_history) < n_clusters:
            return {"error": "Not enough contexts for clustering"}

        # Extract signatures
        signatures = [ctx["topological_signature"] for ctx in self.context_history]

        # Simple clustering based on complexity
        complexities = [sig["complexity"] for sig in signatures]
        sorted_indices = np.argsort(complexities)

        # Assign to clusters
        cluster_assignments = {}
        for i, idx in enumerate(sorted_indices):
            cluster_id = i % n_clusters
            cluster_assignments[idx] = cluster_id

        return {
            "n_clusters": n_clusters,
            "assignments": cluster_assignments,
            "cluster_sizes": {
                k: sum(1 for v in cluster_assignments.values() if v == k) for k in range(n_clusters)
            },
        }

    def get_context_flow(self, context_sequence: list) -> dict:
        """
        Analyze topological flow across a sequence of contexts.

        Args:
            context_sequence: List of context states

        Returns:
            Flow analysis results
        """
        if len(context_sequence) < 2:
            return {"error": "Need at least 2 contexts for flow analysis"}

        # Compute signatures for each context
        signatures = [self.get_context_signature(ctx) for ctx in context_sequence]

        # Compute transitions
        transitions = []
        for i in range(len(signatures) - 1):
            distance = self._compute_topological_distance(signatures[i], signatures[i + 1])
            transitions.append(
                {"from": i, "to": i + 1, "distance": distance, "similarity": 1.0 / (1.0 + distance)}
            )

        # Compute flow metrics
        avg_distance = np.mean([t["distance"] for t in transitions])
        max_distance = max([t["distance"] for t in transitions])
        min_distance = min([t["distance"] for t in transitions])

        return {
            "n_transitions": len(transitions),
            "avg_distance": avg_distance,
            "max_distance": max_distance,
            "min_distance": min_distance,
            "transitions": transitions,
        }


class CortexSemanticReasoning:
    """
    Semantic reasoning using topological context analysis.
    """

    def __init__(self, manifold_dimension: int = 5):
        self.topological_context = CortexTopologicalContext(manifold_dimension)
        self.reasoning_history = []

    def infer_context_relationship(self, context1: np.ndarray, context2: np.ndarray) -> dict:
        """
        Infer relationship between two contexts using topological analysis.

        Args:
            context1: First context state
            context2: Second context state

        Returns:
            Relationship analysis
        """
        sig1 = self.topological_context.get_context_signature(context1)
        sig2 = self.topological_context.get_context_signature(context2)

        distance = self.topological_context._compute_topological_distance(sig1, sig2)
        similarity = 1.0 / (1.0 + distance)

        # Determine relationship type
        if similarity > 0.9:
            relationship = "identical"
        elif similarity > 0.7:
            relationship = "similar"
        elif similarity > 0.5:
            relationship = "related"
        elif similarity > 0.3:
            relationship = "distant"
        else:
            relationship = "unrelated"

        return {
            "relationship": relationship,
            "similarity": similarity,
            "distance": distance,
            "signature1": sig1,
            "signature2": sig2,
        }

    def predict_next_context(self, context_sequence: list) -> dict:
        """
        Predict next context based on topological flow.

        Args:
            context_sequence: Sequence of context states

        Returns:
            Prediction results
        """
        if len(context_sequence) < 3:
            return {"error": "Need at least 3 contexts for prediction"}

        # Analyze flow
        flow = self.topological_context.get_context_flow(context_sequence)

        # Compute average transition
        avg_transition = np.mean([t["distance"] for t in flow["transitions"]])

        # Get last context signature
        last_sig = self.topological_context.get_context_signature(context_sequence[-1])

        # Predict similar complexity
        predicted_complexity = last_sig["complexity"] * (1 + 0.1 * np.random.randn())

        return {
            "predicted_complexity": predicted_complexity,
            "avg_transition_distance": avg_transition,
            "flow_stability": 1.0 / (1.0 + np.std([t["distance"] for t in flow["transitions"]])),
            "last_signature": last_sig,
        }


# Convenience function for quick testing
def test_cortex_topological_context():
    """Test the Cortex Topological Context enhancement."""
    print("\n=== Testing Cortex Topological Context Enhancement ===\n")

    # Initialize
    topo_context = CortexTopologicalContext(manifold_dimension=5)
    semantic_reasoning = CortexSemanticReasoning(manifold_dimension=5)

    # Test context analysis
    print("Testing context topology analysis:")
    context1 = np.random.randn(10, 5)
    topology1 = topo_context.analyze_context_topology(context1, epsilon=0.5)
    print(f"  Context 1 topology: {topology1}")

    context2 = np.random.randn(10, 5)
    topology2 = topo_context.analyze_context_topology(context2, epsilon=0.5)
    print(f"  Context 2 topology: {topology2}")

    # Test context matching
    print("\nTesting context matching:")
    database = [
        {
            "context_state": context1,
            "topological_signature": topo_context.get_context_signature(context1),
        },
        {
            "context_state": context2,
            "topological_signature": topo_context.get_context_signature(context2),
        },
    ]

    query_context = np.random.randn(10, 5)
    matches = topo_context.match_contexts(query_context, database)
    print(f"  Found {len(matches)} matches")
    for i, match in enumerate(matches[:2]):
        print(f"    Match {i+1}: similarity = {match['similarity']:.4f}")

    # Test semantic reasoning
    print("\nTesting semantic reasoning:")
    relationship = semantic_reasoning.infer_context_relationship(context1, context2)
    print(f"  Relationship: {relationship['relationship']}")
    print(f"  Similarity: {relationship['similarity']:.4f}")

    # Test context flow
    print("\nTesting context flow:")
    context_sequence = [np.random.randn(10, 5) for _ in range(5)]
    flow = topo_context.get_context_flow(context_sequence)
    print(f"  Transitions: {flow['n_transitions']}")
    print(f"  Avg distance: {flow['avg_distance']:.4f}")
    print(
        f"  Flow stability: {1.0 / (1.0 + np.std([t['distance'] for t in flow['transitions']])):.4f}"
    )

    # Test prediction
    print("\nTesting context prediction:")
    prediction = semantic_reasoning.predict_next_context(context_sequence)
    print(f"  Predicted complexity: {prediction['predicted_complexity']:.4f}")
    print(f"  Flow stability: {prediction['flow_stability']:.4f}")

    print("\n=== Test Complete ===\n")

    return {
        "topology1": topology1,
        "topology2": topology2,
        "relationship": relationship,
        "flow": flow,
        "prediction": prediction,
    }


if __name__ == "__main__":
    test_cortex_topological_context()
