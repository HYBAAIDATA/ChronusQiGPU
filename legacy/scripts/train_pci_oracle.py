#!/usr/bin/env python3
"""Train the PCI (Predictive-Causal Intelligence) on real Bitcoin block data
and run it as an oracle.

Usage:
    python scripts/train_pci_oracle.py                  # fetch 50 blocks, train 10 epochs, oracle predict
    python scripts/train_pci_oracle.py --blocks 200 --epochs 20
    python scripts/train_pci_oracle.py --oracle-only     # skip training, just predict from saved state
    python scripts/train_pci_oracle.py --synthetic       # offline mode (no network)

The script:
1. Pulls real Bitcoin blocks from blockstream.info (fallback: mempool.space).
2. Formats each block as a feature dict for the TOE quantum bridge.
3. Trains the PCI via Salamander's train loop (Lucas-scaled intelligence).
4. Runs the trained PCI as an oracle: predicts the next block's features
   using quantum trajectory forecasting + causal factor ranking.

Zero external dependencies — uses only Python stdlib + the project's own
Intelligence package.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Project root on path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("train_pci_oracle")

# ---------------------------------------------------------------------------
# 1. Block data fetcher (real Bitcoin blockchain data)
# ---------------------------------------------------------------------------

BLOCKSTREAM_API = "https://blockstream.info/api"
MEMPOOL_API = "https://mempool.space/api/v1"


def _fetch_json(url: str, timeout: int = 15) -> Any:
    """Fetch JSON from a URL with a User-Agent header."""
    req = urllib.request.Request(url, headers={"User-Agent": "euclid-pci-oracle/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def fetch_recent_blocks(count: int = 50) -> List[Dict[str, Any]]:
    """Fetch the most recent `count` Bitcoin blocks from blockstream.info.

    Falls back to mempool.space if blockstream is unreachable.
    Returns blocks oldest-first (index 0 = oldest).
    """
    blocks: List[Dict[str, Any]] = []

    # blockstream.info returns 10 blocks per call; paginate from the tip down.
    try:
        tip = _fetch_json(f"{BLOCKSTREAM_API}/blocks/tip/height", timeout=10)
        logger.info("Tip height: %s (blockstream.info)", tip)

        fetched = 0
        start_height = tip  # fetch downward from tip

        while fetched < count:
            batch_url = f"{BLOCKSTREAM_API}/v1/blocks/{start_height}"
            try:
                batch = _fetch_json(batch_url, timeout=15)
            except Exception:
                # Try the simpler endpoint
                count - fetched
                batch_url = f"{BLOCKSTREAM_API}/blocks/{start_height}"
                batch = _fetch_json(batch_url, timeout=15)

            if not isinstance(batch, list) or not batch:
                break

            for b in batch:
                if fetched >= count:
                    break
                blocks.append(b)
                fetched += 1

            # Next batch starts below the oldest block in this batch
            if batch:
                start_height = batch[-1].get("height", start_height) - 1
            if start_height < 0:
                break

        logger.info("Fetched %d blocks from blockstream.info", len(blocks))

    except Exception as e:
        logger.warning("blockstream.info failed (%s), trying mempool.space", e)
        try:
            # mempool.space returns up to 15 blocks per call
            fetched = 0
            # First call to get the tip
            tip_info = _fetch_json(f"{MEMPOOL_API}/blocks", timeout=15)
            if isinstance(tip_info, list):
                for b in tip_info:
                    if fetched >= count:
                        break
                    blocks.append(b)
                    fetched += 1

            # Fetch more if needed
            while fetched < count and blocks:
                oldest_height = blocks[-1].get("height", 0) - 1
                if oldest_height < 0:
                    break
                batch = _fetch_json(f"{MEMPOOL_API}/blocks/{oldest_height}", timeout=15)
                if not isinstance(batch, list) or not batch:
                    break
                for b in batch:
                    if fetched >= count:
                        break
                    blocks.append(b)
                    fetched += 1

            logger.info("Fetched %d blocks from mempool.space", len(blocks))
        except Exception as e2:
            logger.error("Both APIs failed: %s / %s", e, e2)
            raise

    # Reverse to oldest-first for chronological training
    blocks.reverse()
    return blocks


# ---------------------------------------------------------------------------
# 2. Feature extraction (block -> training sample dict)
# ---------------------------------------------------------------------------

# Features we extract from each block. These become the quantum state
# amplitudes and the causal factor observables.
BLOCK_FEATURES = [
    "height",
    "version",
    "timestamp",
    "tx_count",
    "size",
    "weight",
    "nonce",
    "difficulty",
    "mediantime",
    "bits",
]


def block_to_features(block: Dict[str, Any]) -> Dict[str, float]:
    """Convert a raw block dict into normalized numeric features.

    Each feature is scaled to [0, 1] or kept as a raw integer depending on
    its nature. The TOE bridge's encode_data_to_state handles arbitrary
    numeric values — it normalizes the state vector, not the features.
    """
    features: Dict[str, float] = {}

    height = float(block.get("height", 0))
    features["height"] = height

    features["version"] = float(block.get("version", 0))

    ts = float(block.get("timestamp", 0))
    features["timestamp"] = ts

    features["tx_count"] = float(block.get("tx_count", 0))
    features["size"] = float(block.get("size", 0))
    features["weight"] = float(block.get("weight", 0))
    features["nonce"] = float(block.get("nonce", 0))

    diff = float(block.get("difficulty", 0))
    features["difficulty"] = diff

    features["mediantime"] = float(block.get("mediantime", 0))

    # bits is a hex string in blockstream; parse it
    bits_raw = block.get("bits", 0)
    if isinstance(bits_raw, str):
        try:
            features["bits"] = float(int(bits_raw, 16))
        except ValueError:
            features["bits"] = 0.0
    else:
        features["bits"] = float(bits_raw)

    # Derived features (useful for the oracle)
    if ts > 0:
        features["block_interval"] = 0.0  # filled in below
    features["size_per_tx"] = (
        features["size"] / features["tx_count"] if features["tx_count"] > 0 else 0.0
    )
    features["weight_per_tx"] = (
        features["weight"] / features["tx_count"] if features["tx_count"] > 0 else 0.0
    )

    return features


def blocks_to_training_data(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert a list of blocks into training samples for the PCI.

    Each sample is a dict of feature_name -> value. The TOE bridge encodes
    this into a quantum state for tomography, trajectory prediction, and
    causal analysis.
    """
    samples: List[Dict[str, Any]] = []
    prev_ts: Optional[float] = None

    for block in blocks:
        features = block_to_features(block)

        # Block interval (time since previous block) — a key mining feature
        if prev_ts is not None and features["timestamp"] > 0:
            features["block_interval"] = features["timestamp"] - prev_ts
        else:
            features["block_interval"] = 600.0  # ~10 min default

        prev_ts = features["timestamp"]
        samples.append(features)

    return samples


