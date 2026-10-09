set -eu
for kind in native portable; do
 python -m venv /data/product-closure/venv-$kind
 /data/product-closure/venv-$kind/bin/python -m pip install /data/product-closure/build/$kind/*.whl 'pytest>=8,<10' > /data/product-closure/install-$kind.log 2>&1
 mkdir -p /data/product-closure/installed-tests-$kind
 cp /data/hendrix-elevation/chronos-completed/tests/test_exact_evolution_replacement.py /data/product-closure/installed-tests-$kind/
 cd /data/product-closure/installed-tests-$kind
 env -u PYTHONPATH /data/product-closure/venv-$kind/bin/python -c 'import chronos_one_igpu,sys; print(chronos_one_igpu.__file__); assert "site-packages" in chronos_one_igpu.__file__' > /data/product-closure/import-$kind.log
 env -u PYTHONPATH /data/product-closure/venv-$kind/bin/python -m pytest -q --junitxml=/data/product-closure/installed-evolution-$kind.xml > /data/product-closure/installed-evolution-$kind.log 2>&1
 PYTHONPATH=/data/hendrix-elevation/test-support:/data/quantumphi-canonical:/data/quantumphi-canonical/turing_universal_quantum_computer /data/product-closure/venv-$kind/bin/python -m pytest /data/quantumphi-canonical/tests/test_exact_geometry.py /data/quantumphi-canonical/tests/test_resident_hendrix.py /data/quantumphi-canonical/tests/test_production_replacement_attacks.py -q --junitxml=/data/product-closure/installed-route-$kind.xml > /data/product-closure/installed-route-$kind.log 2>&1
 tail -2 /data/product-closure/installed-evolution-$kind.log; tail -2 /data/product-closure/installed-route-$kind.log
done
