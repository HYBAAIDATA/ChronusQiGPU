# Setting up the fleet on new Apple Silicon Macs

Copyright (c) 2026 HYBA Software Ltd. All rights reserved. Chronus is a HYBA Data product.

This guide takes a brand-new MacBook and iMac (Apple Silicon) to one Chronus iGPU. The **iMac runs the coordinator**, because it stays on. By default each Mac runs the **Chronus iGPU**, our software-defined GPU (`--prefer ours`), even though it has its own GPU; you can also lend the Mac's own GPU (Metal) when you choose (`--prefer host` or `--backend metal`). Type the commands into **Terminal** (Applications → Utilities → Terminal), one block at a time. Lines beginning with `#` are comments.


## Step 0 — secure the Mac first (before anything else)

Do these once, before installing anything:

1. **FileVault on:** System Settings → Privacy & Security → FileVault → Turn On. Keep the recovery key offline, not on the Mac.
2. **Find My on:** System Settings → your name → iCloud → Find My Mac → On (enables Activation Lock and remote erase).
3. **Strong login password; screen lock after 5 minutes;** Touch ID for unlock.
4. **Two-factor everywhere with recovery codes stored offline** (printed or in a password manager that is not only on this Mac): Apple ID, GitHub, Microsoft 365, Azure DevOps, the mining pools. Prefer passkeys or a hardware security key over SMS.
5. **Backups:** Time Machine to an encrypted external drive, plus an encrypted cloud backup. Code lives in two remotes (GitHub `hybadatadevops1` and Azure DevOps `HYBADATA`), never only on this machine.
6. **Secrets stay in the Keychain** (the setup scripts store pool logins there). Never in files inside the repository.

Treat anything that was saved on earlier, lost machines as exposed: rotate tokens, keys and passwords that were stored on them.

## 1. On both Macs: tools, Python 3.12 and the code

```bash
# Apple's command-line developer tools (a window opens; click Install and wait)
xcode-select --install

# Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"

# Python 3.12, git and the GitHub command line
brew install python@3.12 git gh

# Sign in to GitHub (choose GitHub.com, HTTPS, "Login with a web browser")
gh auth login

# The Chronus repository
mkdir -p ~/hyba && cd ~/hyba
gh repo clone hybadatadevops1/Chronusv2
cd Chronusv2
# Until the fleet pull request is merged, use its branch (skip once it is on main):
git switch cowork/igpu-fleet-20261111

# A virtual environment with Chronus, the fleet and MLX (Apple GPU)
/opt/homebrew/bin/python3.12 -m venv ~/.venvs/chronus
source ~/.venvs/chronus/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[fleet-metal]"
```

Check what this Mac offers. It detects each backend, runs the known-answer self-tests, times the verified ones and shows which backend your option selects:

```bash
chronus-fleet bench
```