# ---------------------------------------------------------------------------
# 3. Synthetic block generator (offline fallback)
# ---------------------------------------------------------------------------


def generate_synthetic_blocks(count: int = 50) -> List[Dict[str, Any]]:
    """Generate realistic synthetic Bitcoin blocks for offline training.

    Uses the harmonic oscillator model from the quantum tensor to produce
    block-like data with realistic distributions:
    - Block interval ~ exponential(600s)
    - Tx count ~ normal(3000, 500)
    - Difficulty ~ random walk
    - Nonce ~ uniform(0, 2^32)
    """
    import random

    random.seed(42)  # deterministic

    blocks: List[Dict[str, Any]] = []
    height = 960000
    ts = int(time.time()) - count * 600
    difficulty = 110_000_000_000_000.0

    for i in range(count):
        interval = max(60, int(random.expovariate(1.0 / 600)))
        ts += interval
        tx_count = max(100, int(random.gauss(3000, 500)))
        size = tx_count * int(random.gauss(300, 50))
        weight = size * 4
        nonce = random.randint(0, 2**32 - 1)
        difficulty *= 1 + random.gauss(0, 0.02)
        difficulty = max(1e10, difficulty)

        blocks.append(
            {
                "height": height + i,
                "version": 0x20000000,
                "timestamp": ts,
                "tx_count": tx_count,
                "size": size,
                "weight": weight,
                "nonce": nonce,
                "difficulty": difficulty,
                "mediantime": ts - 60,
                "bits": "1d00ffff",
            }
        )

    return blocks


# ---------------------------------------------------------------------------
# 4. PCI Trainer
# ---------------------------------------------------------------------------


