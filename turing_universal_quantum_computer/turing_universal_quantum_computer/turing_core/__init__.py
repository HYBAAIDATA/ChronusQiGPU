"""TURING Core — exact arithmetic, deterministic scheduling, and certification."""

from .core import *  # noqa: F401,F403
from .schedule import (  # noqa: F401
    TuringScheduleError,
    complete_nonce_schedule,
    iter_nonce_schedule,
    validate_schedule,
)
from . import core, schedule  # noqa: F401
from .ten_thousand import (  # noqa: F401
    DEFAULT_UNIVERSAL_QUBITS,
    EntanglementRegistration,
    TenThousandQubitSystem,
    zeckendorf_valid,
)
from . import ten_thousand  # noqa: F401
from .inventory import (  # noqa: F401
    TuringDiscoveryReport,
    TuringModule,
    discover_repository,
)
from .specification import (  # noqa: F401
    Direction,
    ExactField,
    FoldCertificate,
    MachineDescription,
    MachineType,
    Transition,
    TuringCertificate,
    TuringSpecError,
    certify_fold,
    certify_t_phi_fold,
    execute,
    replay,
    verify_fold_replay,
    verify_machine,
)