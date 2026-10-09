"""EUCLID integrated adaptive intelligence; canonical specialists resolved on demand."""
from importlib import import_module

_EXPORTS = {
    "AccountingExecutor": ("agent", "AccountingExecutor"),
    "AgentConfig": ("context", "AgentConfig"),
    "AgentKnowledge": ("memory", "AgentKnowledge"),
    "EpisodeContext": ("context", "EpisodeContext"),
    "EpisodeResult": ("agent", "EpisodeResult"),
    "IntegratedAgent": ("agent", "IntegratedAgent"),
    "MechanismPosterior": ("world_model", "MechanismPosterior"),
    "SYSTEMS": ("agent", "SYSTEMS"),
    "SkillLibrary": ("skills", "SkillLibrary"),
    "StructuralMemory": ("memory", "StructuralMemory"),
    "build_problem": ("agent", "build_problem"),
    "structural_class": ("context", "structural_class"),
    "structure_tokens": ("context", "structure_tokens"),
}
__all__ = list(_EXPORTS)


def __getattr__(name):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module, attribute = target
    value = getattr(import_module(f"{__name__}.{module}"), attribute)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
