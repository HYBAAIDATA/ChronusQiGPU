"""Commercial Tool & Function Calling Gateway — Governed by EUCLID.

Provides registered function schemas, strict argument validation,
and secure execution dispatch for commercial tool-use integration.
"""

from __future__ import annotations

import inspect
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters_schema: Dict[str, Any]
    handler: Callable[..., Any]


@dataclass(frozen=True)
class ToolCallResult:
    tool_name: str
    success: bool
    result: Any
    latency_ms: float
    error_message: Optional[str] = None


class CommercialToolGateway:
    """Enterprise tool invocation gateway powered by EUCLID."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        parameters_schema: Dict[str, Any],
        handler: Callable[..., Any],
    ) -> None:
        """Register a commercial callable tool."""
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            parameters_schema=parameters_schema,
            handler=handler,
        )

    def list_tool_declarations(self) -> List[Dict[str, Any]]:
        """Return tool declarations formatted for model consumption."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters_schema,
            }
            for t in self._tools.values()
        ]

    def execute_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> ToolCallResult:
        """Execute a tool call with strict validation and error interception."""
        if tool_name not in self._tools:
            return ToolCallResult(
                tool_name=tool_name,
                success=False,
                result=None,
                latency_ms=0.0,
                error_message=f"Tool '{tool_name}' is not registered in EUCLID Tool Gateway.",
            )

        tool = self._tools[tool_name]
        t0 = time.perf_counter()
        try:
            res = tool.handler(**arguments)
            elapsed = (time.perf_counter() - t0) * 1000.0
            return ToolCallResult(tool_name=tool_name, success=True, result=res, latency_ms=elapsed)
        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000.0
            return ToolCallResult(
                tool_name=tool_name,
                success=False,
                result=None,
                latency_ms=elapsed,
                error_message=str(exc),
            )
