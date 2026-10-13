"""LLM Gateway configuration.

No secrets are stored here. Provider credentials are injected at runtime
from the environment or a secrets manager.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class LLMGatewayConfig:
    """Configuration for the commercial LLM Gateway."""

    default_provider: str = "bedrock"
    providers: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {
            "bedrock": {
                "model": "us.anthropic.claude-sonnet-4-20250514-v1:0",
                "region": "us-east-1",
                "temperature": 0.7,
                "max_tokens": 4096,
            },
            "openai": {
                "model": "gpt-4o-mini",
                "temperature": 0.7,
                "max_tokens": 4096,
            },
            "anthropic": {
                "model": "claude-sonnet-4-20250514",
                "temperature": 0.7,
                "max_tokens": 4096,
            },
        }
    )
    enable_euclid_augmentation: bool = True
    augmenter_config: Dict[str, Any] = field(
        default_factory=lambda: {
            "use_meta_evolution": True,
            "use_predictive_solver": True,
            "use_counterfactual": True,
            "memory_weights": {
                "pythia_memory": 0.3,
                "tool_memory": 0.2,
                "feature_memory": 0.5,
            },
        }
    )
    fallback_provider: str = "bedrock"
    max_retries: int = 3
    timeout: float = 30.0
    enable_metrics: bool = True
    metrics_prefix: str = "llm_gateway"