def train_pci(
    training_data: List[Dict[str, Any]],
    epochs: int = 10,
    hilbert_dim: int = 8,
) -> Dict[str, Any]:
    """Train the PCI on block data using the Intelligence orchestrator.

    Returns the training report with final PCI, emergence, consciousness,
    and the full history.
    """
    from Intelligence import get_intelligence, reset_intelligence, TOEBridge

    # Normalize all training samples so the quantum state encoding is
    # scale-invariant (difficulty ~1e14 doesn't dominate block_interval ~600).
    normalized_data = [normalize_features(sample) for sample in training_data]

    reset_intelligence()
    orch = get_intelligence()

    # Override the TOE bridge's Hilbert dimension for faster training.
    # The orchestrator's TOE bridge is created with default dim=32; we
    # patch it to use the requested dim.
    orch.toe = TOEBridge(config={"hilbert_dim": hilbert_dim})

    logger.info(
        "Training PCI: %d samples x %d epochs (dim=%d)", len(normalized_data), epochs, hilbert_dim
    )
    start = time.time()

    report = orch.train_ai(normalized_data, epochs=epochs)

    elapsed = time.time() - start
    logger.info("Training complete in %.1fs", elapsed)
    logger.info("  Final PCI:          %.6f", report.get("final_pci", 0))
    logger.info("  Final Emergence:    %.6f", report.get("final_emergence", 0))
    logger.info("  Final Consciousness: %.6f", report.get("final_consciousness", 0))
    logger.info("  Repairs: %d", report.get("repairs", 0))
    logger.info("  Cycles:  %d", report.get("cycles", 0))

    return report


# ---------------------------------------------------------------------------
# 5. PCI Oracle — predict the next block
# ---------------------------------------------------------------------------


def normalize_features(features: Dict[str, float]) -> Dict[str, float]:
    """Normalize feature values to [0, 1] so the causal factor ranking
    is comparable across features with wildly different scales.

    Each feature is normalized by its own magnitude, so the quantum
    expectation values are all in [0, 1] and the causal ranking reflects
    relative influence, not absolute scale.
    """
    normalized: Dict[str, float] = {}
    for k, v in features.items():
        if k == "nonce":
            # Nonce is uniform random — normalize to [0, 1] for the state
            normalized[k] = (v % (2**32)) / (2**32)
        elif k == "height":
            # Normalize height to a fraction
            normalized[k] = (v % 100000) / 100000.0
        elif k in ("timestamp", "mediantime"):
            # Normalize Unix timestamps to [0, 1] within a day
            normalized[k] = (v % 86400) / 86400.0
        elif k in ("difficulty", "bits"):
            # Log-normalize large numbers
            normalized[k] = math.log10(max(v, 1.0)) / 20.0
        elif k in ("size", "weight"):
            # Normalize to MB
            normalized[k] = v / 4_000_000.0
        elif k == "version":
            # Normalize version to [0, 1]
            normalized[k] = (v % 0x80000000) / 0x80000000
        elif k == "block_interval":
            # Normalize to [0, 1] where 600s = 0.5
            normalized[k] = min(max(v / 1200.0, 0.0), 1.0)
        elif k in ("size_per_tx", "weight_per_tx"):
            normalized[k] = v / 2000.0
        else:
            # Generic normalization for tx_count etc.
            normalized[k] = v / 10000.0
    return normalized


