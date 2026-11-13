# HYBA Mine on a new Mac: quick start

HYBA Mine is HYBA's internal treasury mining runtime. Each run detects the Mac's backends and uses the one you choose. By default (`--backend auto --prefer ours`) it runs on the Chronus iGPU, HYBA's software-defined GPU (Mode A), even though the Mac has its own GPU; `--prefer host` uses the Apple GPU through Metal instead when the Metal lane passes its self-test. It is not a product and is never customer-facing.

Do this once on the MacBook and once on the iMac. Use a different worker name on each.


## Step 0 — secure the Mac first (before anything else)

Do these once, before installing anything:

1. **FileVault on:** System Settings → Privacy & Security → FileVault → Turn On. Keep the recovery key offline, not on the Mac.
2. **Find My on:** System Settings → your name → iCloud → Find My Mac → On (enables Activation Lock and remote erase).
3. **Strong login password; screen lock after 5 minutes;** Touch ID for unlock.
4. **Two-factor everywhere with recovery codes stored offline** (printed or in a password manager that is not only on this Mac): Apple ID, GitHub, Microsoft 365, Azure DevOps, the mining pools. Prefer passkeys or a hardware security key over SMS.
5. **Backups:** Time Machine to an encrypted external drive, plus an encrypted cloud backup. Code lives in two remotes (GitHub `hybadatadevops1` and Azure DevOps `HYBADATA`), never only on this machine.
6. **Secrets stay in the Keychain** (the setup scripts store pool logins there). Never in files inside the repository.

Treat anything that was saved on earlier, lost machines as exposed: rotate tokens, keys and passwords that were stored on them.

## 1. Before you start

- A Mac with Apple Silicon, signed in with an administrator account, connected to the internet and to power.
- Your pool login for one of the four pools HYBA Mine uses:

| Pool | `--pool` | Username (worker name) format | Password |
|---|---|---|---|
| ViaBTC | `viabtc` | `<ViaBTC account or sub-account>.<worker>`, e.g. `hyba.macbook` | any value; ViaBTC ignores it (`123` is customary) |
| Braiins Pool | `braiins` | `<Braiins username>.<worker>`, e.g. `hyba.imac` | anything; Braiins does not use it |
| NiceHash | `nicehash` | `<NiceHash BTC mining address>.<worker>`, e.g. `bc1q….macbook` | `x` |
| ckpool (solo.ckpool.org) | `ckpool` | `<your BTC address>.<worker>`, e.g. `bc1q….imac` | `x` (ignored) |

Endpoints, in the order HYBA Mine tries them (TLS first where the pool offers it):

| Pool | Endpoints |
|---|---|
| ViaBTC | `stratum+ssl://btc-ssl.viabtc.io:551`, `stratum+tcp://btc.viabtc.io:3333`, `stratum+tcp://btc.viabtc.io:443` |
| Braiins Pool | `stratum+tcp://stratum.braiins.com:3333`, `stratum+tcp://stratum.braiins.com:443` |
| NiceHash | `stratum+ssl://sha256asicboost.auto.nicehash.com:443`, `stratum+tcp://sha256asicboost.auto.nicehash.com:9200` |
| ckpool | `stratum+tcp://solo.ckpool.org:3333`, `stratum+tcp://eusolo.ckpool.org:3333`, `stratum+tcp://stratum.ckpool.org:3333` |

## 2. Get the code (Terminal)

Open **Terminal** (Spotlight, type "Terminal"). Install Homebrew if this is a brand-new Mac (it asks for your Mac password and may install the Command Line Tools):

```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
eval "$(/opt/homebrew/bin/brew shellenv)"
```

Then fetch the repository (GitHub asks you to sign in once):

```
brew install gh
gh auth login
mkdir -p ~/HYBA && gh repo clone hybadatadevops1/Chronusv2 ~/HYBA/Chronusv2
```

If you prefer not to use `gh`: download the repository ZIP from GitHub in the browser, unzip it, and move the folder to `~/HYBA/Chronusv2`.

## 3. Run the one setup command

```
cd ~/HYBA/Chronusv2 && bash scripts/mine/setup_mac.sh
```

It asks you, in this order:

1. **Pool** for this Mac (press Enter for `viabtc`).
2. **Username** and **password** for that pool. They are stored in your macOS Keychain (item "HYBA Mine pool login") and nowhere else.
3. **Approval**: type `APPROVE` to allow HYBA Mine to mine on this Mac.
4. It runs the **pre-flight**. Every line must say PASS: known-answer tests on six real Bitcoin block headers on the Chronus iGPU, your login present, the ledger intact, and a live handshake with the pool. If anything fails, nothing mines; the FAIL line says why. If only the Metal lane failed, the script offers to mine on the Chronus iGPU in Mode A instead.
5. **Auto-start**: answer Enter (yes) to run HYBA Mine in the background now and at every login.

Skip the questions with options, for example: `bash scripts/mine/setup_mac.sh --pool braiins --autostart`.

## 4. Watch it

```
~/.hyba-mine/bin/hyba-mine status
```

or open <http://127.0.0.1:8765/> in Safari. Every value comes from the local ledger:

