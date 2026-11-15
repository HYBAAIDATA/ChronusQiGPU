# fix_mining_admin.py - Simple string replacements for mining_admin.py
path = "c:/Users/leonn/OneDrive/Desktop/chronus-quantum-igpu/src/chronus/execution/mining_admin.py"
with open(path, "r", encoding="utf-8") as f:
    c = f.read()


def rep(old, new):
    global c
    assert old in c, "NOT FOUND: " + old[:80]
    c = c.replace(old, new)


# 1. Docstring
rep("rebalancing, causal do(X) interventions, and counterfactual energy arbitrage.",
    "rebalancing.")

# 2. Imports
rep("from chronus.execution.master_e2e_engine import (", "from chronus.execution.geometric_galois_miner import (")
rep("    PatroclusGateway,", "    ExactGaloisOracleF257,")
rep("    StealthEngine,", "    GeometricGaloisMiner,")
rep("    HodgeSheafLaplacianConsensus,", "    HodgeSheafLaplacianConsensus,")
rep("    LiePoissonRamanujanExpander,", "    LiePoissonRamanujanExpander,")

# 3. __init__
rep("        self.anomaly_injected = False\n        self.dsw_healed = False",
    "        self.active_intervention = \"OBSERVATIONAL\"")

# 4. Remove healer
rep("        self.healer = DSW1CycleInstantonCobordism()\n", "")

# 5. Remove gateway
rep("        self.gateway = PatroclusGateway()\n", "")

# 6. Remove stealth_engine init
rep("        self.stealth_engine = StealthEngine(\n            max_cap_eh=self.config.max_configured_eh_s,\n            active_stealth_eh=self.config.stealth_target_eh_s,\n        )\n", "")

# 7. Remove inject_anomaly and execute_dsw_heal
rep("    def inject_anomaly(self) -> Dict[str, Any]:\n        \"\"\"Simulates an adversarial reorg or stratum poisoning perturbation.\"\"\"\n        self.anomaly_injected = True\n        self.dsw_healed = False\n        return self.get_status()\n\n    def execute_dsw_heal(self) -> Dict[str, Any]:\n        \"\"\"Emits a 4D instanton cobordism to heal cohomology obstruction in 1 cycle.\"\"\"\n        self.dsw_healed = True\n        self.anomaly_injected = False\n        return self.get_status()\n\n", "")

# 8. Replace resonance/causal calc
rep("        # Calculate resonance and effective hashrate\n        h1_error = 1.4142 if (self.anomaly_injected and not self.dsw_healed) else 0.0000\n        resonance_pct = 0.0 if h1_error > 0 else 2.61\n        effective_hashrate = self.config.base_hashrate_eh_s * (1.0 + resonance_pct / 100.0)",
    "        # Effective hashrate is the configured base rate; no fabricated resonance boost.\n        effective_hashrate = self.config.base_hashrate_eh_s")

# 9. Remove causal boost
rep("        # Causal delta estimation\n        causal_boost_eh_s = 0.0\n        if self.active_intervention == \"UNDERVOLT_1_10V\":\n            causal_boost_eh_s = 15.8\n        elif self.active_intervention == \"FAN_100_PCT\":\n            causal_boost_eh_s = 8.4\n", "")

# 10. Remove simulated counterfactual
rep("        # Simulated counterfactual avoided loss\n        avoided_loss_gbp = 116120.00 if self.config.counterfactual_weight > 0 else 0.0",
    "        # Counterfactual avoided loss requires actual grid tariff data; return 0.\n        counterfactual_avoided_loss_gbp = 0.0")

# 11. Replace fabricated resonance values
rep("            \"resonance_boost_pct\": resonance_pct,\n            \"sheaf_cohomology_h1\": h1_error,\n            \"consensus_status\": \"OBSTRUCTED\" if h1_error > 0 else \"HARMONIC_CONSENSUS\",",
    "            \"resonance_boost_pct\": 0.0,\n            \"sheaf_cohomology_h1\": 0.0,\n            \"consensus_status\": \"HARMONIC_CONSENSUS\",")

# 12. Fix patroclus gateway_active and counts
rep("            \"gateway_active\": True,\n                \"total_myrmidons\": self.gateway.invariants.total_searchers,\n                \"phalanxes_count\": self.gateway.invariants.hopf_fibers,",
    "            \"gateway_active\": self.gateway is not None,\n                \"total_myrmidons\": self.gateway.invariants.total_searchers if self.gateway is not None else 0,\n                \"phalanxes_count\": self.gateway.invariants.hopf_fibers if self.gateway is not None else 0,")

# 13. Fix patroclus stealth reference (stale self.stealth_engine)
rep("                \"last_mined_block_height\": self.stealth_engine.last_mined_block_height,\n                \"mined_blocks_count\": len(self.stealth_engine.mined_blocks_history),",
    "                \"last_mined_block_height\": 0,\n                \"mined_blocks_count\": 0,")

# Write
with open(path, "w", encoding="utf-8") as f:
    f.write(c)

print("OK: mining_admin.py updated")
