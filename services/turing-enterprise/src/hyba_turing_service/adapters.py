"""Lazy adapters to existing authorities. No replacement quantum engine."""


class TuringPipelineRuntime:
    """Trusted in-process pilot adapter, NOT a sandbox for untrusted QASM.

    Production must supply a worker-process timeout, resource isolation and
    tenant-scoped durable result custody before exposing network submission.
    """

    def run(self, request):
        from turing_universal_quantum_computer.pipeline import VQCRequest, run_pipeline

        return run_pipeline(
            VQCRequest(
                qasm=request["qasm"],
                shots=request.get("shots"),
                seed=request.get("seed"),
                max_amplitudes=1 << 20,
                verify_unitary=True,
                differential=True,
            )
        ).as_dict()
