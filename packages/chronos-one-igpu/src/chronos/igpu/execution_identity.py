"""Plan-authorised implementation selection and independently replayable identity."""

from __future__ import annotations

import hashlib
import ast
import importlib
import inspect
import json
from functools import _lru_cache_wrapper
from pathlib import Path
from types import CodeType

from ..adapters.base import BackendAbsent, DispatchError

ALGORITHM = "hendrix_coprime_stride"
SCHEMA = "pythia.execution_implementation/1"
_ROOT = __package__.rsplit(".igpu", 1)[0]
_COMPONENTS = (
    ("resident_hendrix", "ResidentHendrix.batch"),
    ("resident_hendrix", "ResidentHendrix.validate"),
    ("exact_geometry", "validate_payload"),
    ("exact_geometry", "exact_walk_reference"),
    ("hendrix_execution", "execute_hendrix"),
    ("hendrix_execution", "execute_nonce_batch"),
    ("asic_mining", "PreparedSHA256d.scan_nonce_batch"),
    ("facade", "OneIGPU.execute_hendrix"),
    ("execution_identity", "verify_contract"),
    ("execution_identity", "verify_receipt"),
)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _code_value(value):
    if isinstance(value, CodeType):
        return {
            "bytecode": value.co_code.hex(),
            "constants": [_code_value(x) for x in value.co_consts],
            "names": value.co_names,
            "locals": value.co_varnames,
            "freevars": value.co_freevars,
            "cellvars": value.co_cellvars,
            "argcount": value.co_argcount,
            "kwonlyargcount": value.co_kwonlyargcount,
            "posonlyargcount": value.co_posonlyargcount,
            "flags": value.co_flags,
            "exceptiontable": getattr(value, "co_exceptiontable", b"").hex(),
        }
    if isinstance(value, bytes):
        return {"bytes": value.hex()}
    if isinstance(value, tuple):
        return [_code_value(x) for x in value]
    if isinstance(value, float):
        return {"float_literal": value.hex()}
    if isinstance(value, frozenset):
        return sorted((_code_value(x) for x in value), key=_canonical)
    if value is Ellipsis:
        return {"constant": "ellipsis"}
    if value is None or isinstance(value, (bool, int, str)):
        return value
    raise DispatchError("unsupported implementation code constant")


def _source_code(module, symbol):
    tree = compile(
        Path(module.__file__).read_text(),
        "<implementation>",
        "exec",
        dont_inherit=True,
        optimize=0,
    )
    for name in symbol.split("."):
        matches = [
            x for x in tree.co_consts if isinstance(x, CodeType) and x.co_name == name
        ]
        if len(matches) != 1:
            raise DispatchError("implementation symbol is not uniquely source-defined")
        tree = matches[0]
    return tree


def _implementation_identity(short_module, symbol):
    module = importlib.import_module(_ROOT + ".igpu." + short_module)
    function = module
    for part in symbol.split("."):
        function = getattr(function, part)
    function = getattr(function, "__func__", function)
    if type(function) is _lru_cache_wrapper:
        function = function.__wrapped__
    try:
        expected = _source_code(module, symbol)
    except DispatchError:
        # Preserve recovered class methods attached from module-level kernels.
        tree = ast.parse(Path(module.__file__).read_text())
        targets = [
            n.value.id
            for n in ast.walk(tree)
            if isinstance(n, ast.Assign)
            and isinstance(n.value, ast.Name)
            and any(
                isinstance(t, ast.Attribute) and ast.unparse(t) == symbol
                for t in n.targets
            )
        ]
        if len(targets) != 1:
            raise
        expected = _source_code(module, targets[0])
    if not inspect.isfunction(function) or _code_value(
        function.__code__
    ) != _code_value(expected):
        raise DispatchError("live implementation substituted: " + symbol)
    return {
        "module": module.__name__,
        "symbol": symbol,
        "source_digest": hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),
        "code_digest": _digest(_code_value(expected)),
    }


def implementation_manifest():
    components = [_implementation_identity(m, f) for m, f in _COMPONENTS]
    return {"components": components, "digest": _digest(components)}


