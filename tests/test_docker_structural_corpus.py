"""Static Docker context checks; these do not claim a Docker build/run."""
from pathlib import Path
from Intelligence.mining_structure_training import DEFAULT_CORPUS_CSV, DEFAULT_CORPUS_MANIFEST, load_nonce_corpus

ROOT = Path(__file__).resolve().parents[1]


def test_required_corpus_is_hash_verified():
    rows, manifest = load_nonce_corpus(DEFAULT_CORPUS_CSV, DEFAULT_CORPUS_MANIFEST)
    assert len(rows) == manifest['row_count'] == 200


def test_docker_context_explicitly_preserves_required_corpus():
    rules = (ROOT / '.dockerignore').read_text().splitlines()
    assert 'artifacts' not in rules
    assert 'artifacts/*' in rules
    assert '!artifacts/pythia_training/' in rules
    for name in ('real_nonces_200.csv', 'real_nonces_200.manifest.json'):
        assert f'!artifacts/pythia_training/{name}' in rules
        assert (ROOT / 'artifacts/pythia_training' / name).is_file()
    assert 'COPY . .' in (ROOT / 'Dockerfile').read_text()
