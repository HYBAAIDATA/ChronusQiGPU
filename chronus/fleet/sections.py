"""Tenant/version-scoped local sections and exact overlap gluing.

A section maps a finite execution-domain location to an authoritative custody
content reference. Gluing validates complete coverage and every overlap before
an admitted OVID manifest mutation; THESEUS may index the resulting manifest.
"""

from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType


@dataclass(frozen=True)
class Section:
    tenant: str
    version: int
    entries: dict[str, str]

    def __post_init__(self):
        if (
            not isinstance(self.tenant, str)
            or not self.tenant
            or type(self.version) is not int
            or self.version < 0
        ):
            raise ValueError("section requires tenant and nonnegative version")
        if not isinstance(self.entries, dict) or len(self.entries) > 65536:
            raise ValueError("section entries exceed bound")
        if any(
            not isinstance(k, str)
            or not k
            or not isinstance(v, str)
            or len(v) != 64
            or any(c not in "0123456789abcdef" for c in v)
            for k, v in self.entries.items()
        ):
            raise ValueError("sections require named locations and SHA256 content references")
        object.__setattr__(self, "entries", MappingProxyType(dict(self.entries)))

    def restrict(self, locations):
        selected = set(locations)
        if not selected <= self.entries.keys():
            raise ValueError("restriction exceeds section domain")
        return Section(self.tenant, self.version, {k: self.entries[k] for k in sorted(selected)})


def glue(sections, domain):
    sections = tuple(sections)
    if not sections:
        raise ValueError("at least one section required")
    first = sections[0]
    entries = {}
    for section in sections:
        if (section.tenant, section.version) != (first.tenant, first.version):
            raise ValueError("tenant or version mismatch across sections")
        for location, reference in section.entries.items():
            if location in entries and entries[location] != reference:
                raise ValueError("overlap conflict")
            entries[location] = reference
    if set(entries) != set(domain):
        raise ValueError("sections must cover exactly the declared execution domain")
    return Section(first.tenant, first.version, entries)


@dataclass(frozen=True)
class TenantSectionCustody:
    memory: object
    tenant: str

    def put(self, payload):
        return self.memory.store(payload, tenant=self.tenant).object_id

    def get(self, reference):
        return self.memory.retrieve(reference, tenant=self.tenant)


def commit_sections(
    sections, domain, *, custody, controller, grant, resources, capacity, workload_id, now_ms=None
):
    section = glue(sections, domain)
    if not isinstance(custody, TenantSectionCustody) or custody.tenant != section.tenant:
        raise PermissionError("section custody must be bound to the admitted tenant")
    if section.tenant != resources.tenant_id or section.version != controller.state_version:
        raise ValueError("section does not bind current tenant/version")
    payload = json.dumps(
        {
            "schema": "chronus.global-section/v1",
            "tenant": section.tenant,
            "version": section.version,
            "entries": dict(section.entries),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()

    def mutation():
        # Reads enforce authoritative existence before committing a manifest.
        for ref in set(section.entries.values()):
            custody.get(ref)
        reference = custody.put(payload)
        return {"reference": reference, "payload_sha256": hashlib.sha256(payload).hexdigest()}

    return controller.admit_and_execute(
        grant=grant,
        resource_vector=resources,
        capacity=capacity,
        workload_id=workload_id,
        owner_authority="OVID",
        expected_version=section.version,
        mutation_fn=mutation,
        postcondition_fn=lambda result: custody.get(result["reference"]) == payload,
        now_ms=now_ms,
    )