def issue_contract(
    *, execution_mode="resident_software", device=None, allowed_fallbacks=()
):
    """PYTHIA calls this before sealing; Chronus cannot add alternatives."""
    if execution_mode not in ("resident_software", "resident_opencl"):
        raise BackendAbsent("requested resident execution capability UNAVAILABLE")
    if allowed_fallbacks:
        raise ValueError("use an explicit sealed fallback contract, not a string label")
    manifest = implementation_manifest()
    if execution_mode == "resident_software":
        from .asic_mining import PreparedSHA256d

        adapter = PreparedSHA256d()
        capability = adapter.capability()
        substrate = {"kind": "cpu", "sha256d_backend": capability["backend"]}
        native = adapter.native
        if native is not None:
            for name in (
                "prepare",
                "rebind",
                "hash_batch",
                "scan_batch",
                "scan_range",
                "implementation",
            ):
                function = getattr(native, name, None)
                if (
                    not inspect.isbuiltin(function)
                    or function.__name__ != name
                    or function.__module__ != native.__name__
                ):
                    raise DispatchError(
                        "native SHA256d entry point was replaced: " + name
                    )
        backend_digest = (
            hashlib.sha256(Path(native.__file__).read_bytes()).hexdigest()
            if native is not None
            else None
        )
    else:
        if not isinstance(device, dict) or device.get("physical") is not True:
            raise BackendAbsent("explicit probed physical OpenCL capability required")
        if device.get("backend") != "opencl":
            raise BackendAbsent(
                "requested device is not the registered OpenCL implementation"
            )
        substrate = {
            "kind": "opencl",
            "device_id": device["device_id"],
            "sha256d_backend": device["backend"],
        }
        native = None
        backend_digest = None
        manifest["device_components"] = [
            _implementation_identity("overlay", "OpenCLOverlay.execute_hendrix_order"),
            _implementation_identity("overlay", "OpenCLOverlay.execute_sha256d"),
        ]
        manifest["device_kernel_digest"] = hashlib.sha256(
            (Path(__file__).parent / "kernels/hendrix600.cl").read_bytes()
        ).hexdigest()
        manifest["digest"] = _digest(
            {k: v for k, v in manifest.items() if k != "digest"}
        )
    return {
        "schema": SCHEMA,
        "requested_algorithm": ALGORITHM,
        "planned_algorithm": ALGORITHM,
        "implementation_module": _ROOT + ".igpu.hendrix_execution",
        "implementation_digest": manifest["digest"],
        "implementation_manifest": manifest,
        "execution_mode": execution_mode,
        "substrate": substrate,
        "native_sha256d_digest": backend_digest,
        "allowed_fallbacks": [],
    }


def authorise_fallback(primary, *, name, replacement):
    """An explicit PYTHIA operation, never called by execution or recovery."""
    if (
        name != "resident_software_same_hendrix"
        or replacement["execution_mode"] != "resident_software"
    ):
        raise ValueError(
            "only named exact same-Hendrix software replacement is registered"
        )
    if replacement.get("allowed_fallbacks"):
        raise ValueError("recursive fallback contracts are forbidden")
    if primary.get("allowed_fallbacks"):
        raise ValueError("only one bounded explicit alternative is supported")
    value = json.loads(_canonical(primary))
    value["allowed_fallbacks"] = [{"name": name, "contract": replacement}]
    return value


def _verify_one(contract, igpu=None, *, replay=False):
    if contract.get("schema") != SCHEMA:
        raise DispatchError("missing PYTHIA implementation authority")
    if (
        contract["requested_algorithm"] != ALGORITHM
        or contract["planned_algorithm"] != ALGORITHM
    ):
        raise DispatchError("algorithm identity substitution")
    mode = contract["execution_mode"]
    if mode == "resident_software":
        current = issue_contract()
    elif mode == "resident_opencl":
        overlay = None if igpu is None else igpu.fabric.overlay
        if overlay is None and replay:
            declared = contract["substrate"]
            current = issue_contract(
                execution_mode=mode,
                device={
                    "physical": True,
                    "backend": "opencl",
                    "device_id": declared["device_id"],
                },
            )
            for key in current:
                if key != "allowed_fallbacks" and contract.get(key) != current[key]:
                    raise DispatchError(
                        "archived device implementation identity changed: " + key
                    )
            return contract
        if overlay is None:
            raise BackendAbsent("authorised physical OpenCL executor is not bound")
        from .overlay import OpenCLOverlay

        if type(overlay) is not OpenCLOverlay:
            raise DispatchError("unregistered device implementation substituted")
        current = issue_contract(execution_mode=mode, device=overlay.capability())
    else:
        raise DispatchError("unregistered execution mode")
    for key in current:
        if key != "allowed_fallbacks" and contract.get(key) != current[key]:
            raise DispatchError("authorised implementation identity changed: " + key)
    return contract


