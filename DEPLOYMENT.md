# EUCLID-CORE / PYTHIA — Docker Deployment Guide

## Quick Start

```bash
# 1. Build and start (CPU mode, 1 EH/s cap)
docker compose up -d

# 2. Check health
curl http://localhost:3000/api/health

# 3. View logs
docker compose logs -f pythia
```

## GPU Deployment

If you have NVIDIA GPUs and the NVIDIA Container Toolkit installed:

```bash
# Start with 4 GPUs
EUCLID_GPU_COUNT=4 docker compose up -d

# Or edit docker-compose.yml and uncomment the devices section
```

## Configuration

All configuration is via environment variables (set in docker-compose.yml or at runtime):

| Variable                  | Default    | Description                                               |
| ------------------------- | ---------- | --------------------------------------------------------- |
| `EUCLID_MINING_CAP_EHS`   | `10.0`     | Hashrate cap in EH/s. Max 10.0. Adjustable from frontend. |
| `EUCLID_HARDWARE_PROFILE` | `auto`     | `auto`, `m3_studio`, `docker`, `docker_gpu`               |
| `EUCLID_GPU_COUNT`        | `0`        | Number of GPUs (0 = CPU/Turing fallback)                  |
| `EUCLID_GPU_TYPE`         | `none`     | GPU type (auto-detected)                                  |
| `EUCLID_MAX_MEMORY_GB`    | `100`      | Available memory in GB                                    |
| `EUCLID_ADMIN_API_KEY`    | `changeme` | Admin API key (CHANGE in production)                      |
| `PORT`                    | `3000`     | Server port                                               |

## Hardware Profiles

### M3 Studio/Ultra (80-core GPU = 80 SMs × 128 lanes = 10,240 ALU lanes, 96GB) — original target

- Profile: `m3_studio`
- Backend: Metal
- Physical model: ~4.25 GH/s (`EUCLID_VGPU` topology: 10,240 lanes × 1.7 GHz boost / 4,096 cycles per SHA-256d)
- Cap: 10 EH/s

### Docker + NVIDIA GPU

- Profile: `docker_gpu`
- Backend: CUDA
- Physical: ~100 MH/s per GPU core
- Cap: configurable (default 1 EH/s)

### Docker + CPU (Turing exact-math fallback)

- Profile: `docker_cpu`
- Backend: CPU (Q[√5] rational core)
- Physical: ~1 MH/s per CPU core
- Cap: configurable (default 1 EH/s)
- The Lucas scaling (L_10=123x) amplifies effective search efficiency

## Safety Guarantees

- **Hashrate cap**: enforced server-side. Frontend can request changes but
  cannot exceed the hard cap.
- **Never two consecutive blocks**: after a block is accepted, PYTHIA waits
  for an external block before mining again.
- **One block then wait**: mine one block, submit, wait for acceptance,
  enter cooldown.
- **Blockchain safety is paramount**: all safety constraints are
  non-bypassable.

## Storage

- `pythia_memory` volume: persistent PYTHIA memory + superposition state
- `blockdata` mount: read-only block data feed (mount your block data here)

## Scaling to 10 EH/s

The hashrate cap is adjustable from the frontend up to the absolute hard
cap of 10 EH/s. The frontend can never exceed this — requests above 10
EH/s are automatically clamped.

To reach 10 EH/s effective hashrate, the Lucas scaling ladder must amplify
the physical hashrate. The Intelligence layer ladder goes to L_20 (15127x),
but the pool profiles in `m3_igpu_scaler.ts` extend further:

| Lucas Scale | Value        | 4.25 GH/s physical → effective |
| ----------- | ------------ | ------------------------------ |
| L_10        | 123          | 522.8 GH/s                     |
| L_15        | 1,364        | 5.8 TH/s                       |
| L_20        | 15,127       | 64.3 TH/s                      |
| L_41        | 370,248,451  | 1.57 EH/s                      |
| L_45        | 2,537,720,636 | 10.8 EH/s (capped at 10)      |
| L_50        | 28,143,753,123 | 119.6 EH/s (capped at 10)    |

So even a modest physical hashrate (4.25 GH/s on M3 Ultra, or higher
hybrid with cloud GPUs) can reach 10 EH/s with sufficient Lucas scaling
(L_45+). Valid scale indices are restricted to the ladder rungs
{10,12,15,18,20,31,50,76} and their multiples. The pool profiles enforce
their own ceilings (ViaBTC: 300 EH/s, Braiins: 20 EH/s).

### Hybrid deployment (local GPU + Docker CPU + cloud GPU)

Set `EUCLID_HARDWARE_PROFILE=hybrid` and `EUCLID_CLOUD_GPU_COUNT=N` to
combine:

1. Local AMD Radeon iGPU (~500 MH/s)
2. Docker CPU 100GB (Turing Q[√5] exact-math, ~8 MH/s)
3. N cloud GPUs (~10.3 GH/s each, RTX 4090-class)

The physical hashrates are summed, then amplified by the Lucas scaling.
