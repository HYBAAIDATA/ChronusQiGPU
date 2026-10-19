"""Public API failures. Refusal and timeout never imply a hardware submission."""


class QuantumPipelineError(Exception):
    """Base public API exception."""


class ConfigurationError(QuantumPipelineError, ValueError):
    """Invalid configuration."""


class CapabilityError(QuantumPipelineError):
    """Unsupported operation; no implicit downgrade."""


class CompilationError(QuantumPipelineError):
    """Invalid or unadmitted circuit; no execution performed."""


class ParameterValidationError(QuantumPipelineError, ValueError):
    """Named values violate a schema."""


class JobExecutionError(QuantumPipelineError):
    def __init__(self, message: str, *, job_id: str | None = None, report_json: str | None = None):
        super().__init__(message)
        self.job_id = job_id
        self.report_json = report_json


class JobTimeoutError(JobExecutionError, TimeoutError):
    """The wait expired; the job may still be running. Do not resubmit blindly."""


class ResultValidationError(JobExecutionError):
    """Result or provenance failed validation."""


class IdempotencyConflictError(QuantumPipelineError):
    """An idempotency key was reused for a different request."""
