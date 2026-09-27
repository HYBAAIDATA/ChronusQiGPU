"""Tests for the neural plasticity wiring layer."""

from Intelligence.neural_plasticity import NeuralPlasticity


def test_sprout_on_repeated_coactivation():
    p = NeuralPlasticity(sprout_threshold=3)
    for _ in range(5):
        p.co_activate("A", "B")
    assert ("A", "B") in p.synapses


def test_no_sprout_below_threshold():
    p = NeuralPlasticity(sprout_threshold=5)
    for _ in range(3):
        p.co_activate("A", "B")
    assert ("A", "B") not in p.synapses


def test_reward_potentiates():
    p = NeuralPlasticity(learning_rate=0.1)
    for _ in range(5):
        p.co_activate("A", "B")
    w_before = p.synapses[("A", "B")].weight
    p.deliver_reward(1.0)
    assert p.synapses[("A", "B")].weight > w_before


def test_negative_reward_depresses():
    p = NeuralPlasticity(learning_rate=0.1)
    for _ in range(5):
        p.co_activate("A", "B")
    p.synapses[("A", "B")].weight = 0.5
    w_before = p.synapses[("A", "B")].weight
    p.deliver_reward(-1.0)
    assert p.synapses[("A", "B")].weight < w_before


def test_decay_reduces_weight():
    p = NeuralPlasticity(weight_decay=0.1)
    for _ in range(5):
        p.co_activate("A", "B")
    w_before = p.synapses[("A", "B")].weight
    p.decay()
    assert p.synapses[("A", "B")].weight < w_before


def test_crystallization_protects_from_decay():
    p = NeuralPlasticity(crystallize_threshold=0.5, weight_decay=0.5)
    for _ in range(5):
        p.co_activate("A", "B")
    p.synapses[("A", "B")].weight = 0.9
    p.crystallize()
    assert p.synapses[("A", "B")].crystallized
    w_before = p.synapses[("A", "B")].weight
    p.decay()
    assert p.synapses[("A", "B")].weight == w_before


def test_prune_removes_weak():
    p = NeuralPlasticity(prune_threshold=0.05)
    for _ in range(5):
        p.co_activate("A", "B")
    p.synapses[("A", "B")].weight = 0.01
    n = p.prune()
    assert n == 1
    assert ("A", "B") not in p.synapses


def test_homeostatic_scaling():
    p = NeuralPlasticity(homeostatic_target=1.0)
    for i in range(10):
        for _ in range(3):
            p.co_activate(f"A{i}", f"B{i}")
        p.synapses[(f"A{i}", f"B{i}")].weight = 0.5
    total_before = sum(s.weight for s in p.synapses.values())
    p.deliver_reward(0.0)
    total_after = sum(s.weight for s in p.synapses.values())
    assert total_after <= total_before


def test_maturation_reduces_plasticity():
    p = NeuralPlasticity()
    initial = p.plasticity_level
    for _ in range(10):
        p.mature(factor=0.9)
    assert p.plasticity_level < initial


def test_report_structure():
    p = NeuralPlasticity()
    for _ in range(5):
        p.co_activate("A", "B")
    p.deliver_reward(1.0)
    report = p.report()
    for key in ("synapses", "crystallized", "plasticity_level", "strongest"):
        assert key in report


def test_state_dict_roundtrip():
    p1 = NeuralPlasticity()
    for _ in range(5):
        p1.co_activate("A", "B")
    p1.deliver_reward(1.0)
    state = p1.state_dict()
    p2 = NeuralPlasticity()
    p2.load_state_dict(state)
    assert len(p2.synapses) == len(p1.synapses)
    assert p2.plasticity_level == p1.plasticity_level


def test_event_log():
    p = NeuralPlasticity(sprout_threshold=2)
    for _ in range(3):
        p.co_activate("A", "B")
    assert len(p.event_log) > 0
    assert any(e.event_type == "sprout" for e in p.event_log)


def test_strongest_pathways():
    p = NeuralPlasticity()
    for i in range(5):
        for _ in range(3):
            p.co_activate(f"A{i}", f"B{i}")
        p.synapses[(f"A{i}", f"B{i}")].weight = 0.1 * (i + 1)
    strongest = p.strongest_pathways(k=3)
    assert len(strongest) == 3
    assert strongest[0]["weight"] >= strongest[1]["weight"]


def test_pathway_matrix():
    p = NeuralPlasticity()
    for i in range(3):
        for _ in range(3):
            p.co_activate(f"A{i}", f"B{i}")
    M = p.pathway_matrix()
    assert M.shape[0] == M.shape[1]
    assert M.shape[0] == len(p.subsystems)


def test_max_synapses_limit():
    p = NeuralPlasticity(sprout_threshold=1, max_synapses=5)
    for i in range(20):
        p.co_activate(f"A{i}", f"B{i}")
    assert len(p.synapses) <= 5
