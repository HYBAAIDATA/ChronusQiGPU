# Contributing to HYBAPhiMiner-project

## Identity

Configure your local identity for this project only:

```bash
git config --local user.name "Your Name"
git config --local user.email "you@example.com"
```

## Workflow

```bash
git switch main
git pull --ff-only
# make changes
git add <files>
git commit -m "scope: description"
git push
```

Branch from `main` for larger work and open a merge request.

## Standards

- Python: `black` (line length 88) + `flake8` must be clean.
- TypeScript: `npm run lint` (`tsc --noEmit`) must be 0 errors.
- Preserve `LUCAS WIRING` module headers. No shebang after docstrings.
- No explanatory-comment clutter; keep mathematical clarity.

## Verification (before push)

```bash
npm run lint
npm run build
python -m flake8 --count
python -m black --check .
python -m pytest tests/ -x -q
python -m unittest discover -s chronus/mla1517_platform/python
python3 scripts/re_paper_gate.py
```

A missing device must produce an unavailable / fail-closed gate. Never convert it to a pass.

## Security / Consensus

- Never commit secrets, keys, tokens, or `.env` (`.env*` is git-ignored except `.env.example`).
- Never bypass double-SHA256 or target comparison. Intelligence reorders/prunes search; it never fakes proofs.
- Every candidate block must verify `SHA256(SHA256(header)) <= target`.
- Stratum lifecycle transitions only via declared edge table.
- Production admin endpoints require `EUCLID_ADMIN_API_KEY` and fail closed.
