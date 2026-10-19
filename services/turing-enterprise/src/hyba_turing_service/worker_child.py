"""No network listener or keys; stdin is the admitted QASM request."""

import json
import sys


def main():
    from .adapters import TuringPipelineRuntime

    request = json.loads(sys.stdin.buffer.read(131073))
    # Enforce the same boundary even if a worker is invoked outside the API.
    from .control import ControlPlane

    request = ControlPlane._request(request)
    report = TuringPipelineRuntime().run(request)
    sys.stdout.write(json.dumps(report, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
