"""Checks for the AL HARAS sovereign runner files in infra/runners/al-haras.

Standard library only (no fastapi). Nothing here loads BPF programs, touches
/sys or starts systemd units. The tests:

* run ``bash -n`` on every script;
* check that the README documents every file, install path, script path and
  environment variable that the unit and the scripts use, and that the unit
  runs the privileged steps with the ``+`` prefix instead of
  ``PermissionsStartOnly=``;
* run the scripts' own functions against fixture files and a stub
  ``bpftool``: the bootstrap's attestation must be accepted by the job-started
  hook, and tampered inputs (wrong invocation, unattached program, hash
  mismatch, missing link, ...) must be rejected. Two mutation tests show that
  removing a check makes the corresponding case pass, i.e. the cases detect
  regressions.

Every check here is local. Behaviour on a real host (kernel, bpftool, systemd,
actions runner) is not covered.

The scripts are Linux/systemd units: they are owned by ``github-runner``, read
``/proc`` and ``/sys``, and assert POSIX owner and mode bits (``stat -c '%u %a'``).
Those semantics do not exist on Windows, so the whole module is skipped there
rather than reported as a failure. The pure-text checks (README layout, unit
file contents, environment variables) are portable and run everywhere.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.real

REPO = Path(__file__).resolve().parents[1]
RUNNER = REPO / "infra" / "runners" / "al-haras"
UNIT = RUNNER / "chronus-sovereign-runner.service"
README = RUNNER / "README.md"
BOOTSTRAP = RUNNER / "al-haras-bootstrap.sh"
TEARDOWN = RUNNER / "al-haras-teardown.sh"
REGISTER = RUNNER / "register-ephemeral.sh"
PRE_JOB = RUNNER / "hooks" / "pre-job-attest.sh"
POST_JOB = RUNNER / "hooks" / "post-job-scrub.sh"
SCRIPTS = [BOOTSTRAP, TEARDOWN, REGISTER, PRE_JOB, POST_JOB]

BASH = shutil.which("bash")
needs_bash = pytest.mark.skipif(BASH is None, reason="bash is not installed")

# The runner scripts are Linux units run by systemd as root and as
# "github-runner". Exercising them needs POSIX owner and mode bits: os.getuid,
# chmod(2) that the filesystem honours, and "stat -c '%u %a'". A Windows host
# has none of these (Git for Windows bash reports a synthetic uid and ignores
# chmod), so running the scripts there would report a platform mismatch as a
# product defect. These checks are therefore POSIX-only; the portable text
# checks below stay enabled everywhere.
POSIX_ONLY = os.name == "posix"
needs_posix = pytest.mark.skipif(
    not POSIX_ONLY, reason="AL HARAS runner scripts require POSIX owner and mode semantics"
)

INVOCATION = "0123456789abcdef0123456789abcdef"
BOOT_ID = "8a1b6c3e-1111-4c4c-9d9d-0123456789ab"
KERNEL = "6.8.0-al-haras-test"
LSM_LIST = "lockdown,capability,landlock,yama,apparmor,bpf"

# Fixture objects for the stub bpftool: one "prog <name> <tag> <mode>" per line.
# mode: link (attached lsm_mac link), unattached (bare program pin, what bpftool
# does when auto-attach is impossible), kprobe (link with another attach type),
# wrongtype (lsm_mac link whose program type is not lsm).
OBJECTS = {
    "fs_guard.o": [("restrict_mount", "0123456789abcdef", "link"), ("restrict_ptrace", "fedcba9876543210", "link")],
    "net_guard.o": [("restrict_socket", "00112233445566ff", "link")],
}

STUB_BPFTOOL = r"""#!/usr/bin/env bash
# Stub for the bpftool subcommands the AL HARAS scripts call.
set -euo pipefail
state=${STUB_BPFTOOL_STATE:?}
mkdir -p "$state/link" "$state/prog"
# Deterministic ids derived from the pin path (no counter file to rewrite).
id_for() {
  local s=$1 h=7 i c
  for ((i = 0; i < ${#s}; i++)); do
    printf -v c '%d' "'${s:i:1}"
    h=$(( (h * 31 + c) % 1000000007 ))
  done
  echo $((h + 1))
}
if [[ ${1:-} == -j ]]; then shift; fi
case "${1:-} ${2:-}" in
  "prog help")
    echo "Usage: bpftool prog { load | loadall } OBJ PATH [type TYPE] [pinmaps MAP_DIR] [autoattach]" >&2
    exit 0 ;;
  version*)
    echo "bpftool v7.4.0 (stub)"
    exit 0 ;;
  "prog loadall")
    obj=$3 dir=$4
    [[ ${5:-} == autoattach ]] || { echo "stub: autoattach expected" >&2; exit 2; }
    mkdir -p "$dir"
    while read -r kind name tag mode; do
      [[ $kind == prog ]] || continue
      pid=$(id_for "prog:$dir/$name")
      ptype=lsm attach=lsm_mac
      [[ $mode == kprobe ]] && attach=kprobe_multi
      [[ $mode == wrongtype ]] && ptype=tracing
      printf '%s %s %s\n' "$name" "$tag" "$ptype" > "$state/prog/$pid"
      if [[ $mode == unattached ]]; then
        printf 'prog %s\n' "$pid" > "$dir/$name"
      else
        lid=$(id_for "link:$dir/$name")
        printf '%s %s\n' "$pid" "$attach" > "$state/link/$lid"
        printf 'link %s\n' "$lid" > "$dir/$name"
      fi
    done < "$obj"
    exit 0 ;;
  "link show")
    if [[ ${3:-} == pinned ]]; then
      read -r kind id < "$4"
      [[ $kind == link ]] || { echo "Error: incorrect object type: prog" >&2; exit 255; }
    else
      id=$4
    fi
    [[ -f $state/link/$id ]] || { echo "Error: get by id ($id): No such file or directory" >&2; exit 255; }
    read -r pid attach < "$state/link/$id"
    printf '{"id":%s,"type":"tracing","prog_id":%s,"prog_type":"lsm","attach_type":"%s","target_obj_id":1,"target_btf_id":4242}\n' "$id" "$pid" "$attach"
    exit 0 ;;
  "prog show")
    id=$4
    [[ -f $state/prog/$id ]] || { echo "Error: get by id ($id): No such file or directory" >&2; exit 255; }
    read -r name tag ptype < "$state/prog/$id"
    printf '{"id":%s,"type":"%s","name":"%s","tag":"%s","gpl_compatible":true,"uid":0}\n' "$id" "$ptype" "${name:0:15}" "$tag"
    exit 0 ;;
