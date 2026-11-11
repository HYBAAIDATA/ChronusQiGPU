#!/usr/bin/env python3
"""Workbench fix script (never merged): restore green CI on main.

Each change fixes a root cause found in the CI logs; no test or gate is
weakened. Every replacement asserts the exact number of matches, so a drift in
the source stops the script instead of producing a partial edit.
"""
import ast
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
WB = Path(os.environ["WB"])


def read(path):
    return (ROOT / path).read_bytes().decode("utf-8")


def write(path, text):
    (ROOT / path).write_bytes(text.encode("utf-8"))


def newline_of(text):
    return "\r\n" if text.count("\r\n") * 2 > text.count("\n") else "\n"


def replace_exact(path, old, new, count=1):
    text = read(path)
    nl = newline_of(text)
    old_n, new_n = old.replace("\n", nl), new.replace("\n", nl)
    found = text.count(old_n)
    if found != count:
        sys.exit(f"{path}: expected {count} x {old[:70]!r}, found {found}")
    write(path, text.replace(old_n, new_n))


def replace_regex(path, pattern, new, count=1, flags=0):
    text = read(path)
    nl = newline_of(text)
    new_n = new.replace("\n", nl)
    result, found = re.subn(pattern, lambda _m: new_n, text, flags=flags)
    if found != count:
        sys.exit(f"{path}: expected {count} match(es) for {pattern[:70]!r}, found {found}")
    write(path, result)


def git(*args):
    subprocess.run(["git", *args], cwd=ROOT, check=True)


# 1. Purity gate: apply its own documented rule (exact integer helpers are allowed).
PG = "scripts/ci/purity_gate.py"
replace_exact(PG, '(re.compile(r"(?<![\\w.])math\\.(?!isqrt)"), "floating-point math module usage"),',
              '(re.compile(r"(?<![\\w.])math\\.(?!(?:isqrt|gcd|lcm|comb|perm|factorial)\\b)"), "floating-point math module usage"),')
replace_exact(PG, "   `math.isqrt` are allowlisted.",
              "   `math.isqrt`, `math.gcd`, `math.lcm`, `math.comb`, `math.perm` and\n"
              "   `math.factorial` are allowlisted: they accept only integers and return\n"
              "   exact integers (floats raise TypeError).")
write("tests/test_purity_gate_rules.py", (WB / "test_purity_gate_rules.py").read_text())

# 2. Static security: the standalone HR API binds to loopback unless configured.
HR = "src/chronus/service/production_hr_api.py"
hr_text = read(HR)
local_os = "" if re.search(r"^import os\b", hr_text, re.M) else "    import os\n\n"
replace_regex(HR, r'if __name__ == "__main__":\r?\n    import uvicorn\r?\n    uvicorn\.run\(app, host="0\.0\.0\.0", port=8000\)',
              'if __name__ == "__main__":\n' + local_os +
              "    import uvicorn\n\n"
              "    # Loopback by default; a deployment sets CHRONUS_HR_API_HOST explicitly.\n"
              "    uvicorn.run(\n"
              "        app,\n"
              '        host=os.environ.get("CHRONUS_HR_API_HOST", "127.0.0.1"),\n'
              '        port=int(os.environ.get("CHRONUS_HR_API_PORT", "8000")),\n'
              "    )")

# 3. Lint F811: the first get_patroclus_status is dead code (Python binds the later one).
MA = "src/chronus/execution/mining_admin.py"
ma_text = read(MA)
defs = sorted((n for n in ast.walk(ast.parse(ma_text)) if isinstance(n, ast.FunctionDef) and n.name == "get_patroclus_status"),
              key=lambda n: n.lineno)
if len(defs) != 2:
    sys.exit(f"{MA}: expected two get_patroclus_status definitions, found {len(defs)}")
lines = ma_text.splitlines(keepends=True)
start = (defs[0].decorator_list[0].lineno if defs[0].decorator_list else defs[0].lineno) - 1
end = defs[0].end_lineno
while end < len(lines) and not lines[end].strip():
    end += 1
write(MA, "".join(lines[:start] + lines[end:]))

