#!/usr/bin/env python3
"""Static deployment gate for cross-service shared /dev/shm visibility."""
from pathlib import Path
text = Path('docker-compose.yml').read_text()
for service in ('mla1517-coordinator:', 'prime-db:', 'telemetry:', 'salamander:'):
    assert service in text, service
assert text.count('target: /dev/shm') == 4
assert text.count('source: mla1517_shm') == 4
assert 'type: tmpfs' in text and 'device: tmpfs' in text
print('{"status":"PASS","shared_shm":true,"services":4}')
