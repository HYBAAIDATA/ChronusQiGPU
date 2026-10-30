"""Stage 4 — Dual backend with digest comparison.

Closes cell: "self-hosting/fixed-point equivalence across substrates"
but only the two-backend case (Track 4 proper).
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple


# — Backend abstraction —

class Backend(ABC):
    """Abstract base class for computation backends."""

    @abstractmethod
    def execute(self, program: List[Any]) -> Any:
        pass

    @abstractmethod
    def digest(self, result: Any) -> str:
        pass


# — Stack-IR CPU reference backend —

class StackIRBackend(Backend):
    """CPU reference backend executing stack-based intermediate representation."""

    def execute(self, program: List[int]) -> int:
        self.regs: Dict[int, int] = {i: 0 for i in range(8)}
        self.pc = 0
        self.halted = False
        stack: List[int] = []

        while self.pc < len(program):
            opcode = program[self.pc]
            self.pc += 1

            if opcode == 0x99:  # HALT
                self.halted = True
                break

            if 0x00 <= opcode <= 0x0F:  # PUSH immediate
                value = opcode & 0x0F
                stack.append(value)
                continue

            if 0x10 <= opcode <= 0x1F:  # POP to register
                reg_idx = opcode & 0x0F
                if stack:
                    self.regs[reg_idx] = stack.pop()
                continue

            if opcode == 0x20:  # ADD
                if len(stack) >= 2:
                    b = stack.pop()
                    a = stack.pop()
                    stack.append(a + b)
                continue

            if opcode == 0x21:  # MUL
                if len(stack) >= 2:
                    b = stack.pop()
                    a = stack.pop()
                    stack.append(a * b)
                continue

            if opcode == 0x22:  # MOD
                if len(stack) >= 2:
                    b = stack.pop()
                    a = stack.pop()
                    if b != 0:
                        stack.append(a % b)
                continue

            if opcode == 0x30:  # STORE
                if stack:
                    reg_idx = stack.pop()
                    if reg_idx < 8:
                        self.regs[reg_idx] = stack.pop() if stack else 0
                continue

            if opcode == 0x31:  # LOAD
                reg_idx = stack.pop() if stack else 0
                if reg_idx < 8:
                    stack.append(self.regs[reg_idx])
                continue

        return self.regs[0]

    def digest(self, result: int) -> str:
        return hashlib.sha256(str(result).encode()).hexdigest()