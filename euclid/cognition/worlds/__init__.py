"""Interactive task worlds for falsifiable integrated-intelligence research.

Worlds are environments, not intelligence: they hold hidden mechanisms an
agent must discover through a governed, budgeted executor.  See
:mod:`.families` for the declared generating distributions.
"""
from .families import (
    ADVERSARIAL_TAGS,
    FAMILIES,
    HELD_OUT,
    IN_DISTRIBUTION,
    SuiteTask,
    generate_suite,
    generate_task,
    isomorph,
    resample_mechanisms,
)
from .mechanisms import Mechanism, hypothesis_space, run_program
from .world import (
    ASSIGN,
    MAXIMISE_RESPONSE,
    HiddenTruth,
    MechanismWorld,
    TaskSpec,
    WorldExecutor,
    normalise_program,
)

__all__ = [
    "ADVERSARIAL_TAGS",
    "ASSIGN",
    "FAMILIES",
    "HELD_OUT",
    "HiddenTruth",
    "IN_DISTRIBUTION",
    "MAXIMISE_RESPONSE",
    "Mechanism",
    "MechanismWorld",
    "SuiteTask",
    "TaskSpec",
    "WorldExecutor",
    "generate_suite",
    "generate_task",
    "hypothesis_space",
    "isomorph",
    "normalise_program",
    "resample_mechanisms",
    "run_program",
]