- **Route and backend**: the requested backend and preference, the backends detected on this Mac, the backend that actually ran (`igpu` or `metal`), and the reason if it differs from the preference.
- **Hashrate**: executed candidates divided by device time over the last 60 seconds of recorded work, and the effective rate (the same candidates divided by the wall-clock time those records cover, so time spent outside the device counts against it). "Not measured" means no device work was recorded in that window.
- **Shares**: submitted, accepted and rejected. Accepted and rejected count only the pool's replies; a share without a reply shows as awaiting or unacknowledged, never as accepted.
- **Current job, pool, uptime** and the pool's last literal reply.

To make `hyba-mine` available as a plain command, add this line to `~/.zshrc`: `export PATH="$HOME/.hyba-mine/bin:$PATH"`.

## 4a. Choose the backend

Each run detects the backends and picks one from your option. See what this Mac offers and what would run:
```
~/.hyba-mine/bin/hyba-mine backends                      # default: --backend auto --prefer ours -> igpu
~/.hyba-mine/bin/hyba-mine backends --prefer host        # the Apple GPU (Metal) when it passes its tests
```
Make the choice the default for every start (and for the launch agent):
```
~/.hyba-mine/bin/hyba-mine config --backend auto --prefer ours   # Chronus iGPU (the default)
~/.hyba-mine/bin/hyba-mine config --backend auto --prefer host   # host GPU (Metal) when it passes
~/.hyba-mine/bin/hyba-mine config --backend metal                # exactly Metal, or refuse to mine
```
A named backend runs exactly there or fails closed. With `--fleet on` the units go to the Chronus iGPU fleet through HYBA Mine's kernel plugin (set `CHRONUS_FLEET_KERNELS=hyba_mine.fleet_kernel` on every fleet machine); each fleet machine runs the backend it chose at `chronus-fleet join --backend ... --prefer ...`.

## 5. Switch pool while mining

Store the other pool's login once, then switch (from Terminal or the status page):

```
~/.hyba-mine/bin/hyba-mine login braiins
~/.hyba-mine/bin/hyba-mine pool use braiins
```

The running miner switches between work units and records the switch in the ledger. A pool without a stored login is refused.

## 6. Stop it

| What | Command |
|---|---|
| Stop now (it starts again at the next login) | `~/.hyba-mine/bin/hyba-mine stop` |
| Stop and remove auto-start | `~/.hyba-mine/bin/hyba-mine stop --disable-autostart` |
| Start again in the background | `~/.hyba-mine/bin/hyba-mine autostart enable --run-script ~/HYBA/Chronusv2/scripts/mine/run.sh` |
| Run in a Terminal window instead | `bash ~/HYBA/Chronusv2/scripts/mine/run.sh` (stop with Ctrl-C) |
| Manual launchd stop | `launchctl bootout gui/$(id -u)/ae.hybadata.mine` |

## 7. Logs and files

- Logs: `~/Library/Logs/HYBA-Mine/hyba-mine.log` (rotated), plus `launchd.out.log` and `launchd.err.log` when auto-started.
- Ledger, settings and approval: `~/Library/Application Support/HYBA-Mine/` (`ledger.jsonl`; check it with `hyba-mine ledger verify`).
- Python environment: `~/.hyba-mine/venv`.
- Launch agent: `~/Library/LaunchAgents/ae.hybadata.mine.plist`. It runs `scripts/mine/run.sh`, restarts the miner after a crash or a failed pre-flight (at most every two minutes), and does not restart it after a clean stop.

While it runs, `run.sh` keeps the Mac from idle sleep (and from system sleep on power) with `caffeinate`. A MacBook still sleeps when its lid is closed (unless it is in clamshell mode with a display and power); mining pauses while it sleeps, and after waking HYBA Mine replaces the dead pool connection and fetches a fresh job before it hashes again.

## 8. Remove everything

```
~/.hyba-mine/bin/hyba-mine stop --disable-autostart
~/.hyba-mine/bin/hyba-mine logout viabtc        # repeat for each pool you stored
~/.hyba-mine/bin/hyba-mine revoke
rm -rf ~/.hyba-mine "$HOME/Library/Application Support/HYBA-Mine" ~/Library/Logs/HYBA-Mine
```

## 9. If the pre-flight fails

| FAIL line | What to do |
|---|---|
| pool login is stored on this machine | `hyba-mine login <pool>` |
| operator approval for this machine | `hyba-mine approve` |
| pool is not blocked by an earlier login rejection | the pool refused the login (during a pre-flight or while mining); store the right one with `hyba-mine login <pool>` |
| Stratum handshake: not run | fix the other FAIL lines first; the pool is not contacted until everything else passes |
| Stratum handshake | check the internet connection and the login; `hyba-mine config --tls off` uses the pool's plain TCP endpoints only |
| Metal lane builds / Metal KAT lines | mine on the Chronus iGPU: `hyba-mine config --backend igpu --prefer ours`, then start again; send the FAIL lines to HYBA engineering |
| `<backend> lane present` | that backend has no lane on this Mac; HYBA Mine fails closed rather than run elsewhere. Use `--backend auto` (or `igpu`, or `metal` on Apple Silicon) |
| ledger hash chain verifies | the ledger was edited or damaged; move `ledger.jsonl` aside (keep it) and start again |

Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