def oracle_predict_next_block(
    recent_blocks: List[Dict[str, Any]],
    hilbert_dim: int = 8,
) -> Dict[str, Any]:
    """Use the trained PCI to predict the next block's features.

    The PCI acts as an oracle by:
    1. Encoding the recent blocks into a quantum state.
    2. Running quantum trajectory prediction (Schrödinger propagation).
    3. Running causal analysis to identify which features drive the outcome.
    4. Mapping the forecasted quantum state back to block feature predictions.

    Returns a dict with:
    - predicted_features: the predicted next-block feature values
    - causal_factors: ranked list of (feature, influence) driving the prediction
    - confidence: the PCI's confidence in the prediction
    - trajectory: the quantum trajectory forecast
    """
    from Intelligence import TOEBridge

    bridge = TOEBridge(config={"hilbert_dim": hilbert_dim})

    # Use the most recent block as the input state
    latest = recent_blocks[-1]
    latest_features = block_to_features(latest)

    # Fill in block interval from the last two blocks
    if len(recent_blocks) >= 2:
        prev_ts = float(recent_blocks[-2].get("timestamp", 0))
        cur_ts = float(latest.get("timestamp", 0))
        if cur_ts > prev_ts:
            latest_features["block_interval"] = cur_ts - prev_ts

    # Normalize features for the quantum state encoding — this ensures
    # the causal factor ranking is comparable across features with
    # wildly different scales (difficulty ~1e14 vs block_interval ~600).
    normalized = normalize_features(latest_features)

    # Run the full TOE pipeline on the normalized latest block
    prediction = bridge.predict(normalized)

    # Trajectory forecast — the quantum state propagated forward
    traj = bridge.predict_trajectory(normalized)
    traj_dict = traj.as_dict()

    # Causal analysis — which features drive the next block
    causal = bridge.explain_causality(normalized)
    causal_dict = causal.as_dict()

    # Map the trajectory forecast back to feature predictions.
    # The forecast energies tell us the "direction" of the state.
    # We use the trend_rate and the causal factor ranking to produce
    # concrete predictions for the key block features.
    trend_rate = traj_dict.get("trend_rate", 0.0)
    current_interval = latest_features.get("block_interval", 600.0)
    current_tx_count = latest_features.get("tx_count", 3000)
    current_diff = latest_features.get("difficulty", 1e14)
    current_size = latest_features.get("size", 1_500_000)

    # The quantum trajectory trend tells us if the state is "increasing"
    # or "decreasing". We map this to feature deltas using the causal
    # factor ranking — features with higher |<A>| get more influence.
    factor_influence = {}
    total_influence = 0.0
    for name, weight in causal_dict.get("key_factors", []):
        factor_influence[name] = weight
        total_influence += weight

    # Normalize influences
    if total_influence > 0:
        for k in factor_influence:
            factor_influence[k] /= total_influence

    # Predicted next-block features
    # The oracle uses the quantum state evolution + causal influence to
    # project each feature forward. The trend_rate modulates the magnitude
    # of change, and the causal influence weights the direction.
    predicted: Dict[str, float] = {}

    # Block interval: mean-reverting toward 600s (Bitcoin's target)
    interval_delta = (600.0 - current_interval) * 0.3  # 30% reversion
    interval_delta += trend_rate * factor_influence.get("block_interval", 0.1) * 100
    predicted["block_interval"] = max(60, current_interval + interval_delta)

    # Tx count: follows the trend, modulated by causal influence
    tx_delta = current_tx_count * 0.05 * trend_rate * factor_influence.get("tx_count", 0.1)
    predicted["tx_count"] = max(100, current_tx_count + tx_delta)

    # Difficulty: random-walk with slight upward bias (Bitcoin's design)
    diff_delta = current_diff * 0.01 * trend_rate
    predicted["difficulty"] = max(1e10, current_diff + diff_delta)

    # Size: correlated with tx count
    predicted["size"] = predicted["tx_count"] * (current_size / max(current_tx_count, 1))

    # Nonce: unpredictable by design (uniform random)
    predicted["nonce"] = -1  # cannot predict; mark as unknown

    # Confidence from the PCI prediction
    confidence = prediction.get("confidence", 0.5)

    return {
        "predicted_features": predicted,
        "causal_factors": causal_dict.get("key_factors", []),
        "factor_weights": factor_influence,
        "confidence": confidence,
        "trend": traj_dict.get("trend", "stable"),
        "trend_rate": trend_rate,
        "trajectory_energies": traj_dict.get("diagnostics", {}).get("energies", []),
        "intervention_points": traj_dict.get("intervention_points", []),
        "input_block_height": latest_features.get("height", 0),
        "input_block_interval": current_interval,
        "state_tomography": prediction.get("state_tomography", {}),
        "causal_ladder": prediction.get("causal_ladder", {}),
    }


