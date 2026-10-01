"""Cloud (Kubernetes) manifest emitter."""
from typing import Dict


MANIFEST_TEMPLATE = (
    "apiVersion: apps/v1\n"
    "kind: Deployment\n"
    "metadata:\n"
    "  name: hyba-phi\n"
    "  labels:\n"
    "    app: hyba-phi\n"
    "spec:\n"
    "  replicas: {replicas}\n"
    "  selector:\n"
    "    matchLabels:\n"
    "      app: hyba-phi\n"
    "  template:\n"
    "    metadata:\n"
    "      labels:\n"
    "        app: hyba-phi\n"
    "    spec:\n"
    "      containers:\n"
    "      - name: substrate\n"
    "        image: {image}\n"
    "        resources:\n"
    "          requests:\n"
    "            cpu: \"2\"\n"
    "            memory: \"4Gi\"\n"
    "          limits:\n"
    "            cpu: \"4\"\n"
    "            memory: \"8Gi\"\n"
)


class KubernetesManifest:
    """Emit a Kubernetes Deployment manifest for the substrate."""

    def emit(self, replicas: int = 4, image: str = "hyba-phi:0.3.2") -> str:
        return MANIFEST_TEMPLATE.format(replicas=replicas, image=image)

    def status(self) -> Dict:
        return {"target": "kubernetes", "available": True}
