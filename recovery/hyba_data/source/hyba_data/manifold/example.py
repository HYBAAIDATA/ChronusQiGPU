"""
Automated Manifold Discovery (v9.0) - Example Usage

This script demonstrates how to use the Automated Manifold Discovery Engine
to learn optimal manifold geometries for optimization problems.

Examples include:
- Basic manifold discovery
- Cryptographic hash-specific discovery
- Custom neural network configuration
- Quality evaluation
- Checkpointing and resume
- Multi-algorithm comparison

Author: Phi-Grover Development Team
Version: 9.0.0
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from framework import (  # Core classes; Configuration; Enums; Oracles; Utilities
    CryptographicHashManifoldDiscovery,
    EnhancedManifoldDiscoveryEngine,
    GradientFlowConfig,
    ManifoldRepresentation,
    NeuralEmbeddingConfig,
    OptimizationAlgorithm,
    PhiResonanceOracle,
    QualityEvaluator,
    SphereOracle,
    SymmetryDetector,
)


def example_basic_discovery():
    """Example 1: Basic manifold discovery."""
    print("\n" + "=" * 78)
    print("Example 1: Basic Manifold Discovery")
    print("=" * 78)

    # Create oracle
    oracle = PhiResonanceOracle()

    # Create discovery engine
    engine = EnhancedManifoldDiscoveryEngine(
        representation=ManifoldRepresentation.NEURAL_EMBEDDING,
        optimizer_algorithm=OptimizationAlgorithm.ADAM,
        verbose=True,
    )

    # Run discovery (short run for demo)
    results = engine.discover(oracle, max_iterations=500, hash_function=None)  # Short run for demo

    # Print results
    print("\n" + "-" * 78)
    print("Results:")
    print("-" * 78)
    print(f"Detected symmetries: {len(results['symmetries'])}")
    for i, symmetry in enumerate(results["symmetries"][:3]):
        print(f"  {i+1}. {symmetry.symmetry_type.value}: {symmetry.confidence:.4f}")

    print(f"\nGenerated proposals: {len(results['proposals'])}")
    for i, proposal in enumerate(results["proposals"][:3]):
        print(f"  {i+1}. {proposal.manifold_type}: {proposal.expected_performance:.4f}")

    if results["quality_metrics"]:
        quality = results["quality_metrics"]
        print("\nQuality Metrics:")
        print(f"  Overall Score: {quality.overall_score:.4f}")
        print(f"  Exploration Efficiency: {quality.exploration_efficiency:.4f}")
        print(f"  Convergence Rate: {quality.convergence_rate:.4f}")
        print(f"  Smoothness: {quality.smoothness:.4f}")


def example_cryptographic_hash_discovery():
    """Example 2: Cryptographic hash-specific discovery."""
    print("\n" + "=" * 78)
    print("Example 2: Cryptographic Hash-Specific Discovery (SHA-256)")
    print("=" * 78)

    # Create oracle
    oracle = PhiResonanceOracle()

    # Create hash-specific discovery
    discovery = CryptographicHashManifoldDiscovery(
        hash_function="sha256",
        optimizer_config=GradientFlowConfig(
            algorithm=OptimizationAlgorithm.ADAM,
            learning_rate=0.001,
            max_iterations=500,
        ),
        checkpoint_dir=None,  # No checkpointing for demo
    )

    # Run discovery
    manifold, quality = discovery.discover(
        oracle, max_iterations=500, verbose=True  # Short run for demo
    )

    # Print results
    print("\n" + "-" * 78)
    print("Results:")
    print("-" * 78)
    print("Hash Function: sha256")
    print(f"Overall Quality Score: {quality.overall_score:.4f}")
    print(f"Exploration Efficiency: {quality.exploration_efficiency:.4f}")
    print(f"Convergence Rate: {quality.convergence_rate:.4f}")
    print(f"Smoothness: {quality.smoothness:.4f}")
    print(f"Coverage: {quality.coverage:.4f}")
    print(f"Embedding Diversity: {quality.embedding_diversity:.4f}")
    print(f"Oracle Correlation: {quality.oracle_correlation:.4f}")
    print(f"Manifold Curvature: {quality.manifold_curvature:.4f}")


def example_custom_neural_network():
    """Example 3: Custom neural network configuration."""
    print("\n" + "=" * 78)
    print("Example 3: Custom Neural Network Configuration")
    print("=" * 78)

    # Create custom neural network configuration
    nn_config = NeuralEmbeddingConfig(
        input_dim=32,
        hidden_dims=[128, 64, 32],
        output_dim=5,
        activation="tanh",
        use_skip_connections=True,
        initialization="xavier",
    )

    # Create optimizer configuration
    optimizer_config = GradientFlowConfig(
        algorithm=OptimizationAlgorithm.ADAM,
        learning_rate=0.001,
        beta1=0.9,
        beta2=0.999,
        max_iterations=500,
        l2_regularization=0.01,
        use_warmup=True,
        warmup_steps=100,
    )

    # Create oracle
    oracle = PhiResonanceOracle()

    # Create hash-specific discovery with custom config
    discovery = CryptographicHashManifoldDiscovery(
        hash_function="generic", nn_config=nn_config, optimizer_config=optimizer_config
    )

    # Run discovery
    manifold, quality = discovery.discover(oracle, max_iterations=500, verbose=True)

    # Print results
    print("\n" + "-" * 78)
    print("Results:")
    print("-" * 78)
    print(f"Network Architecture: {nn_config.hidden_dims}")
    print(f"Output Dimension: {nn_config.output_dim}")
    print(f"Overall Quality Score: {quality.overall_score:.4f}")


def example_quality_evaluation():
    """Example 4: Quality evaluation and analysis."""
    print("\n" + "=" * 78)
    print("Example 4: Quality Evaluation and Analysis")
    print("=" * 78)

    # Create oracle
    oracle = SphereOracle(dimension=10)

    # Create discovery engine
    engine = EnhancedManifoldDiscoveryEngine(
        representation=ManifoldRepresentation.NEURAL_EMBEDDING,
        optimizer_algorithm=OptimizationAlgorithm.ADAM,
        verbose=False,
    )

    # Run discovery
    results = engine.discover(oracle, max_iterations=500, hash_function=None)

    # Evaluate quality
    if results["learned_manifold"]:
        evaluator = QualityEvaluator(sample_size=500)
        quality = evaluator.evaluate(results["learned_manifold"], oracle)

        print("\n" + "-" * 78)
        print("Quality Metrics:")
        print("-" * 78)
        print(f"Exploration Efficiency: {quality.exploration_efficiency:.6f}")
        print(f"Convergence Rate: {quality.convergence_rate:.6f}")
        print(f"Smoothness: {quality.smoothness:.6f}")
        print(f"Coverage: {quality.coverage:.6f}")
        print(f"Gradient Norm: {quality.gradient_norm:.6f}")
        print(f"Parameter Variance: {quality.parameter_variance:.6f}")
        print(f"Embedding Diversity: {quality.embedding_diversity:.6f}")
        print(f"Oracle Correlation: {quality.oracle_correlation:.6f}")
        print(f"Manifold Curvature: {quality.manifold_curvature:.6f}")
        print(f"Overall Score: {quality.overall_score:.6f}")


def example_symmetry_detection():
    """Example 5: Symmetry detection and analysis."""
    print("\n" + "=" * 78)
    print("Example 5: Symmetry Detection and Analysis")
    print("=" * 78)

    # Create oracle
    oracle = PhiResonanceOracle()

    # Create symmetry detector
    detector = SymmetryDetector(sample_size=500, tolerance=1e-3)

    # Detect symmetries
    symmetries = detector.detect_all_symmetries(oracle)

    print("\n" + "-" * 78)
    print("Detected Symmetries:")
    print("-" * 78)

    for i, symmetry in enumerate(symmetries):
        print(f"\n{i+1}. {symmetry.symmetry_type.value}")
        print(f"   Confidence: {symmetry.confidence:.4f}")
        if symmetry.confidence > 0.3:
            print(f"   Parameters: {symmetry.parameters}")
            print(f"   Evidence points: {len(symmetry.evidence)}")


def example_multi_algorithm_comparison():
    """Example 6: Compare multiple optimization algorithms."""
    print("\n" + "=" * 78)
    print("Example 6: Multi-Algorithm Comparison")
    print("=" * 78)

    # Create oracle
    oracle = PhiResonanceOracle()

    # Define algorithms to compare
    algorithms = [
        OptimizationAlgorithm.ADAM,
        OptimizationAlgorithm.RMSPROP,
        OptimizationAlgorithm.MOMENTUM,
    ]

    results = {}

    for algo in algorithms:
        print(f"\nTesting {algo.value}...")

        engine = EnhancedManifoldDiscoveryEngine(
            representation=ManifoldRepresentation.NEURAL_EMBEDDING,
            optimizer_algorithm=algo,
            verbose=False,
        )

        result = engine.discover(oracle, max_iterations=300, hash_function=None)

        if result["quality_metrics"]:
            results[algo.value] = result["quality_metrics"].overall_score
        else:
            results[algo.value] = 0.0

    # Print comparison
    print("\n" + "-" * 78)
    print("Algorithm Comparison (Quality Score):")
    print("-" * 78)

    for algo, score in sorted(results.items(), key=lambda x: x[1], reverse=True):
        print(f"  {algo:15s}: {score:.4f}")


def example_checkpointing():
    """Example 7: Checkpointing and resume (demonstration)."""
    print("\n" + "=" * 78)
    print("Example 7: Checkpointing and Resume")
    print("=" * 78)

    # Create temporary checkpoint directory
    checkpoint_dir = "temp_checkpoints"

    # Create oracle
    oracle = PhiResonanceOracle()

    # Create discovery with checkpointing
    discovery = CryptographicHashManifoldDiscovery(
        hash_function="generic",
        optimizer_config=GradientFlowConfig(
            algorithm=OptimizationAlgorithm.ADAM, max_iterations=300
        ),
        checkpoint_dir=checkpoint_dir,
    )

    # Run discovery (will checkpoint automatically)
    manifold, quality = discovery.discover(oracle, max_iterations=300, verbose=True)

    print("\n" + "-" * 78)
    print("Checkpoint Information:")
    print("-" * 78)

    # List checkpoint files
    checkpoint_path = Path(checkpoint_dir)
    if checkpoint_path.exists():
        checkpoint_files = list(checkpoint_path.glob("checkpoint_*.json"))
        print(f"Checkpoint files created: {len(checkpoint_files)}")

        # Clean up
        import shutil

        shutil.rmtree(checkpoint_dir)
        print("Cleaned up checkpoint directory")
    else:
        print("No checkpoint directory created (checkpoints disabled or not triggered)")


def main():
    """Run all examples."""
    print("\n" + "=" * 78)
    print("AUTOMATED MANIFOLD DISCOVERY (v9.0) - EXAMPLES")
    print("=" * 78)

    examples = [
        ("Basic Discovery", example_basic_discovery),
        ("Cryptographic Hash Discovery", example_cryptographic_hash_discovery),
        ("Custom Neural Network", example_custom_neural_network),
        ("Quality Evaluation", example_quality_evaluation),
        ("Symmetry Detection", example_symmetry_detection),
        ("Multi-Algorithm Comparison", example_multi_algorithm_comparison),
        ("Checkpointing", example_checkpointing),
    ]

    for name, example_func in examples:
        try:
            example_func()
        except Exception as e:
            print(f"\nError in {name}: {e}")
            import traceback

            traceback.print_exc()

    print("\n" + "=" * 78)
    print("All examples completed")
    print("=" * 78)


if __name__ == "__main__":
    main()