esac
echo "stub bpftool: unsupported arguments: $*" >&2
exit 64
"""

# The stub is run through a shell function, which takes precedence over PATH
# and does not need an executable bit (some synced filesystems drop it).
STUB_FUNCTION = 'bpftool() { bash "$STUB_BPFTOOL" "$@"; }\n'

BOOTSTRAP_DRIVER = STUB_FUNCTION + r"""
set -euo pipefail
source "$1"
lsm_dir=$2 stage=$3 pin_dir=$4 att=$5 owner=$6
read_manifest "$lsm_dir/manifest.sha256"
stage_and_verify_objects "$lsm_dir" "$stage" "$owner"
load_and_collect "$stage" "$pin_dir"
write_attestation "$att" "$7" "$8" "$9" "${10}" 1 "bpftool v7.4.0 (stub)" "$lsm_dir/manifest.sha256" "$pin_dir"
"""

HOOK_DRIVER = r"""
set -euo pipefail
source "$1"
verify_attestation "$2" "$3" "$4" "$5" "$6" "$7" "$8" "$9"
write_receipt "${10}"
"""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_file(path: Path, text: str, mode: int = 0o644) -> Path:
    """Write a new file and rename it over PATH (never rewrite in place)."""
    tmp = path.with_name(path.name + ".new")
    tmp.write_text(text)
    os.chmod(tmp, mode)
    os.replace(tmp, path)
    return path


def run_bash(script: str, *args: object, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [BASH, "-c", script, "bash", *[str(a) for a in args]],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


def chmod_supported(directory: Path) -> bool:
    """Some synced or network filesystems ignore chmod."""
    probe = directory / ".chmod-probe"
    probe.write_text("x")
    try:
        os.chmod(probe, 0o600)
        return probe.stat().st_mode & 0o777 == 0o600
    finally:
        probe.unlink()


def symlinks_supported(directory: Path) -> bool:
    """Some synced or network filesystems refuse symlinks."""
    link = directory / ".symlink-probe"
    try:
        os.symlink(directory, link)
    except OSError:
        return False
    link.unlink()
    return True


class Host:
    """Fixture layout standing in for the root-owned paths on a runner host."""

    def __init__(self, base: Path, objects: dict | None = None):
        self.base = base
        self.uid = os.getuid()
        self.lsm_dir = base / "opt" / "al-haras" / "lsm"
        self.stage = base / "run" / "al-haras" / "stage"
        self.run_dir = base / "run" / "al-haras"
        self.attestation = self.run_dir / "attestation"
        self.pin_dir = base / "bpffs" / "al_haras" / INVOCATION
        self.receipt = base / "work" / "_al_haras" / "pre-flight-receipt.json"
        self.state = base / "bpftool-state"
        for d in (self.lsm_dir, self.stage, self.state, self.pin_dir.parent):
            d.mkdir(parents=True, exist_ok=True)
        for d in (base / "opt", base / "opt" / "al-haras", self.lsm_dir, base / "run", self.run_dir):
            os.chmod(d, 0o755)
        os.chmod(self.stage, 0o700)
        objects = OBJECTS if objects is None else objects
        for name, progs in objects.items():
            self.write_object(name, progs)
        self.write_manifest(list(objects))
        stub = replace_file(base / "bpftool-stub.sh", STUB_BPFTOOL)
        self.env = {
            "PATH": f"{os.environ.get('PATH', '')}{os.pathsep}/usr/bin{os.pathsep}/bin",
            "STUB_BPFTOOL": str(stub),
            "LC_ALL": "C",
            "TMPDIR": str(base),
            "STUB_BPFTOOL_STATE": str(self.state),
            "GITHUB_REPOSITORY": "hybadatadevops1/Chronusv2",
            "GITHUB_RUN_ID": "4242",
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_JOB": "qualify",
            "GITHUB_SHA": "a" * 40,
            "GITHUB_WORKFLOW_REF": 'hybadatadevops1/Chronusv2/.github/workflows/q.yml@refs/heads/"main"',
            "RUNNER_NAME": "sovereign-test-1",
        }

    def write_object(self, name: str, progs: list) -> None:
        replace_file(self.lsm_dir / name, "".join(f"prog {p} {tag} {mode}\n" for p, tag, mode in progs))

    def write_manifest(self, names: list, override: dict | None = None) -> Path:
        override = override or {}
        lines = [f"{override.get(n, sha256_file(self.lsm_dir / n))}  {n}\n" for n in names]
        return replace_file(self.lsm_dir / "manifest.sha256", "".join(lines))

    @property
    def manifest(self) -> Path:
        return self.lsm_dir / "manifest.sha256"

    def bootstrap(self) -> subprocess.CompletedProcess:
        return run_bash(
            BOOTSTRAP_DRIVER, BOOTSTRAP, self.lsm_dir, self.stage, self.pin_dir, self.attestation,
            self.uid, INVOCATION, BOOT_ID, KERNEL, LSM_LIST, env=self.env,
        )

    def hook(self, invocation=INVOCATION, boot=BOOT_ID, kernel=KERNEL, lsm=LSM_LIST, unpriv="1", owner=None):
        return run_bash(
            HOOK_DRIVER, PRE_JOB, self.attestation, self.manifest, self.uid if owner is None else owner,
            invocation, boot, kernel, lsm, unpriv, self.receipt, env=self.env,
        )


def attested_host(tmp_path: Path) -> Host:
    host = Host(tmp_path)
    result = host.bootstrap()
    assert result.returncode == 0, result.stderr
    return host


# --------------------------------------------------------------------------
# Static checks
# --------------------------------------------------------------------------


@needs_bash
def test_every_script_parses_with_bash_n():
    for script in SCRIPTS:
        result = subprocess.run([BASH, "-n", str(script)], capture_output=True, text=True)
        assert result.returncode == 0, f"{script.name}: {result.stderr}"


def _unit_entries() -> list[tuple[str, str]]:
    entries = []
    for raw in UNIT.read_text().splitlines():
        line = raw.strip()
        if line and not line.startswith(("#", "[")):
            key, _, value = line.partition("=")
            entries.append((key, value))
    return entries


def test_unit_runs_privileged_steps_with_plus_prefix_and_sandboxes_the_runner():
    text = UNIT.read_text()
    entries = _unit_entries()
    values = {}
    for key, value in entries:
        values.setdefault(key, []).append(value)
    assert "PermissionsStartOnly" not in text
    assert values["ExecStartPre"] == [
        "+/usr/local/sbin/al-haras-bootstrap.sh",
        "+/usr/local/libexec/al-haras/register-ephemeral.sh",
    ]
    assert values["ExecStart"] == ["/opt/actions-runner/run.sh"]
    assert values["ExecStopPost"] == ["+/usr/local/sbin/al-haras-teardown.sh"]
    assert values["User"] == ["github-runner"]
    # The runner hands its environment to every job step: no secrets in it.
    assert "EnvironmentFile" not in values
    assert not any("TOKEN" in v for v in values.get("Environment", []))
    for key, expected in {
        "NoNewPrivileges": "true",
        "PrivateTmp": "true",
        "RemoveIPC": "true",
        "ProtectSystem": "strict",
        "ProtectKernelTunables": "true",
        "ProtectKernelModules": "true",
        "KillMode": "control-group",
        "ReadWritePaths": "/opt/actions-runner",
    }.items():
        assert values.get(key) == [expected], key


def _readme_layout() -> dict[str, str]:
    rows = re.findall(r"^\| `([^`]+)` \| `(/[^`]*/)` \|", README.read_text(), flags=re.MULTILINE)
    return {source: target + Path(source).name for source, target in rows}


def test_readme_layout_lists_every_file_and_matches_the_unit():
    layout = _readme_layout()
    shipped = {
        str(p.relative_to(RUNNER)) for p in RUNNER.rglob("*") if p.is_file() and p.name != "README.md"
    }
    assert set(layout) == shipped
    readme = README.read_text()
    install_block = readme.split("## Install", 1)[1].split("## Configuration", 1)[0]
    for source, installed in layout.items():
        install_lines = [line for line in install_block.splitlines() if source in line.split()]
        assert install_lines, f"no install command for {source}"
        assert any(str(Path(installed).parent) in line for line in install_lines), source
    installed_paths = set(layout.values())
    used_by_unit = []
    for key, value in _unit_entries():
        if key.startswith("Exec"):
            used_by_unit.append(value.lstrip("+-@:!").split()[0])
        if key == "Environment" and value.startswith("ACTIONS_RUNNER_HOOK_"):
            used_by_unit.append(value.split("=", 1)[1])
    for path in used_by_unit:
        if path == "/opt/actions-runner/run.sh":
            continue  # from the runner release, copied by the bootstrap
        assert path in installed_paths, f"unit uses {path}, which the README does not install"
    assert "/etc/systemd/system/chronus-sovereign-runner.service" in installed_paths


def test_readme_documents_every_path_constant_of_the_scripts():
    readme = README.read_text()
    for script in SCRIPTS:
        for name, value in re.findall(r"^readonly ([A-Z_]+)=(/\S+)$", script.read_text(), flags=re.MULTILINE):
            assert value in readme, f"{script.name}: {name}={value} is not documented in the README"


_SHELL_NAMES = {"BASH_SOURCE", "BASH_REMATCH", "EUID", "PATH", "LC_ALL", "LANG", "HOME", "USER", "LOGNAME"}


def _external_variables(script: Path) -> set[str]:
    text = script.read_text()
    referenced = set(re.findall(r"\$\{?([A-Z][A-Z0-9_]*)", text))
    assigned = set(re.findall(r"(?:^|[\s;(])(?:readonly |local |export |declare -A )?([A-Z][A-Z0-9_]*)=", text, flags=re.MULTILINE))
    return referenced - assigned - _SHELL_NAMES


def test_every_environment_variable_is_documented():
    readme = README.read_text()
    documented = set(re.findall(r"`([A-Z][A-Z0-9_]+)`", readme))
    needed = set()
    for script in SCRIPTS:
        needed |= _external_variables(script)
    needed |= set(re.search(r'^readonly ENV_KEYS="([^"]+)"', REGISTER.read_text(), flags=re.MULTILINE).group(1).split())
    for key, value in _unit_entries():
        if key == "Environment":
            needed.add(value.split("=", 1)[0])
    missing = sorted(needed - documented)
    assert not missing, f"undocumented variables: {missing}"
    # Variables that older revisions named but nothing reads must not come back.
    for script in SCRIPTS:
        assert "RUNNER_CFG_PAT" not in script.read_text()
        assert "RUNNER_REMOVE_TOKEN" not in script.read_text()


def test_readme_template_matches_hook_paths_and_receipt_format():
    readme = README.read_text()
    hook = PRE_JOB.read_text()
    receipt = re.search(r"^readonly RECEIPT=(\S+)$", hook, flags=re.MULTILINE).group(1)
    attestation = re.search(r"^readonly ATTESTATION=(\S+)$", hook, flags=re.MULTILINE).group(1)
    template = readme.split("## Using the sovereign pool from a workflow", 1)[1]
    assert f"receipt={receipt}" in template
    assert f"sha256sum {attestation}" in template
    assert template.count(receipt) == 2 and attestation in template.split("subject-path:", 1)[1]
    assert "\\\"attestation_sha256\\\": \\\"${digest}\\\"" in template
    labels = re.search(r"^readonly DEFAULT_LABELS=(\S+)$", REGISTER.read_text(), flags=re.MULTILINE).group(1)
    assert f"runs-on: [self-hosted, {', '.join(labels.split(','))}]" in template


# --------------------------------------------------------------------------
# Bootstrap -> pre-job hook round trip (stub bpftool)
# --------------------------------------------------------------------------


@needs_bash
def test_bootstrap_attestation_is_accepted_and_receipt_carries_digests(tmp_path):
    host = attested_host(tmp_path)
    lines = host.attestation.read_text().splitlines()
    assert f"invocation_id={INVOCATION}" in lines
    assert f"manifest_sha256={sha256_file(host.manifest)}" in lines
    for name in OBJECTS:
        assert f"object={name} {sha256_file(host.lsm_dir / name)}" in lines
    links = [line for line in lines if line.startswith("link=")]
    assert len(links) == sum(len(p) for p in OBJECTS.values())
    assert all(line.endswith(" lsm_mac") for line in links)

    result = host.hook()
    assert result.returncode == 0, result.stdout + result.stderr
    text = host.receipt.read_text()
    receipt = json.loads(text)
    assert receipt["schema"] == "al-haras-pre-flight-receipt/1"
    assert receipt["attestation_sha256"] == sha256_file(host.attestation)
    assert f'"attestation_sha256": "{sha256_file(host.attestation)}"' in text  # README template's grep
    assert receipt["attestation"]["manifest_sha256"] == sha256_file(host.manifest)
    assert {o["name"]: o["sha256"] for o in receipt["objects"]} == {
        name: sha256_file(host.lsm_dir / name) for name in OBJECTS
    }
    expected_links = {(obj, prog, tag) for obj, progs in OBJECTS.items() for prog, tag, _ in progs}
    assert {(l["object"], l["program"], l["prog_tag"]) for l in receipt["lsm_links"]} == expected_links
    assert {l["attach_type"] for l in receipt["lsm_links"]} == {"lsm_mac"}
    stub_links = {p.name: p.read_text().split()[0] for p in (host.state / "link").iterdir()}
    for link in receipt["lsm_links"]:
        assert stub_links[str(link["link_id"])] == str(link["prog_id"])
    assert receipt["observed_at_job_start"]["invocation_id"] == INVOCATION
    assert receipt["observed_at_job_start"]["lsm"] == LSM_LIST
    assert receipt["github"]["run_id"] == "4242"
    assert receipt["github"]["workflow_ref"].endswith('@refs/heads/"main"')  # escaped, still valid JSON


@needs_bash
def test_bootstrap_rejects_object_that_differs_from_manifest(tmp_path):
    host = Host(tmp_path)
    host.write_object("net_guard.o", [("restrict_socket", "00112233445566ff", "link"), ("extra", "1" * 16, "link")])
    result = host.bootstrap()
    assert result.returncode != 0
    assert "does not match the manifest entry" in result.stderr
    assert not host.attestation.exists()
    # Verification happens before anything is loaded.
    assert not (host.state / "prog").exists() or not any((host.state / "prog").iterdir())


@pytest.mark.parametrize(
    "mutate, message",
    [
        ("unlisted", "not listed in the manifest"),
        ("uppercase", "expected '<sha256>  <name>.o'"),
        ("dotted", "expected '<sha256>  <name>.o'"),
        ("duplicate", "duplicate entry"),
        ("empty", "no entries"),
        ("unattached", "not an attached link"),
        ("kprobe", "attach type kprobe_multi, expected lsm_mac"),
        ("wrongtype", "program type tracing, expected lsm"),
    ],
)
@needs_bash
def test_bootstrap_fails_closed(tmp_path, mutate, message):
    host = Host(tmp_path)
    if mutate == "unlisted":
        host.write_object("stray.o", [("x", "2" * 16, "link")])
    elif mutate == "uppercase":
        replace_file(host.manifest, host.manifest.read_text().upper().replace(".O", ".o"))
    elif mutate == "dotted":
        host.write_object("fs.guard.o", [("x", "3" * 16, "link")])
        host.write_manifest(["fs.guard.o"])
    elif mutate == "duplicate":
        replace_file(host.manifest, host.manifest.read_text() * 2)
    elif mutate == "empty":
        replace_file(host.manifest, "")
    else:
        host.write_object("net_guard.o", [("restrict_socket", "00112233445566ff", mutate)])
        host.write_manifest(list(OBJECTS))
    result = host.bootstrap()
    assert result.returncode != 0
    assert message in result.stderr, result.stderr
    assert not host.attestation.exists()


@needs_bash
def test_bootstrap_rejects_group_writable_object(tmp_path):
    host = Host(tmp_path)
    if not chmod_supported(tmp_path):
        pytest.skip("this filesystem ignores chmod")
    os.chmod(host.lsm_dir / "net_guard.o", 0o664)
    result = host.bootstrap()
    assert result.returncode != 0
    assert "net_guard.o: mode 664 is group- or world-writable" in result.stderr
    assert not host.attestation.exists()


# --------------------------------------------------------------------------
# Pre-job hook rejections
# --------------------------------------------------------------------------


def _edit_attestation(host: Host, edit) -> None:
    lines = host.attestation.read_text().splitlines()
    replace_file(host.attestation, "".join(f"{line}\n" for line in edit(lines)))


@pytest.mark.parametrize(
    "case, message",
    [
        ("other_invocation", "was written for invocation"),
        ("missing_invocation", "INVOCATION_ID is missing"),
        ("other_boot", "boot_id"),
        ("other_kernel", "differs from the running kernel"),
        ("lsm_without_bpf", "BPF LSM is not active"),
        ("unprivileged_bpf_allowed", "unprivileged_bpf_disabled is '2'"),
        ("manifest_changed", "manifest SHA-256 is"),
        ("object_hash_edited", "object net_guard.o: attestation has"),
        ("links_dropped", "object net_guard.o: no attached LSM link recorded"),
        ("attach_type_edited", "expected lsm_mac"),
        ("extra_object", "attestation lists 3 object(s)"),
        ("unknown_key", "unknown key 'note'"),
        ("duplicate_key", "duplicate key boot_id"),
        ("wrong_owner", "owner uid"),
    ],
)
@needs_bash
def test_pre_job_hook_rejects(tmp_path, case, message):
    host = attested_host(tmp_path)
    kwargs = {}
    if case == "other_invocation":
        kwargs["invocation"] = "f" * 32
    elif case == "missing_invocation":
        kwargs["invocation"] = ""
    elif case == "other_boot":
        kwargs["boot"] = "00000000-0000-0000-0000-000000000000"
    elif case == "other_kernel":
        kwargs["kernel"] = "6.9.0-other"
    elif case == "lsm_without_bpf":
        kwargs["lsm"] = "lockdown,capability,yama,apparmor"
    elif case == "unprivileged_bpf_allowed":
        kwargs["unpriv"] = "2"
    elif case == "manifest_changed":
        host.write_manifest(list(OBJECTS), override={"net_guard.o": "e" * 64})
    elif case == "object_hash_edited":
        _edit_attestation(host, lambda ls: [re.sub(r"^(object=net_guard\.o) \w+$", r"\1 " + "d" * 64, l) for l in ls])
    elif case == "links_dropped":
        _edit_attestation(host, lambda ls: [l for l in ls if not l.startswith("link=net_guard.o ")])
    elif case == "attach_type_edited":
        _edit_attestation(host, lambda ls: [l.replace(" lsm_mac", " kprobe_multi", 1) if l.startswith("link=") else l for l in ls])
    elif case == "extra_object":
        _edit_attestation(host, lambda ls: ls + ["object=other.o " + "c" * 64])
    elif case == "unknown_key":
        _edit_attestation(host, lambda ls: ls + ["note=hello"])
    elif case == "duplicate_key":
        _edit_attestation(host, lambda ls: ls + [f"boot_id={BOOT_ID}"])
    elif case == "wrong_owner":
        kwargs["owner"] = host.uid + 1
    result = host.hook(**kwargs)
    assert result.returncode != 0
    assert "::error::" in result.stdout
    assert message in result.stdout, result.stdout
    assert not host.receipt.exists()


@needs_bash
def test_pre_job_hook_rejects_writable_or_symlinked_attestation(tmp_path):
    host = attested_host(tmp_path)
    if not (chmod_supported(tmp_path) and symlinks_supported(tmp_path)):
        pytest.skip("this filesystem ignores chmod or refuses symlinks")
    os.chmod(host.attestation, 0o664)
    result = host.hook()
    assert result.returncode != 0 and "group- or world-writable" in result.stdout
    os.chmod(host.attestation, 0o644)
    real = host.run_dir / "attestation.real"
    host.attestation.rename(real)
    os.symlink(real, host.attestation)
    result = host.hook()
    assert result.returncode != 0 and "missing or a symlink" in result.stdout
    assert not host.receipt.exists()


# --------------------------------------------------------------------------
# Mutation tests: dropping a check makes the corresponding case pass
# --------------------------------------------------------------------------


@needs_bash
def test_mutant_hook_without_invocation_check_accepts_a_stale_attestation(tmp_path):
    host = attested_host(tmp_path)
    source = PRE_JOB.read_text()
    check = '[[ ${ATT[invocation_id]} == "$invocation" ]] \\\n'
    assert check in source
    mutant = tmp_path / "pre-job-mutant.sh"
    mutant.write_text(source.replace(check, "true \\\n", 1))
    result = run_bash(
        HOOK_DRIVER, mutant, host.attestation, host.manifest, host.uid, "f" * 32, BOOT_ID, KERNEL,
        LSM_LIST, "1", host.receipt, env=host.env,
    )
    assert result.returncode == 0, "the mutant should accept; test_pre_job_hook_rejects[other_invocation] guards this"
    assert host.hook(invocation="f" * 32).returncode != 0


@needs_bash
def test_mutant_bootstrap_that_skips_unattached_entries_is_caught(tmp_path):
    # Regression modelled: an entry that is not a link is skipped instead of
    # failing, so one attached program per object would be enough.
    host = Host(tmp_path)
    host.write_object(
        "net_guard.o",
        [("restrict_socket", "00112233445566ff", "link"), ("restrict_bind", "0f0f0f0f0f0f0f0f", "unattached")],
    )
    host.write_manifest(list(OBJECTS))
    source = BOOTSTRAP.read_text()
    check = '|| die "${name}/${prog}: pinned object is not an attached link (unattached program?): ${json}"'
    assert check in source
    mutant = replace_file(tmp_path / "bootstrap-mutant.sh", source.replace(check, "|| continue", 1))
    result = run_bash(
        BOOTSTRAP_DRIVER, mutant, host.lsm_dir, host.stage, host.pin_dir, host.attestation, host.uid,
        INVOCATION, BOOT_ID, KERNEL, LSM_LIST, env=host.env,
    )
    assert result.returncode == 0, result.stderr
    assert "restrict_bind" not in host.attestation.read_text()
    real = host.bootstrap()
    assert real.returncode != 0
    assert "net_guard.o/restrict_bind: pinned object is not an attached link" in real.stderr


# --------------------------------------------------------------------------
# Teardown, registration and post-job functions
# --------------------------------------------------------------------------


@needs_bash
def test_teardown_compares_recorded_links_with_the_kernel(tmp_path):
    host = attested_host(tmp_path)
    driver = STUB_FUNCTION + 'set -euo pipefail; source "$1"; check_links "$2" "$3"'
    ok = run_bash(driver, TEARDOWN, host.attestation, INVOCATION, env=host.env)
    assert ok.returncode == 0, ok.stderr
    assert "3 recorded LSM link(s) compared with the kernel, 0 gone or changed" in ok.stdout
    victim = sorted((host.state / "link").iterdir())[0]
    victim.unlink()
    gone = run_bash(driver, TEARDOWN, host.attestation, INVOCATION, env=host.env)
    assert gone.returncode != 0 and "is gone or now runs another program" in gone.stderr
    other = run_bash(driver, TEARDOWN, host.attestation, "e" * 32, env=host.env)
    assert other.returncode != 0 and "belongs to invocation" in other.stderr
    missing = run_bash(driver, TEARDOWN, tmp_path / "absent", INVOCATION, env=host.env)
    assert missing.returncode == 0 and "nothing to compare" in missing.stdout


@needs_bash
def test_teardown_archives_logs_prunes_old_copies_and_scrubs(tmp_path):
    runner = tmp_path / "actions-runner"
    (runner / "_diag" / "pages").mkdir(parents=True)
    (runner / "_diag" / "Runner_20261111.log").write_text("runner log\n")
    (runner / "_diag" / "Worker_20261111.log").write_text("worker log\n")
    (runner / "_diag" / "pages" / "step.log").write_text("step output\n")
    (runner / "_work" / "repo" / "repo").mkdir(parents=True)
    (runner / "_work" / "repo" / "repo" / "secret.txt").write_text("job data\n")
    for name in (".runner", ".credentials", ".credentials_rsaparams"):
        (runner / name).write_text("{}")
    (runner / "run.sh").write_text("#!/bin/sh\n")
    archive = tmp_path / "runner-diag"
    (archive / "old-invocation").mkdir(parents=True)
    (archive / "recent-invocation").mkdir()
    old = 1_000_000_000
    os.utime(archive / "old-invocation", (old, old))
    driver = 'set -euo pipefail; source "$1"; archive_diag "$2/_diag" "$3" "$4" "$5"; scrub_runner_tree "$2"'
    result = run_bash(driver, TEARDOWN, runner, archive, INVOCATION, "14", env={"PATH": os.environ.get("PATH", "") + ":/usr/bin:/bin", "LC_ALL": "C", "TMPDIR": str(tmp_path)})
    assert result.returncode == 0, result.stderr
    assert sorted(p.name for p in (archive / INVOCATION).iterdir()) == ["Runner_20261111.log", "Worker_20261111.log"]
    assert not (archive / "old-invocation").exists()
    assert (archive / "recent-invocation").exists()
    assert (runner / "_work").is_dir() and not any((runner / "_work").iterdir())
    assert not any((runner / n).exists() for n in (".runner", ".credentials", ".credentials_rsaparams"))
    assert (runner / "run.sh").exists()


def _write_env(path: Path, text: str, mode: int = 0o600) -> Path:
    return replace_file(path, text, mode)


REGISTER_DRIVER = r"""
set -euo pipefail
source "$1"
read_env_file "$2" "$3"
build_config_args testhost 1700000000
printf '%s\0' "${CONFIG_ARGS[@]}"
"""


@needs_bash
def test_register_builds_ephemeral_arguments_without_the_token(tmp_path):
    if not chmod_supported(tmp_path):
        pytest.skip("this filesystem ignores chmod; the settings file must be 0600")
    token = "AABBCCDDEEFFGG0123456789"
    env_file = _write_env(
        tmp_path / "runner.env",
        f'# registration\nRUNNER_CFG_TOKEN={token}\n\nREPO_URL="https://github.com/example-org/example"\n',
    )
    result = run_bash(REGISTER_DRIVER, REGISTER, env_file, os.getuid())
    assert result.returncode == 0, result.stderr
    args = result.stdout.split("\0")[:-1]
    assert token not in " ".join(args)
    for flag in ("--unattended", "--ephemeral", "--disableupdate", "--replace"):
        assert flag in args
    assert args[args.index("--url") + 1] == "https://github.com/example-org/example"
    assert args[args.index("--name") + 1] == "sovereign-testhost-1700000000"
    assert args[args.index("--labels") + 1] == "sovereign,al-haras-enforced"
    assert args[args.index("--work") + 1] == "_work"
    assert "--runnergroup" not in args

    _write_env(env_file, f"RUNNER_CFG_TOKEN={token}\nRUNNER_GROUP=sovereign-compute\nRUNNER_LABELS=sovereign,gpu\n")
    args = run_bash(REGISTER_DRIVER, REGISTER, env_file, os.getuid()).stdout.split("\0")[:-1]
    assert args[args.index("--runnergroup") + 1] == "sovereign-compute"
    assert args[args.index("--labels") + 1] == "sovereign,gpu"


@pytest.mark.parametrize(
    "text, message",
    [
        ("RUNNER_CFG_PAT=ghp_x\n", "unsupported key RUNNER_CFG_PAT"),
        ("REPO_URL=https://github.com/x/y\n", "RUNNER_CFG_TOKEN is not set"),
        ("RUNNER_CFG_TOKEN=abc def\n", "whitespace or control characters"),
        ("RUNNER_CFG_TOKEN=abc\nREPO_URL=http://github.com/x/y\n", "https:// URL"),
        ("RUNNER_CFG_TOKEN=abc\nRUNNER_LABELS=a b\n", "comma-separated labels"),
        ("export RUNNER_CFG_TOKEN=abc\n", "expected KEY=VALUE"),
    ],
)
@needs_bash
def test_register_rejects_bad_settings(tmp_path, text, message):
    if not chmod_supported(tmp_path):
        pytest.skip("this filesystem ignores chmod; the settings file must be 0600")
    env_file = _write_env(tmp_path / "runner.env", text)
    result = run_bash(REGISTER_DRIVER, REGISTER, env_file, os.getuid())
    assert result.returncode != 0
    assert message in result.stderr, result.stderr


@needs_bash
def test_register_rejects_env_file_readable_by_others_or_owned_by_someone_else(tmp_path):
    env_file = _write_env(tmp_path / "runner.env", "RUNNER_CFG_TOKEN=abc\n")
    wrong_owner = run_bash(REGISTER_DRIVER, REGISTER, env_file, os.getuid() + 1)
    assert wrong_owner.returncode != 0 and "owner uid" in wrong_owner.stderr
    if not chmod_supported(tmp_path):
        pytest.skip("this filesystem ignores chmod")
    os.chmod(env_file, 0o640)
    readable = run_bash(REGISTER_DRIVER, REGISTER, env_file, os.getuid())
    assert readable.returncode != 0 and "allows group/other access" in readable.stderr


@needs_bash
def test_post_job_scrub_deletes_receipt_and_checkout_only_under_work_root(tmp_path):
    work = tmp_path / "_work"
    receipt_dir = work / "_al_haras"
    workspace = work / "Chronusv2" / "Chronusv2"
    actions = work / "_actions"
    for d in (receipt_dir, workspace / "src", actions):
        d.mkdir(parents=True)
    (receipt_dir / "pre-flight-receipt.json").write_text("{}")
    (workspace / "src" / "a.py").write_text("x = 1\n")
    (workspace / ".git").mkdir()
    (actions / "keep").write_text("teardown removes this")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep").write_text("not under _work")
    driver = 'set -euo pipefail; source "$1"; scrub_job_files "$2" "$3" "$4"'
    env = {"PATH": os.environ.get("PATH", "") + ":/usr/bin:/bin", "LC_ALL": "C", "TMPDIR": str(tmp_path)}
    result = run_bash(driver, POST_JOB, work, receipt_dir, workspace, env=env)
    assert result.returncode == 0, result.stderr
    assert not receipt_dir.exists()
    assert workspace.is_dir() and not any(workspace.iterdir())
    assert (actions / "keep").exists()
    refused = run_bash(driver, POST_JOB, work, receipt_dir, outside, env=env)
    assert refused.returncode == 0 and "outside" in refused.stdout
    assert (outside / "keep").exists()
    dotdot = run_bash(driver, POST_JOB, work, receipt_dir, f"{work}/../outside", env=env)
    assert "outside" in dotdot.stdout and (outside / "keep").exists()