Expect `igpu`, `simd` and `reference` (and `metal`, the Mac's own GPU) to show **verified**, and `backend: requested auto, prefer ours -> igpu`. `opencl`, `cuda` and `cpp-simd` will show **absent** with the reason; that is correct, and nothing pretends otherwise. `chronus-fleet bench --prefer host` shows `-> metal`. If `metal` shows **FAILED**, the fleet will not use it. Save the details with `chronus-fleet bench --backend metal --json > ~/Desktop/metal-bench.json` and send the file to HYBA engineering.

Optional extras:

```bash
python -m pip install -e ".[fleet-metal,fleet-opencl]"        # Apple's OpenCL GPU route as well
python -m pip install -e ".[fleet-metal,fleet-metal-pyobjc]"  # PyObjC Metal as a second Metal engine
```

Every new Terminal window needs the environment again:

```bash
cd ~/hyba/Chronusv2 && source ~/.venvs/chronus/bin/activate
```

## 2. On the iMac: create the fleet and start the coordinator

```bash
cd ~/hyba/Chronusv2 && source ~/.venvs/chronus/bin/activate

# The iMac's network name, for example Andres-iMac.local; note it down
HOST="$(scutil --get LocalHostName).local"; echo "$HOST"

# Fleet token, receipt-signing key and a TLS certificate for that name (once only)
chronus-fleet init --tls-host "$HOST" --tls-host localhost

# Start the coordinator for the local network (leave this window open)
chronus-fleet coordinator --host 0.0.0.0 --port 8740 --tls
```

When macOS asks whether Python may accept incoming network connections, click **Allow**.

## 3. On the iMac: join the fleet

Open a **second** Terminal window (⌘N). This joins with the default, the Chronus iGPU (`--backend auto --prefer ours`):

```bash
cd ~/hyba/Chronusv2 && source ~/.venvs/chronus/bin/activate
HOST="$(scutil --get LocalHostName).local"
caffeinate -i chronus-fleet join --coordinator "https://$HOST:8740" \
  --tls-ca ~/.chronus/fleet/tls/coordinator-cert.pem --label imac
```

To lend the iMac's own GPU as well, open a **third** window and choose the host GPU (exactly Metal, or fail closed):

```bash
cd ~/hyba/Chronusv2 && source ~/.venvs/chronus/bin/activate
HOST="$(scutil --get LocalHostName).local"
caffeinate -i chronus-fleet join --coordinator "https://$HOST:8740" \
  --tls-ca ~/.chronus/fleet/tls/coordinator-cert.pem --backend metal --label imac-gpu
```

(`--prefer host` instead of `--backend metal` uses Metal when it passes its self-test and the Chronus iGPU otherwise, with the reason recorded.)

`caffeinate -i` keeps the Mac awake while it works. On the iMac the token is read from `~/.chronus/fleet/token` automatically.

## 4. Give the MacBook the token and the certificate

On the **iMac**, open the fleet folder in Finder:

```bash
open ~/.chronus/fleet
```

AirDrop two files to the MacBook: `token`, and `coordinator-cert.pem` from the `tls` folder. **Never send `coordinator-key.pem` or `coordinator_mldsa65.seed`**; they stay on the iMac.

On the **MacBook**, move them into place (they arrive in Downloads):

```bash
mkdir -p ~/.chronus/fleet/tls && chmod 700 ~/.chronus ~/.chronus/fleet
mv ~/Downloads/token ~/.chronus/fleet/token && chmod 600 ~/.chronus/fleet/token
mv ~/Downloads/coordinator-cert.pem ~/.chronus/fleet/tls/coordinator-cert.pem
```

## 5. On the MacBook: join

Use the iMac name noted in step 2 (here `Andres-iMac.local`). In one window, the Chronus iGPU (the default):

```bash
cd ~/hyba/Chronusv2 && source ~/.venvs/chronus/bin/activate
caffeinate -i chronus-fleet join --coordinator https://Andres-iMac.local:8740 \
  --tls-ca ~/.chronus/fleet/tls/coordinator-cert.pem --label macbook
```

Optionally, in a second window, the MacBook's own GPU:

```bash
cd ~/hyba/Chronusv2 && source ~/.venvs/chronus/bin/activate
caffeinate -i chronus-fleet join --coordinator https://Andres-iMac.local:8740 \
  --tls-ca ~/.chronus/fleet/tls/coordinator-cert.pem --backend metal --label macbook-gpu
```

## 6. Check the fleet and run a job

From either Mac:

```bash
chronus-fleet status --coordinator https://Andres-iMac.local:8740 \
  --tls-ca ~/.chronus/fleet/tls/coordinator-cert.pem

chronus-fleet run --coordinator https://Andres-iMac.local:8740 \
  --tls-ca ~/.chronus/fleet/tls/coordinator-cert.pem --kernel m15_fold --size 16MiB
```

`status` lists the workers, the backend each one selected and their measured throughput. It also shows the tier: with four workers, 4 × 8,000 virtual units = 1,000 logical warps against Tier 1's entitlement of 1,024 (provisioning, not a performance claim). `run` sends a 16 MiB job across the fleet, checks that the result is exact, verifies the ML-DSA-65 receipt and saves it as `receipt-job-….json`. To check a saved receipt again later:

```bash
<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:75584bee6ec7af891322638a566e69814dd55b6a19420d412de9816f1972f58d -->

chronus-fleet verify-receipt receipt-job-<id>.json --public-key <coordinator-public-key-hex>

<!-- /coderabbit-ai-generated:v1 -->
```

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:39415cef16b6b2646d2251905fa15bb7348406542ce5e06ddb9c354976b9aefd -->

Obtain the coordinator public key directly from the coordinator machine's
owner-controlled state or an authenticated status response, and compare it over
a separate trusted channel. Do not take the verification key from the receipt
file being checked. Receipt signature verification does not independently prove
ledger inclusion unless the verifier also checks the local ledger file.

## 7. Other laptops and servers

<!-- /coderabbit-ai-generated:v1 -->

On Linux or Windows with Python 3.10 or later, install the repository the same way (`python -m pip install -e .`; add `".[fleet-opencl]"` on a machine with an OpenCL GPU). Copy `token` and `coordinator-cert.pem` across, then run:

```bash
chronus-fleet join --coordinator https://Andres-iMac.local:8740 \
  --token-file ~/.chronus/fleet/token --tls-ca ~/.chronus/fleet/tls/coordinator-cert.pem
```

Tier 1 provisions 1,024 logical warps. With four workers at 8,000 virtual units (1,000 warps) in place, a fifth machine joins and **waits** (`waiting for the fleet to scale`); `chronus-fleet tier status` shows `scale available: Tier 2`.

## 8. Move to Tier 2

On the iMac (the coordinator, so the owner's signing key is there), in a new window:

```bash
cd ~/hyba/Chronusv2 && source ~/.venvs/chronus/bin/activate
chronus-fleet tier grant --tier 2 --expires 30d
chronus-fleet tier set --tier 2
HOST="$(scutil --get LocalHostName).local"
chronus-fleet tier status --coordinator "https://$HOST:8740" --tls-ca ~/.chronus/fleet/tls/coordinator-cert.pem
```

The grant is signed with ML-DSA-65 by the coordinator's key and lasts 30 days; the coordinator applies it within 2 seconds, admits any waiting machine at its full 8,000 virtual units and `tier status` shows Tier 2 (10,000 logical warps, 1,000 TB). Renew with another `tier grant` before it expires; when it expires the fleet returns to Tier 1 and the newest machines wait. To move down at any time: `chronus-fleet tier set --tier 1`.

## Stopping and restarting

- Press **Ctrl-C** in a worker window: the worker finishes its tile, leaves the fleet and its work moves to the others.
- Press **Ctrl-C** in the coordinator window to stop the fleet. The token, signing key, ledger (`~/.chronus/fleet/ledger.jsonl`) and receipts (`~/.chronus/fleet/receipts/`) stay on disk and are reused at the next start.

## If something goes wrong

| Message | Fix |
|---|---|
| `the coordinator rejected this fleet token` | The token file differs from the iMac's. Copy `~/.chronus/fleet/token` again. |
| `certificate verify failed` | Use the iMac's own `coordinator-cert.pem`, and the exact name printed in step 2. If the iMac's name changed, run `chronus-fleet init --tls-host <new name>` on the iMac, then copy the certificate again. |
| `request timestamp outside the allowed clock skew` | Turn on System Settings → General → Date & Time → Set time and date automatically, on both Macs. |
| `joined as ...; waiting for the fleet to scale` | Tier 1's entitlement is in use. On the iMac: `chronus-fleet tier grant --tier 2 --expires 30d` (section 8). |
| `backend metal unavailable; failing closed` | Metal is absent or failed its self-test on this Mac. Join without `--backend` to run the Chronus iGPU. |
| `cannot reach coordinator` | Both Macs must be on the same network, the coordinator window must be running, and macOS must have allowed Python's incoming connections (System Settings → Network → Firewall → Options). |