def verify_contract(contract, igpu=None):
    """Return the selected authorised contract; never invent a fallback."""
    try:
        return _verify_one(contract, igpu), None
    except BackendAbsent as exc:
        alternatives = contract.get("allowed_fallbacks", [])
        if len(alternatives) != 1:
            raise
        alternative = alternatives[0]
        if alternative["name"] != "resident_software_same_hendrix":
            raise DispatchError("unregistered fallback name")
        replacement = alternative["contract"]
        if replacement.get("allowed_fallbacks"):
            raise DispatchError("recursive fallback contract")
        _verify_one(replacement, igpu)
        return replacement, str(exc)


def receipt_identity(contract, *, fallback_reason=None):
    return {
        "requested_algorithm": contract["requested_algorithm"],
        "planned_algorithm": contract["planned_algorithm"],
        "executed_algorithm": ALGORITHM,
        "implementation_module": contract["implementation_module"],
        "implementation_digest": contract["implementation_digest"],
        "execution_mode": contract["execution_mode"],
        "substrate": contract["substrate"],
        "fallback_used": fallback_reason is not None,
        "fallback_reason": fallback_reason,
    }


def verify_receipt(receipt, artifact, *, igpu=None):
    """Replay implementation, plan, geometry, ordering and actual candidate hash."""
    from .resident_hendrix import ResidentHendrix, seal

    plan = ResidentHendrix.from_dict(artifact)
    body = dict(receipt)
    digest = body.pop("receipt_digest", None)
    if digest != seal(body):
        raise DispatchError("execution receipt seal changed")
    primary = artifact["execution_contract"]
    if receipt["fallback_used"]:
        choices = primary.get("allowed_fallbacks", [])
        if len(choices) != 1 or choices[0]["name"] != "resident_software_same_hendrix":
            raise DispatchError("receipt fallback was not authorised")
        selected = choices[0]["contract"]
        if (
            not isinstance(receipt["fallback_reason"], str)
            or not receipt["fallback_reason"]
        ):
            raise DispatchError("fallback requires a recorded cause")
    else:
        selected = primary
    _verify_one(selected, igpu, replay=True)
    identity = receipt_identity(selected, fallback_reason=receipt["fallback_reason"])
    for key, expected in identity.items():
        if receipt.get(key) != expected:
            raise DispatchError("execution identity replay failed: " + key)
    if (
        receipt["plan_digest"] != artifact["plan_digest"]
        or receipt["resident_execution_digest"] != plan.digest
    ):
        raise DispatchError("receipt changed plan semantics")
    if receipt["geometry_digest"] != artifact["geometry"]["digest"]:
        raise DispatchError("receipt changed exact certificate")
    prefix = bytes.fromhex(receipt["header_prefix_hex"])
    target = bytes.fromhex(receipt["target_hex"])
    if (
        len(prefix) != 76
        or hashlib.sha256(prefix).hexdigest() != artifact["header_digest"]
    ):
        raise DispatchError("receipt header changed")
    if target.hex() != artifact["target_hex"]:
        raise DispatchError("receipt target changed")
    position, count = receipt["position"], receipt["requested_candidates"]
    values, _ = plan.batch(position, count)
    if (
        receipt["order_digest"]
        != hashlib.sha256(values.astype("<u4").tobytes()).hexdigest()
    ):
        raise DispatchError("receipt changed authorised ordering")
    checked = receipt["sha256d_evaluations"]
    if type(checked) is not int or not 0 <= checked <= count:
        raise DispatchError("receipt claims work outside its budget")
    if receipt["iterations_work_performed"] != {
        "positions_requested": count,
        "sha256d": checked,
        "verification_sha256d": receipt["verification_sha256d_evaluations"],
    }:
        raise DispatchError("receipt work identity changed")
    nonce = receipt["nonce"]
    if nonce is None:
        if (
            checked != count
            or receipt["digest"] is not None
            or receipt["host_verified"]
        ):
            raise DispatchError("receipt has an inconsistent negative result")
    else:
        if type(nonce) is not int or nonce not in values[:checked]:
            raise DispatchError("receipt candidate escaped authorised order")
        actual = hashlib.sha256(
            hashlib.sha256(prefix + nonce.to_bytes(4, "little")).digest()
        ).digest()
        if actual.hex() != receipt["digest"] or int.from_bytes(
            actual, "little"
        ) > int.from_bytes(target, "big"):
            raise DispatchError("independent consensus verification failed")
        if (
            receipt["host_verified"] is not True
            or receipt["verification_sha256d_evaluations"] < 1
        ):
            raise DispatchError("receipt lacks actual candidate verification")
    return True
