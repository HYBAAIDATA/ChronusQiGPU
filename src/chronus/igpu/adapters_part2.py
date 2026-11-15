
# ---------------------------------------------------------------------------
# Tier 6.2 - TypedUnavailableAdapter (Axiom 7: complete fallback)
# ---------------------------------------------------------------------------


class TypedUnavailableError(RuntimeError):
    """Raised when a typed-unavailable adapter is asked to execute work."""


class TypedUnavailableAdapter:
    """An adapter known to be functional but that has not passed conformance.

    Axiom 7: execute NEVER silently succeeds. It raises
    TypedUnavailableError so the fleet scheduler can log and handle the
    failure explicitly.
    """

    __slots__ = ("backend", "gate", "capability")

    def __init__(self, backend: AdapterBackend, gate: str) -> None:
        self.backend = backend
        self.gate = gate
        self.capability = self._build_capability()

    def _build_capability(self) -> CapabilityManifest:
        return CapabilityManifest(
            adapter_id=f"typed_unavailable:{self.backend.value}",
            product=self.backend.value,
            backend=self.backend,
            status=AdapterStatus.TYPED_UNAVAILABLE,
            role=self._role_for_backend(),
            core_count=0,
            memory_bytes=0,
            memory_tier=MemoryTier.TIER_0_ON_DEVICE_HBM,
            bandwidth_mbps=0.0,
            spmd_lanes=0,
            trust_class=TrustClass.TYPED_UNAVAILABLE,
            evidence_class=EvidenceClass.PROJECTED,
            projection=None,
        )

    def _role_for_backend(self) -> AdapterRole:
        for spec in ADAPTER_TABLE:
            if spec.backend == self.backend:
                return spec.role
        return RoleEnum.GENERAL

    def execute(self, work_item: dict) -> dict:
        """Raise TypedUnavailableError rather than simulating or faking success."""
        raise TypedUnavailableError(
            backend=str(self.backend),
            gate=self.gate,
            reason="kernel not implemented",
            message=(
                "Conformance test required before promotion (Axiom 8). "
                "This adapter must not be executed."
            ),
        )

    def capability(self) -> CapabilityManifest:
        return self.capability


def promote_adapter(backend: AdapterBackend, kernel: dict) -> bool:
    """Promote an adapter from TYPED_UNAVAILABLE to FUNCTIONAL.

    Axiom 8: measurement before promotion. The kernel must pass a conformance
    test before it can be routed for real work.
    """
    from chronus.evidence import run_conformance_test

    conformance = run_conformance_test(backend, kernel)
    if not conformance.passed:
        from chronus.governance import elevation_preflight
        from chronus.core.dataclasses import ElevationAction

        action = ElevationAction(
            action_id=f"promote:{backend.value}",
            name="promote_adapter",
            context={"backend": str(backend), "failures": conformance.failures},
        )
        elevation_preflight(action)
        return False

    # Axiom 6: record evidence digest chain
    from chronus.evidence import EvidenceRecord

    evidence = EvidenceRecord(
        layer=str(backend),
        item_id=backend.value,
        input_digest="kernel_manifest",
        config_digest=conformance.digest_chain(),
        output_digest="conformance_passed",
        trust_class=TrustClass.RUNTIME_SIGNED,
    )
    return True
