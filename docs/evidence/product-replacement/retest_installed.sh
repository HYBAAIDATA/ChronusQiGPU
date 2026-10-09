set -eu
for kind in native portable; do
 cp /data/product-closure/installed-evolution-$kind.log /data/product-closure/initial-installed-evolution-$kind.log
 if test -f /data/product-closure/installed-route-$kind.log; then cp /data/product-closure/installed-route-$kind.log /data/product-closure/initial-installed-route-$kind.log; fi
 /data/product-closure/venv-$kind/bin/python -m pip install --force-reinstall --no-deps /data/product-closure/build/$kind/*.whl > /data/product-closure/reinstall-$kind.log 2>&1
 cp /data/hendrix-elevation/chronos-completed/tests/test_exact_evolution_replacement.py /data/product-closure/installed-tests-$kind/
 cd /data/product-closure/installed-tests-$kind
 env -u PYTHONPATH /data/product-closure/venv-$kind/bin/python - <<'PY' > /data/product-closure/import-final-$kind.json
import json,hashlib,chronos_one_igpu
from pathlib import Path
import chronos_one_igpu.igpu.exact_quantum as exact
import chronos_one_igpu.igpu.virtual_abi as abi
src=Path('/data/hendrix-elevation/chronos-completed/src/chronos_one_igpu/igpu')
for m in [exact,abi]:
 assert 'site-packages' in m.__file__
 assert Path(m.__file__).read_bytes()==(src/Path(m.__file__).name).read_bytes()
print(json.dumps({'package':chronos_one_igpu.__file__,'modules':{m.__name__:hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()for m in [exact,abi]}}))
PY
 env -u PYTHONPATH /data/product-closure/venv-$kind/bin/python -m pytest -q --junitxml=/data/product-closure/installed-evolution-$kind.xml > /data/product-closure/installed-evolution-$kind.log 2>&1
 PYTHONPATH=/data/hendrix-elevation/test-support:/data/quantumphi-canonical:/data/quantumphi-canonical/turing_universal_quantum_computer /data/product-closure/venv-$kind/bin/python -m pytest /data/quantumphi-canonical/tests/test_exact_geometry.py /data/quantumphi-canonical/tests/test_resident_hendrix.py /data/quantumphi-canonical/tests/test_production_replacement_attacks.py -q --junitxml=/data/product-closure/installed-route-$kind.xml > /data/product-closure/installed-route-$kind.log 2>&1
 tail -2 /data/product-closure/installed-evolution-$kind.log; tail -2 /data/product-closure/installed-route-$kind.log
done