# 4. Stratum E2E fixture: rebuild the real Bitcoin block 0 coinbase so the known
#    genesis nonce is a true known-answer test, and make the local pool verify shares.
E2E = "src/chronus/execution/master_e2e_engine.py"
replace_exact(E2E, "class LocalStratumTestServer:",
              "# Bitcoin block 0 coinbase transaction (public chain data). Its sha256d is the\n"
              "# genesis merkle root 4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b.\n"
              "GENESIS_COINBASE_HEX = (\n"
              '    "01000000" "01" + "00" * 32 + "ffffffff" "4d"\n'
              '    "04ffff001d0104455468652054696d65732030332f4a616e2f32303039204368616e63656c6c6f72"\n'
              '    "206f6e206272696e6b206f66207365636f6e64206261696c6f757420666f722062616e6b73"\n'
              '    "ffffffff" "01" "00f2052a01000000" "43"\n'
              '    "4104678afdb0fe5548271967f1a67130b7105cd6a828e03909a67962e0ea1f61deb649f6bc3f"\n'
              '    "4cef38c4f35504e51ec112de5c384df7ba0b8d578a4c702b6bf11d5fac"\n'
              '    "00000000"\n'
              ")\n\n\n"
              "class LocalStratumTestServer:")
replace_exact(E2E, "      mining.submit → accept share and return result",
              "      mining.submit → rebuild the header from the job and accept only shares\n"
              "                      whose sha256d meets the pushed difficulty")
replace_exact(E2E, '        self.extranonce1 = "a45b7889"',
              '        # Block 0 has no pool extranonce1: coinb1 + extranonce2 + coinb2 must\n'
              '        # reproduce the genesis coinbase byte for byte.\n'
              '        self.extranonce1 = ""')
replace_regex(E2E, r'        self\.coinb1 = "[0-9a-f]+"', "        self.coinb1 = GENESIS_COINBASE_HEX[:2]")
replace_regex(E2E, r'        self\.coinb2 = "[0-9a-f]+"', "        self.coinb2 = GENESIS_COINBASE_HEX[2 + 2 * self.extranonce2_size:]")
replace_exact(E2E, '        self.ntime = "495fab29"', '        self.ntime = "495fab29"\n        self.share_difficulty = 1')
replace_exact(E2E, '"method": "mining.set_difficulty", "params": [1]}',
              '"method": "mining.set_difficulty", "params": [self.share_difficulty]}')
replace_regex(E2E, r'                elif method == "mining\.submit":\r?\n                    res = \{"id": req_id, "result": True, "error": None\}',
              '                elif method == "mining.submit":\n'
              "                    accepted = self.validate_share(_params)\n"
              "                    res = {\n"
              '                        "id": req_id,\n'
              '                        "result": accepted,\n'
              '                        "error": None if accepted else [23, "Low difficulty share", None],\n'
              "                    }")
replace_exact(E2E, "    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):",
              "    def validate_share(self, params: List[Any]) -> bool:\n"
              '        """Recompute the submitted header from the job; accept only a share meeting the difficulty."""\n'
              "        if not isinstance(params, list) or len(params) < 5:\n"
              "            return False\n"
              "        _worker, job_id, extranonce2_hex, ntime_hex, nonce_hex = params[:5]\n"
              "        if job_id != self.current_job_id or len(str(extranonce2_hex)) != self.extranonce2_size * 2:\n"
              "            return False\n"
              "        try:\n"
              "            mask = int(self.pool_mask, 16)\n"
              "            version_int = int(self.version, 16)\n"
              "            if len(params) > 5 and params[5] is not None:\n"
              "                version_int = (version_int & ~mask) | (int(params[5], 16) & mask)\n"
              "            merkle_root = compute_merkle_root(\n"
              "                self.coinb1, self.extranonce1, extranonce2_hex, self.coinb2, list(self.merkle_branch)\n"
              "            )\n"
              "            header = build_block_header(\n"
              "                version_int, swap_endian_words(self.prevhash_stratum), merkle_root,\n"
              "                ntime_hex, self.nbits, int(nonce_hex, 16)\n"
              "            )\n"
              "        except (TypeError, ValueError):\n"
              "            return False\n"
              "        is_valid, _block_hash, _hash_int, _target = check_share_difficulty_exact(header, self.share_difficulty)\n"
              "        return is_valid\n\n"
              "    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):")

