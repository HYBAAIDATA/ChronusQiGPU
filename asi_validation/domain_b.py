"""Domain B exact-reconstruction harness.

The harness deliberately measures only observable properties.  A successful
round trip establishes byte identity for the supplied input; it does not, by
itself, establish compression, intelligence, or thermodynamic superiority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class RoundTripResult:
    """Machine-readable evidence from one fold/unfold trial."""

    trial: int
    input_bytes: int
    encoded_bytes: int
    input_sha512: str
    output_sha512: str
    encode_seconds: float
    decode_seconds: float
    exact_match: bool


def _sha512(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha512()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _materialize(command: Sequence[str], source: Path, destination: Path) -> list[str]:
    """Replace explicit path placeholders without invoking a shell."""
    if not command:
        raise ValueError("command must not be empty")
    if not any("{input}" in part for part in command):
        raise ValueError("command must contain an {input} placeholder")
    if not any("{output}" in part for part in command):
        raise ValueError("command must contain an {output} placeholder")
    rendered = [part.replace("{input}", str(source)).replace("{output}", str(destination)) for part in command]
    return rendered


def run_round_trip(
    source: Path,
    work_dir: Path,
    encoder: Sequence[str],
    decoder: Sequence[str],
    *,
    trials: int = 1,
) -> list[RoundTripResult]:
    """Run isolated encoder/decoder trials and return auditable observations."""
    source = source.resolve(strict=True)
    if not source.is_file():
        raise ValueError(f"source is not a regular file: {source}")
    if trials < 1:
        raise ValueError("trials must be at least one")

    work_dir.mkdir(parents=True, exist_ok=True)
    input_hash = _sha512(source)
    results: list[RoundTripResult] = []
    for trial in range(1, trials + 1):
        trial_dir = work_dir / f"trial-{trial:04d}"
        if trial_dir.exists():
            shutil.rmtree(trial_dir)
        trial_dir.mkdir()
        encoded = trial_dir / "encoded.bin"
        reconstructed = trial_dir / "reconstructed.bin"

        started = time.perf_counter()
        subprocess.run(_materialize(encoder, source, encoded), check=True)
        encode_seconds = time.perf_counter() - started
        if not encoded.is_file():
            raise RuntimeError("encoder completed without producing its output")

        started = time.perf_counter()
        subprocess.run(_materialize(decoder, encoded, reconstructed), check=True)
        decode_seconds = time.perf_counter() - started
        if not reconstructed.is_file():
            raise RuntimeError("decoder completed without producing its output")

        output_hash = _sha512(reconstructed)
        results.append(
            RoundTripResult(
                trial=trial,
                input_bytes=source.stat().st_size,
                encoded_bytes=encoded.stat().st_size,
                input_sha512=input_hash,
                output_sha512=output_hash,
                encode_seconds=encode_seconds,
                decode_seconds=decode_seconds,
                exact_match=input_hash == output_hash and source.stat().st_size == reconstructed.stat().st_size,
            )
        )
    return results


def _command_argv(value: str) -> list[str]:
    """Tokenize a single shell-quoted command into argv.

    The codec command is one quoted string rather than ``nargs="+"``: a
    variadic option cannot express a real codec invocation, because argparse
    claims any token that begins with "-" -- ``--encoder zstd -d`` and
    ``--encoder python -c '...'`` were both unusable, which is to say no real
    codec could be benchmarked through this CLI. Quoting survives those
    tokens: ``--encoder "zstd -d"`` reaches the codec intact.
    """
    command = shlex.split(value)
    if not command:
        raise argparse.ArgumentTypeError("command must not be empty")
    return command


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Domain B exact-reconstruction protocol")
    parser.add_argument("source", type=Path)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument(
        "--encoder",
        type=_command_argv,
        required=True,
        metavar="COMMAND",
        help='shell-quoted encoder argv containing {input} and {output}; e.g. "zstd -q {input} -o {output}"',
    )
    parser.add_argument(
        "--decoder",
        type=_command_argv,
        required=True,
        metavar="COMMAND",
        help='shell-quoted decoder argv containing {input} and {output}; e.g. "zstd -d {input} -o {output}"',
    )
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    results = run_round_trip(args.source, args.work_dir, args.encoder, args.decoder, trials=args.trials)
    report = {
        "schema_version": 1,
        "domain": "B",
        "results": [asdict(result) for result in results],
        "all_exact": all(result.exact_match for result in results),
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["all_exact"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
