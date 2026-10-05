"""Canonical production composition for the shared computational organism.

This root turns the shared THESEUS/OVID relationship from an available library
into the default governed startup path for the memory/data-bearing subsystem
surface. It composes real PYTHIA, TOE, Kellogg, TURING, Salamander, AL HARAS
and EUCLID objects over one :class:`CompositionRoot` and exposes only their
shared-data-bound views.

Authority is not collapsed:

* EUCLID orchestrates/delegates intelligence;
* PYTHIA retains predictive/causal intelligence ownership;
* Kellogg remains an intelligence/tensor substrate consumed by PYTHIA/TOE;
* TURING retains post-classical quantum computation ownership;
* Salamander retains healing/optimisation ownership;
* AL HARAS retains security/governance ownership;
* THESEUS owns durable custody; OVID owns transform/lineage.

Local journals and caches may still exist inside subsystems. On this production
path they are subordinate working state: shared durable identities and lineage
are committed through the one enterprise fabric.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .lifecycle import CompositionRoot
from .system_relations import ProductionSystemRelations


class ProductionOrganism:
    """One governed startup/shutdown boundary for the shared system graph."""

    def __init__(
        self,
        root: str | Path,
        *,
        hmac_key: bytes,
        creator_id: str = "pythia-operator",
        guardian: Any,
        tenant: str = "default",
        allow_insecure_dev_key: bool = False,
        intelligence: Any | None = None,
        euclid_runtime: Any | None = None,
    ) -> None:
        if guardian is None:
            raise ValueError("production organism requires an AL HARAS guardian")
        self.root = Path(root)
        self.creator_id = str(creator_id)
        self.guardian_input = guardian
        self._intelligence_input = intelligence
        self._euclid_input = euclid_runtime
        self.lifecycle = CompositionRoot(
            self.root / "theseus-ovid",
            tenant=tenant,
            hmac_key=hmac_key,
            allow_insecure_dev_key=allow_insecure_dev_key,
        )
        self.relations: ProductionSystemRelations | None = None
        self.intelligence: Any | None = None
        self.pythia: Any | None = None
        self.toe: Any | None = None
        self.kellogg: Any | None = None
        self.turing: Any | None = None
        self.salamander: Any | None = None
        self.al_haras: Any | None = None
        self.euclid: Any | None = None
        self._started = False

    def start(self) -> "ProductionOrganism":
        if self._started:
            return self
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            self.lifecycle.start()
            relations = ProductionSystemRelations(self.lifecycle)

            if self._intelligence_input is None:
                from Intelligence.orchestrator import IntelligenceOrchestrator

                intelligence = IntelligenceOrchestrator(
                    store_dir=self.root / "pythia-local-cache"
                )
            else:
                intelligence = self._intelligence_input
            self.intelligence = relations.bind_intelligence(intelligence)
            self.pythia = self.intelligence
            self.toe = self.intelligence.toe
            self.salamander = self.intelligence.salamander

            self.al_haras = relations.bind_al_haras(self.guardian_input)
            self.kellogg = relations.kellogg()
            self.turing = relations.turing()

            if self._euclid_input is None:
                from euclid import EuclidRuntime

                euclid_runtime = EuclidRuntime.production(
                    creator_id=self.creator_id,
                    state_dir=self.root / "euclid",
                    pythia=self.intelligence.pythia,
                    memory=self.intelligence.memory,
                    store=self.intelligence.store,
                    guardian=self.al_haras,
                )
            else:
                euclid_runtime = self._euclid_input
            self.euclid = relations.bind_euclid(euclid_runtime)
            self.relations = relations
            self._started = True
            return self
        except Exception:
            self._fail_closed_cleanup()
            raise

    def _close_euclid(self) -> None:
        runtime = self.euclid
        if runtime is None:
            return
        raw = getattr(runtime, "raw", runtime)
        close = getattr(raw, "close", None)
        if callable(close):
            close()

    def _fail_closed_cleanup(self) -> None:
        try:
            self._close_euclid()
        except Exception:
            # Startup cleanup is best-effort because the original startup
            # exception is the primary evidence. THESEUS still must close.
            pass
        try:
            self.lifecycle.stop()
        finally:
            self._started = False

    def stop(self) -> None:
        """Persist final state and close every layer even when one step fails.

        Shutdown is fail-closed, not fail-short. A final PYTHIA snapshot or
        EUCLID close failure is surfaced to the caller, but it must never leave
        the shared THESEUS/OVID custody root open merely because an earlier
        cleanup step raised.
        """
        if not self._started:
            self._fail_closed_cleanup()
            return

        first_error: Exception | None = None

        # Persist PYTHIA's final live state through the shared wrapper before
        # EUCLID/consumers close and before THESEUS is sealed.
        try:
            if self.intelligence is not None:
                store = getattr(self.intelligence, "store", None)
                save = getattr(store, "save", None)
                if callable(save):
                    save()
        except Exception as exc:
            first_error = exc

        try:
            self._close_euclid()
        except Exception as exc:
            if first_error is None:
                first_error = exc

        try:
            self.lifecycle.stop()
        except Exception as exc:
            if first_error is None:
                first_error = exc
        finally:
            self._started = False

        if first_error is not None:
            raise first_error

    def status(self) -> dict[str, Any]:
        lifecycle = self.lifecycle.readiness()
        bound = {
            "pythia": self.pythia is not None,
            "toe": self.toe is not None,
            "kellogg": self.kellogg is not None,
            "turing": self.turing is not None,
            "salamander": self.salamander is not None,
            "al_haras": self.al_haras is not None,
            "euclid": self.euclid is not None,
            "chronus": bool(
                self.euclid is not None
                and "chronus" in {
                    item.get("organ_id")
                    for item in getattr(
                        getattr(self.euclid, "raw", self.euclid), "registry", ()
                    ).report()
                }
            )
            if self.euclid is not None
            else False,
        }
        ready = bool(self._started and lifecycle.get("ready") and all(bound.values()))
        return {
            "schema": "aethel.production-organism/1",
            "ready": ready,
            "shared_custody_ready": bool(lifecycle.get("ready")),
            "bound_systems": bound,
            "authority_preserved": True,
            "custody_owner": "theseus",
            "transform_lineage_owner": "ovid",
            "relations": self.relations.status() if self.relations is not None else None,
        }

    def __enter__(self) -> "ProductionOrganism":
        return self.start()

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.stop()


__all__ = ["ProductionOrganism"]