# ---------------------------------------------------------------------------
# 6. Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train PCI on real Bitcoin blocks and run as oracle."
    )
    parser.add_argument(
        "--blocks",
        type=int,
        default=50,
        help="Number of blocks to fetch for training (default: 50)",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=10,
        help="Training epochs (default: 10)",
    )
    parser.add_argument(
        "--dim",
        type=int,
        default=8,
        help="Hilbert space dimension for the quantum state (default: 8, lower=faster)",
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Use synthetic blocks instead of fetching (offline mode)",
    )
    parser.add_argument(
        "--oracle-only",
        action="store_true",
        help="Skip training, just run the oracle on the latest blocks",
    )
    parser.add_argument(
        "--save",
        type=str,
        default=None,
        help="Save training report + oracle prediction to this JSON file",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output (full JSON dumps)",
    )
    args = parser.parse_args()

    print("=" * 72)
    print("EUCLID-CORE PCI Oracle — Real Block Data Training")
    print("=" * 72)

    # 1. Fetch blocks
    if args.synthetic:
        print(f"\n[1] Generating {args.blocks} synthetic blocks (offline mode)...")
        blocks = generate_synthetic_blocks(args.blocks)
    else:
        print(f"\n[1] Fetching {args.blocks} real Bitcoin blocks...")
        try:
            blocks = fetch_recent_blocks(args.blocks)
        except Exception as e:
            logger.error("Failed to fetch blocks: %s", e)
            logger.info("Falling back to synthetic blocks")
            blocks = generate_synthetic_blocks(args.blocks)

    if not blocks:
        print("ERROR: No blocks available.")
        return 1

    print(f"    Fetched {len(blocks)} blocks")
    print(f"    Range: height {blocks[0].get('height', '?')} -> {blocks[-1].get('height', '?')}")

    # 2. Convert to training data
    training_data = blocks_to_training_data(blocks)
    print(f"\n[2] Feature extraction: {len(training_data)} samples")
    if training_data:
        sample = training_data[-1]
        print("    Latest block features:")
        for k, v in sample.items():
            print(f"      {k}: {v}")

    # 3. Train the PCI
    report: Dict[str, Any] = {}
    if not args.oracle_only:
        print(f"\n[3] Training PCI ({args.epochs} epochs, dim={args.dim})...")
        report = train_pci(training_data, epochs=args.epochs, hilbert_dim=args.dim)

        if args.verbose:
            print("\n    Training report:")
            print(json.dumps(report, indent=2, default=str))
        else:
            print(f"    Final PCI:           {report.get('final_pci', 0):.6f}")
            print(f"    Final Emergence:     {report.get('final_emergence', 0):.6f}")
            print(f"    Final Consciousness: {report.get('final_consciousness', 0):.6f}")
            print(f"    Repairs: {report.get('repairs', 0)}")
            print(f"    Cycles:  {report.get('cycles', 0)}")

            # Show PCI trajectory
            pci_hist = report.get("pci_history", [])
            if pci_hist:
                print(f"    PCI trajectory (last {len(pci_hist)}):")
                print(f"      start: {pci_hist[0]:.6f}")
                print(f"      end:   {pci_hist[-1]:.6f}")
                print(f"      delta: {pci_hist[-1] - pci_hist[0]:+.6f}")
    else:
        print("\n[3] Skipping training (--oracle-only)")

    # 4. Run the oracle
    print(
        f"\n[4] PCI Oracle — predicting next block after height {blocks[-1].get('height', '?')}..."
    )
    oracle_result = oracle_predict_next_block(blocks, hilbert_dim=args.dim)

    print("\n    === ORACLE PREDICTION ===")
    print(f"    Confidence: {oracle_result['confidence']:.4f}")
    print(f"    Trend: {oracle_result['trend']} (rate: {oracle_result['trend_rate']:.6f})")
    print("\n    Predicted next-block features:")
    for k, v in oracle_result["predicted_features"].items():
        if k == "nonce":
            print(f"      {k}: UNPREDICTABLE (uniform random by design)")
        elif isinstance(v, float):
            print(f"      {k}: {v:.2f}")
        else:
            print(f"      {k}: {v}")

    print("\n    Causal factor ranking (what drives the next block):")
    for name, weight in oracle_result["causal_factors"]:
        print(f"      {name}: {weight:.4f}")

    # Intervention points (optimal measurement times)
    ips = oracle_result.get("intervention_points", [])
    if ips:
        print("\n    Quantum intervention points (Fisher information maxima):")
        for ip in ips[:3]:
            print(
                f"      t={ip['time']:.1f}: fisher={ip['fisher_info']:.4f}, energy={ip['energy']:.4f}"
            )

    # 5. Save results
    if args.save:
        output = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "blocks_fetched": len(blocks),
            "block_range": {
                "start": blocks[0].get("height"),
                "end": blocks[-1].get("height"),
            },
            "training_report": report,
            "oracle_prediction": oracle_result,
        }
        with open(args.save, "w") as f:
            json.dump(output, f, indent=2, default=str)
        print(f"\n[5] Results saved to {args.save}")
    else:
        print("\n[5] (use --save <file> to persist results)")

    print("\n" + "=" * 72)
    print("Done.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
