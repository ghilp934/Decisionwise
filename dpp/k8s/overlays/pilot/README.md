# DPP Pilot Overlay

Cost-capped Kubernetes configurations for pilot/preview environments.

## Deployment Profiles

| Resource | Production (`k8s/worker-deployment.yaml`) | Pilot (`overlays/pilot/worker-deployment-pilot.yaml`) |
|----------|------------------------------------------|-------------------------------------------------------|
| **Namespace** | `dpp-production` | `dpp-pilot` |
| **Initial Replicas** | 5 | 1 |
| **HPA Min/Max** | 5-10 | 1-3 |
| **CPU Request** | 4000m (4 cores) | 1000m (1 core) |
| **CPU Limit** | 4000m | 2000m (2 cores) |
| **Memory Request** | 8Gi | 1Gi |
| **Memory Limit** | 8Gi | 2Gi |
| **Scale Up Stabilization** | 60s | 60s |
| **Scale Down Stabilization** | 300s (5min) | 180s (3min) |

## Cost Impact

**Production**: ~5-10 pods × 4 CPU × 8Gi = 20-40 CPU cores, 40-80 Gi RAM

**Pilot**: ~1-3 pods × 1 CPU × 1Gi = 1-3 CPU cores, 1-3 Gi RAM

**Estimated Cost Reduction**: ~90-95% for pilot environments

## Usage

### Deploy to Pilot Environment

```bash
# Apply pilot worker deployment
kubectl apply -f k8s/overlays/pilot/worker-deployment-pilot.yaml

# Verify deployment
kubectl get deployment -n dpp-pilot
kubectl get hpa -n dpp-pilot
```

### Deploy to Production Environment

```bash
# Apply production worker deployment
kubectl apply -f k8s/worker-deployment.yaml

# Verify deployment
kubectl get deployment -n dpp-production
kubectl get hpa -n dpp-production
```

## Notes

- Pilot overlay is **cost-optimized** for preview/testing environments
- Production profile is **performance-optimized** for high-throughput workloads
- Both profiles use the same Docker image (only resource allocation differs)
- Ensure `dpp-pilot` namespace exists before deploying pilot overlay
