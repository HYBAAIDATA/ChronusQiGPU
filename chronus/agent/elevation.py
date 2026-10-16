"""Qualification service entry point, explicitly outside ordinary task execution."""

from .qualification_loop import QualificationService


def elevate(service, trigger, report, attestation, goodhart, *, now, expires_at):
    if not isinstance(service, QualificationService):
        raise TypeError("host qualification service required")
    return service.qualify(trigger, report, attestation, goodhart, now=now, expires_at=expires_at)
