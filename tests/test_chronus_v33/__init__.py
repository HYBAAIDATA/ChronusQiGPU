# Marks test_chronus_v33 as a package so pytest's prepend import mode derives
# ``test_chronus_v33.test_gap_close`` instead of colliding with the repo-root
# ``tests/test_gap_close.py`` module of the same basename (the pattern already
# used by ``tests/euclid_dominance/__init__.py``).
