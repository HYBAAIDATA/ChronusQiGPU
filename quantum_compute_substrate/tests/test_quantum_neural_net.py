"""Tests for the quantum-mathematical neural network."""

import numpy as np
from quantum_compute_substrate.quantum_neural_net import QuantumNeuralNetwork, QuantumNeuralLayer


class TestQuantumNeuralLayer:
    def test_initialization(self):
        layer = QuantumNeuralLayer(16, 8, seed=42)
        assert layer.input_dim == 16
        assert layer.output_dim == 8
        assert layer.weights_real.shape == (8, 16)
        assert layer.bias.shape == (8,)

    def test_forward_pass(self):
        layer = QuantumNeuralLayer(16, 8, seed=42)
        x = np.random.randn(16)
        out = layer.forward(x)
        assert out.shape == (8,)
        # After ReLU, all values should be >= 0
        assert np.all(out >= 0)

    def test_parameter_count(self):
        layer = QuantumNeuralLayer(16, 8, seed=42)
        # 8*16 (real) + 8*16 (imag) + 8 (bias) = 264
        assert layer.parameter_count() == 8 * 16 * 2 + 8

    def test_backward_updates_weights(self):
        np.random.seed(0)
        layer = QuantumNeuralLayer(16, 8, seed=42)
        x = np.random.randn(16)
        layer.forward(x)
        grad = np.ones(8)  # deterministic non-zero gradient
        original_weights = layer.weights_real.copy()
        layer.backward(grad, lr=0.1)
        assert not np.allclose(original_weights, layer.weights_real, atol=1e-12)


class TestQuantumNeuralNetwork:
    def test_initialization(self):
        net = QuantumNeuralNetwork([16, 32, 16, 2], seed=42)
        assert len(net.layers) == 3
        assert net.parameter_count() > 0

    def test_forward_pass(self):
        net = QuantumNeuralNetwork([16, 32, 16, 2], seed=42)
        x = np.random.randn(16)
        out = net.forward(x)
        assert out.shape == (2,)

    def test_training_reduces_loss(self):
        rng = np.random.default_rng(42)
        X = rng.standard_normal((50, 16))
        Y = np.sin(X[:, :2])
        net = QuantumNeuralNetwork([16, 32, 16, 2], seed=42)
        result = net.train(X, Y, epochs=50, lr=0.01)
        assert result["final_loss"] < result["initial_loss"]
        assert result["loss_reduction_pct"] > 0

    def test_measured_performance(self):
        rng = np.random.default_rng(42)
        X = rng.standard_normal((20, 16))
        Y = np.sin(X[:, :2])
        net = QuantumNeuralNetwork([16, 32, 2], seed=42)
        result = net.train(X, Y, epochs=20, lr=0.01)
        assert result["time_seconds"] > 0
        assert result["samples_per_second"] > 0
        assert result["parameter_count"] > 0

    def test_estimate_parameters_for_target(self):
        projection = QuantumNeuralNetwork.estimate_parameters_for_target(10**12)
        assert projection["target_parameters"] == 10**12
        assert projection["estimated_parameters"] >= 10**12
        assert projection["memory_required_gb"] > 0
