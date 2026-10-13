"""
HYBA Utilities — Helper Functions
"""

from typing import List, Tuple, Dict, Any
import math


def format_bytes(n: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if n < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} PB"


def format_ratio(ratio: float) -> str:
    return f"{ratio:.2f}x"


def print_metrics(metrics: Dict[str, Any]) -> None:
    print("\n" + "=" * 60)
    print("HYBA Metrics")
    print("=" * 60)
    for key, value in metrics.items():
        if isinstance(value, float):
            if value > 1000:
                print(f"  {key}: {value:.2e}")
            elif value > 1:
                print(f"  {key}: {value:.2f}")
            else:
                print(f"  {key}: {value:.6f}")
        else:
            print(f"  {key}: {value}")
    print("=" * 60)
