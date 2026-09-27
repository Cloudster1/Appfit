# Appfit Helm chart

Deploys Appfit to Kubernetes:
- **backend:** FastAPI API with the embedding model.
- **frontend:** nginx, which serves the UI and proxies `/api` to the backend.
- **postgresql** (optional): PostgreSQL 17 with pgvector.
- **worker** (optional): a separate embedding worker.

Kubernetes 1.27 or newer. The pods meet the "restricted" Pod Security Standard.

## Install

1. Build the images and push them to a registry the cluster can pull from:
   ```bash
   docker build -t registry.example.com/appfit/backend:0.1.0 backend
   docker build -t registry.example.com/appfit/frontend:0.1.0 --target prod frontend
   docker push registry.example.com/appfit/backend:0.1.0
   docker push registry.example.com/appfit/frontend:0.1.0
   ```
2. Install the chart:
   ```bash
   helm install appfit deploy/helm/appfit -n appfit --create-namespace \
     --set backend.image.repository=registry.example.com/appfit/backend \
     --set frontend.image.repository=registry.example.com/appfit/frontend
   ```
3. Follow the printed notes. They say how to open the UI and read the generated admin password:
   ```bash
   kubectl -n appfit get secret appfit-auth -o jsonpath='{.data.BOOTSTRAP_ADMIN_PASSWORD}' | base64 -d; echo
   ```
4. Check the deployment with `helm test appfit -n appfit`. The test calls the UI, `/api/health/ready`, and a protected endpoint.

The first start downloads the embedding model (about 2.2 GB) into the model cache volume.
- The API pods become ready once it is loaded.
- Catalog and keyword search work before that.
- Matching answers 503 until the model is loaded.

For a complete example, see [`ci/production-values.yaml`](ci/production-values.yaml). It covers a registry, TLS ingress, two replicas, a separate worker, a shared cache and existing secrets.

## What happens at startup

- Each backend pod waits for the database (`appfit wait-for-db`) and then runs the migrations.
- Replicas that start together take a PostgreSQL advisory lock, so only one migrates. The others then find the schema up to date.
- While the users table is empty, the backend creates the admin `auth.bootstrapAdmin.email`.

## Values

| Key | Default | Description |
|---|---|---|
| `backend.image.repository` / `.tag` | `appfit-backend` / appVersion | API image |
| `backend.replicaCount` | `1` | API pods; each loads the model (about 2.5 GB memory) |
| `backend.strategy` | auto | `Recreate` while the model cache is ReadWriteOnce, else `RollingUpdate` |
| `backend.resources` | 500m / 3Gi, limit 4Gi | |
| `backend.startupProbe`, `.livenessProbe`, `.readinessProbe` | | `periodSeconds`, `failureThreshold` |
| `backend.extraEnv`, `.extraEnvFrom` | `[]` | extra environment for the API pods |
| `worker.enabled` | `false` | run the embedding worker as its own Deployment; the API pods then stop embedding |
| `frontend.image.repository` / `.tag` | `appfit-frontend` / appVersion | UI image (nginx, port 8080, non-root) |
| `frontend.replicaCount` | `1` | |
| `config.embeddingBackend` | `sentence_transformers` | `fake` skips the model (tests and demos only) |
| `config.embeddingModel`, `.embeddingModelRevision` | `BAAI/bge-m3`, `""` | pin a revision for reproducible embeddings |
| `config.embeddingDevice` | `cpu` | `cuda` needs a CUDA build of the image |
| `config.hfHubOffline` | `false` | `true` once the model is cached: no access to the model hub |
| `config.cookieSecure` | auto | `true` when the ingress has TLS |
| `config.extra` | `{}` | any other setting as environment variables, e.g. `MATCH_T_COVERED` |
| `auth.existingSecret` | `""` | Secret with `JWT_SECRET` and `BOOTSTRAP_ADMIN_PASSWORD` |
| `auth.jwtSecret`, `auth.bootstrapAdmin.password` | generated | kept across upgrades |
| `auth.bootstrapAdmin.email` | `admin@example.com` | |
| `modelCache.persistence.enabled` | `true` | `false` uses an emptyDir: every pod start downloads the model |
| `modelCache.persistence.accessModes` | `[ReadWriteOnce]` | `ReadWriteMany` lets pods on several nodes share it and enables rolling updates |
| `modelCache.persistence.size`, `.storageClass`, `.existingClaim` | `5Gi` | |
| `postgresql.enabled` | `true` | built-in PostgreSQL with pgvector |
| `postgresql.auth.database`, `.username` | `appfit` | |
| `postgresql.auth.password` | generated | URL-safe characters only (it becomes part of the database URL) |
| `postgresql.auth.existingSecret` | `""` | Secret with `POSTGRES_PASSWORD` |
| `postgresql.persistence.size`, `.storageClass` | `10Gi` | |
| `externalDatabase.url` | `""` | SQLAlchemy URL, `postgresql+psycopg://user:pass@host:5432/db` |
| `externalDatabase.existingSecret`, `.existingSecretKey` | `""`, `DATABASE_URL` | Secret with the URL |
| `ingress.enabled`, `.className`, `.annotations`, `.hosts`, `.tls` | disabled | routes everything to the frontend |
| `imagePullSecrets`, `serviceAccount.*` | | |
| `podSecurityContext`, `securityContext` | restricted | non-root, read-only root filesystem, no capabilities |
| `*.nodeSelector`, `*.tolerations`, `*.affinity`, `*.podAnnotations` | | per component |

`values.schema.json` validates all values on install.

## Operations

- **External database:** set `postgresql.enabled=false` and `externalDatabase.url` (or `.existingSecret`).
  - The server needs the pgvector extension installed.
  - The user must be allowed to run `CREATE EXTENSION vector`, or an administrator creates the extension beforehand.
- **Uninstall:** `helm uninstall` keeps some resources on purpose, so a reinstall under the same release name picks them up:
  - the generated Secrets
  - the model cache
  - the PostgreSQL volume

  To remove everything, delete them as well:
  ```bash
  kubectl -n appfit delete secret appfit-auth appfit-postgresql
  kubectl -n appfit delete pvc appfit-model-cache data-appfit-postgresql-0
  ```
- **Upload size:** imports are limited to 12 MB by the frontend's nginx. With ingress-nginx, also set `nginx.ingress.kubernetes.io/proxy-body-size: 12m`.
- **Backups:**
  ```bash
  kubectl -n appfit exec appfit-postgresql-0 -- pg_dump -U appfit -Fc appfit > appfit.dump
  ```
- **Air-gapped clusters:**
  1. Fill the model cache once (a start with internet access, or `appfit download-model` in a pod).
  2. Set `config.hfHubOffline=true`.

## Testing the chart

```bash
make helm-lint   # helm lint and kubeconform for every file in ci/
make helm-kind   # builds the images, installs into a local kind cluster (restricted namespace), runs helm test
```
