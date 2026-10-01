"""Serverless (AWS Lambda / Google Cloud Run / Azure Functions) adapter.

Emits deployment manifests. No cloud SDK required.
"""
from __future__ import annotations

import json
from typing import Dict


class ServerlessAdapter:
    def aws_lambda(self, memory_mb: int = 3008, timeout_s: int = 300) -> str:
        cfg = {
            "functionName": "hyba-phi-worker",
            "runtime": "python3.11",
            "handler": "lambda_handler.handler",
            "memorySize": int(memory_mb),
            "timeout": int(timeout_s),
            "architectures": ["arm64"],
            "claim_lane": "MATHEMATICAL_QUANTUM (SUBSTRATE-AGNOSTIC)",
        }
        return json.dumps(cfg, indent=2)

    def google_cloud_run(self, cpu: int = 2, memory_gb: int = 4) -> str:
        cfg = {
            "service": "hyba-phi",
            "image": "gcr.io/hyba/phi:0.3.3",
            "cpu": int(cpu),
            "memory": f"{int(memory_gb)}Gi",
            "maxInstances": 100,
            "claim_lane": "MATHEMATICAL_QUANTUM (SUBSTRATE-AGNOSTIC)",
        }
        return json.dumps(cfg, indent=2)

    def azure_functions(self, plan: str = "Consumption") -> str:
        cfg = {
            "functionApp": "hyba-phi",
            "runtime": "python",
            "version": "3.11",
            "plan": plan,
            "claim_lane": "MATHEMATICAL_QUANTUM (SUBSTRATE-AGNOSTIC)",
        }
        return json.dumps(cfg, indent=2)

    def status(self) -> Dict:
        return {"providers": ["aws", "gcp", "azure"], "available": True}
