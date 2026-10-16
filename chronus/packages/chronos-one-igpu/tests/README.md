# tests/

`test_self_tests.py` wraps this codebase's real module self-tests (the same
`_self_test()` / `self_test_all()` / `ChronosTestHarness` functions used
throughout development) as pytest test functions, so `pytest` becomes a
single standard entry point.

```bash
pip install -r requirements.txt
PYTHONPATH=src pytest tests/ -v
```

If you don't have `pytest` installed, every test here calls a function you
can run directly without it, e.g.:

```bash
PYTHONPATH=src python3 -c "from chronos.theory.report import self_test_all; print(self_test_all())"
PYTHONPATH=src python3 -m chronos.test_harness
PYTHONPATH=src python3 -m chronos.qsdl_compiler
```
