# Enterprise Cloud & Whitelabel Workstation Architecture

# Enterprise Cloud & Whitelabel Workstation Architecture

## 1. Multi-Cloud Kubernetes & Docker Deployments

The AL HARAS substrate and CIaaS interface are fully dockerized and orchestrated for multi-cloud deployments.

- **Docker Compose (`docker-compose.yml`):** Deploys the full stack locally or on single nodes, orchestrating `hyba-backend`, `hyba-frontend`, and `hyba-telemetry` (Prometheus) with direct GPU reservations.
- **AWS EKS (`eks-deployment.yaml`):** Scaled deployment targeting `p4d.24xlarge` nodes.
- **Azure AKS (`aks-deployment.yaml`):** Scaled deployment targeting `nvidia-a100` nodes.
- **Google GKE (`gke-deployment.yaml`):** Scaled deployment targeting `nvidia-tesla-a100` nodes.
- **CI/CD (`.github/workflows/multicloud_deploy.yml`):** Fully automates building the `Dockerfile.prod` image and applying the respective Kubernetes manifests across all three hyperscalers.

## 2. Whitelabel Workstation UI

The client-facing frontend has been completely rewritten into a **Whitelabel Workstation**, built in React (`frontend/src/WhitelabelWorkstation.tsx`).

### Enterprise Error Handling & Tooltips

- **`ErrorBoundary.tsx`:** Wraps critical UI components. If the substrate interface fails or detects a desync, it cleanly catches the exception, preventing a white screen, and provides an "Attempt Recovery" action to re-initialize the connection.
- **`Tooltip.tsx`:** Provides hover-context for complex physics telemetry, ensuring that enterprise administrators understand the mathematical metrics without needing a physics degree.

### Management & Control Plane

The workstation includes a dedicated `ManagementControlTab.tsx` providing real-time oversight of the substrate:

- **Hermitian Telemetry Stream:** Displays the real-time Navier-Stokes Vorticity ($\omega$), Unitary Drift Epsilon ($\epsilon$), Homological Anomaly Betti-1 ($\beta_1$), and CBF-QP Filter Latency. Tooltips explain the exact threshold bounds.
- **Substrate Controls:** Provides actionable buttons to `[FORCE TOPOLOGY DROP]`, `[EXPORT ZK BILLING PROOF]`, and `[RELOAD CBF ENVELOPES]`.
- **Whitelabeling:** Includes dynamic tenant naming ("Whitelabel Active") allowing banking or defense clients to rebrand the dashboard interface entirely to their internal security nomenclature.