# 5. v36 receipts: real FIPS 204 ML-DSA-65 signatures verified with the signer's public key.
V = "src/chronus/chronus_gpiu-v36.py"
replace_regex(V, r"class MLDSASigner:\r?\n.*?(?=\r?\n\r?\n\r?\nclass Poseidon2FiatShamirIVCFolder:)",
              (WB / "mldsa_v36_block.py").read_text().rstrip("\n"), flags=re.S)
replace_regex(V, r'_signing_seed = hashlib\.sha256\(f"mldsa_tenant_key_v1:\{tenant_hash\}"\.encode\(\)\)\.digest\(\)\r?\n[ \t]*rs = MLDSASigner\.sign_mldsa\(_signing_seed, rh\)',
              "rs = MLDSASigner.sign_mldsa(MLDSASigner.tenant_private_key(tenant_hash), rh)")
replace_exact(V, 'MLDSASigner.verify_mldsa(b"mock_pub", recomputed, stored.receipt_sig)',
              "MLDSASigner.verify_mldsa(MLDSASigner.tenant_public_key(stored.tenant_hash), recomputed, stored.receipt_sig)")
replace_exact(V, 'MLDSASigner.verify_mldsa(b"pub", rh, stored.receipt_sig)',
              "MLDSASigner.verify_mldsa(MLDSASigner.tenant_public_key(stored.tenant_hash), rh, stored.receipt_sig)", count=2)
replace_exact(V, '"I3  PASS — ML-DSA Post-Quantum lattice signature structurally valid"',
              '"I3  PASS — FIPS 204 ML-DSA-65 receipt signature verified with the tenant public key"', count=2)
replace_exact(V, "to reduce AIR degree by 100x.", "to reduce AIR degree from 2^16 to 2^6.")
replace_exact(V, '"air_degree_reduction": "100x (Degree 2^16 -> 2^6 via Poseidon2)",',
              '"air_degree_reduction": f"{(1 << 16) // (1 << 6)}-fold (Degree 2^16 -> 2^6 via Poseidon2)",')

# 6. Frontend: restore the five AL HARAS application calls dropped by e04dbd0
#    (backend routes exist under /v1/al-haras/applications).
API = "frontend/lib/api-client.ts"
old_api = subprocess.check_output(["git", "show", "0d564c4:" + API], cwd=ROOT).decode("utf-8").replace("\r\n", "\n").split("\n")
blocks = []
for name in ("executeAgenticSheafTurn", "transmitOrbitalTelemetry", "executeZkNeuralProveAndVerify",
             "processCBDCCrossBorderSettlement", "executeTISAMicrocode"):
    first = next(i for i, line in enumerate(old_api) if line.strip().startswith(f"static {name} ="))
    last = first + 1
    while last < len(old_api) and not old_api[last].strip().startswith("static ") and not old_api[last].startswith("}"):
        last += 1
    block = old_api[first:last]
    while block and (not block[-1].strip() or block[-1].strip().startswith("//")):
        block.pop()
    blocks.append("\n".join(block))
replace_exact(API, "  // Hashrate Intelligence & Mining Administration",
              "  // AL HARAS (HYBA Security) application engines: /v1/al-haras/applications/*\n"
              + "\n".join(blocks) + "\n\n  // Hashrate Intelligence & Mining Administration")
replace_exact("frontend/app/mining/page.tsx", '<span className="text-emerald-400">#{lastMinedBlock}</span>',
              '<span className="text-neutral-400">not reported by the miner</span>')

# 7. Preserve the review text that overwrote the attestation file; regenerate valid JSON.
git("mv", "SOVEREIGN_CAPABILITY_ATTESTATION.json", "reviews/attestation-file-review-2026-11-11.md")

# 8. Claim-token gate: exact exclusions and a reviewed allowlist (policy generated next).
write("scripts/ci/check_forbidden_claims.py", (WB / "check_forbidden_claims.py").read_text())
write("tests/test_forbidden_claims.py", (WB / "test_forbidden_claims.py").read_text())
print("fix_ci.py: all edits applied")
