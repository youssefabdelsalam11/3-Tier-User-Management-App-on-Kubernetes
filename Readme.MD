# 3-Tier User Management App on Kubernetes

A user management web app (add, list, delete users) deployed as three containerized tiers on a 2-node **kubeadm** Kubernetes cluster with **Calico** networking.

```
                 ┌────────────────────────── Kubernetes cluster ──────────────────────────┐
                 │                                                                          │
 Browser ──────► │  frontend Service ──► Nginx pods ──/api──► backend Service ──► Flask pods │
 (NodePort)      │                       (2 replicas)                            (2 replicas)│
                 │                                                                   │      │
                 │                                          mysql Service ◄──────────┘      │
                 │                                                │                         │
                 │                                          MySQL pod ──► PVC ──► PV        │
                 └──────────────────────────────────────────────────────────────────────────┘
```

## Tech stack

| Tier     | Technology                                         | Image                                  |
| -------- | -------------------------------------------------- | -------------------------------------- |
| Frontend | HTML/JS served by Nginx (reverse proxy for `/api`) | `youssefabdelsalllam1/my-frontend-app` |
| Backend  | Python 3.10, Flask, Flask-CORS, mysql-connector    | `my-backend-app`                       |
| Database | MySQL 8.0 with persistent storage                  | `mysql:8.0`                            |

## Project structure

```
.
├── backend/
│   ├── app.py                  # Flask REST API
│   ├── requirements.txt
│   └── Dockerfile
├── database/
│   └── init.sql                # Creates the users table and seed data
├── frontend/
│   ├── index.html              # UI
│   ├── nginx.conf              # Serves the UI and proxies /api to the backend
│   └── Dockerfile
└── k8s/
    ├── app-config.yaml         # ConfigMap (DB host, port, name)
    ├── mysql-secret.example.yaml   # Secret template (real one is git-ignored)
    ├── my-pv.yaml              # PersistentVolume
    ├── my-pvc.yaml             # PersistentVolumeClaim
    ├── database-deployment.yaml
    ├── database-svc.yaml
    ├── backend-deployment.yaml
    ├── backend-svc.yaml
    ├── frontend-deployment.yaml
    └── frontend-svc.yaml
```

## 1. Dockerized images

Each tier has its own Dockerfile.

**Frontend** (`frontend/Dockerfile`): Nginx serves `index.html` and forwards `/api/*` to the backend Service.

```dockerfile
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html
EXPOSE 80
```

**Backend** (`backend/Dockerfile`): Flask API on port 5000.

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["python", "app.py"]
```

**Database**: uses the official `mysql:8.0` image. The schema is loaded from `database/init.sql` through a ConfigMap (see below).

### Build the images

```bash
# Frontend (pushed to Docker Hub so every node can pull it)
docker build -t youssefabdelsalllam1/my-frontend-app:latest ./frontend
docker push youssefabdelsalllam1/my-frontend-app:latest

# Backend (built locally; the Deployment uses imagePullPolicy: Never)
docker build -t my-backend-app:latest ./backend
```

If the cluster has more than one node, the backend image must exist on every node that can run it. Either push it to a registry and remove `imagePullPolicy: Never`, or export and import it per node:

```bash
docker save my-backend-app:latest -o backend.tar
ctr -n k8s.io images import backend.tar     # run on each node
```

## 2. Deployments and Services

Each component has a Deployment (runs the pods) and a Service (stable network endpoint).

| Component | Deployment | Replicas                | Service    | Type                 | Port |
| --------- | ---------- | ----------------------- | ---------- | -------------------- | ---- |
| Frontend  | `frontend` | 2                       | `frontend` | NodePort             | 80   |
| Backend   | `backend`  | 2                       | `backend`  | NodePort / ClusterIP | 5000 |
| Database  | `db`       | 1 (`Recreate` strategy) | `mysql`    | ClusterIP            | 3306 |

How they connect:

- The browser talks only to the **frontend** Service.
- Nginx forwards `/api/*` to `http://backend:5000`.
- The backend reaches MySQL at `mysql:3306` through cluster DNS.
- The database pod mounts a PersistentVolumeClaim at `/var/lib/mysql`, so data survives pod restarts.

### Persistent storage

`my-pv.yaml` defines a 1Gi `hostPath` volume at `/mnt/data`, and `my-pvc.yaml` claims it. This is suitable for a single-node lab. Use a real StorageClass in production.

## 3. ConfigMaps and Secrets

### ConfigMap: application settings

`k8s/app-config.yaml` holds non-sensitive settings, injected into the backend as environment variables:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  DB_HOST: mysql
  DB_PORT: "3306"
  DB_NAME: mydb
```

### ConfigMap: database init script

The MySQL image runs any `.sql` file in `/docker-entrypoint-initdb.d/` on first start. The script is stored as a ConfigMap and mounted there:

```bash
kubectl create configmap mysql-init --from-file=database/init.sql
```

### Secret: database credentials

Credentials are stored in a Kubernetes Secret and injected as `DB_USER` and `DB_PASSWORD` (backend) and `MYSQL_ROOT_PASSWORD` (database). The real `mysql-secret.yaml` is **not committed** (see `.gitignore`). Create your own from the template:

```bash
cp k8s/mysql-secret.example.yaml k8s/mysql-secret.yaml
echo -n 'root' | base64             # use as username
echo -n 'YourStrongPass' | base64   # use as password
```

Or create it directly:

```bash
kubectl create secret generic mysql-secret \
  --from-literal=username=root \
  --from-literal=password='YourStrongPass'
```

> Base64 is encoding, not encryption. For real environments use sealed secrets or an external secret manager.

## Deploy

Run from the repository root, in this order:

```bash
# 1. Configuration
kubectl apply -f k8s/app-config.yaml
kubectl apply -f k8s/mysql-secret.yaml
kubectl create configmap mysql-init --from-file=database/init.sql

# 2. Storage
kubectl apply -f k8s/my-pv.yaml
kubectl apply -f k8s/my-pvc.yaml

# 3. Database, then backend, then frontend
kubectl apply -f k8s/database-deployment.yaml -f k8s/database-svc.yaml
kubectl apply -f k8s/backend-deployment.yaml  -f k8s/backend-svc.yaml
kubectl apply -f k8s/frontend-deployment.yaml -f k8s/frontend-svc.yaml
```

Check that everything is running:

```bash
kubectl get pods,svc,pvc
```

## Access and test

Find the frontend NodePort:

```bash
kubectl get svc frontend
```

Open `http://<node-ip>:<frontend-nodeport>` in your browser. Test the API through the frontend:

```bash
curl http://<node-ip>:<frontend-nodeport>/api/health
# {"database":"connected","status":"healthy"}

curl http://<node-ip>:<frontend-nodeport>/api/users
```

Verify persistence by deleting the database pod and refreshing the page. The users should still be there:

```bash
kubectl delete pod -l app=db
```

## API endpoints

| Method | Path              | Description                                   |
| ------ | ----------------- | --------------------------------------------- |
| GET    | `/api`            | Hello message                                 |
| GET    | `/api/health`     | Health check, including database connectivity |
| GET    | `/api/users`      | List users                                    |
| POST   | `/api/users`      | Add a user (`name` and `email` required)      |
| DELETE | `/api/users/<id>` | Delete a user                                 |

## Troubleshooting

Problems I hit while building this, and how I fixed them:

| Symptom                                                             | Cause                                                                                                   | Fix                                                                                                                 |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| UI shows "Network error: Failed to fetch"                           | `index.html` called `http://localhost:5000`, which in a browser means the user's own machine            | Use a relative `/api` URL and proxy it through Nginx to the backend Service                                         |
| Backend: `Unknown MySQL server host 'mysql'`                        | Pods could not reach cluster DNS because `calico-node` was not Ready and firewalld was blocking traffic | Stopped/disabled firewalld on both nodes and restarted Calico; used the Service ClusterIP as a workaround meanwhile |
| Frontend `CrashLoopBackOff`: `host not found in upstream "backend"` | Nginx resolves the upstream name at startup, and DNS was down                                           | Fixed cluster DNS (above)                                                                                           |
| MySQL ignores new password or init script                           | `hostPath` volume already contained an initialized data directory                                       | Init variables and scripts only run on an empty data directory; wipe `/mnt/data` for a fresh start                  |

Useful commands:

```bash
kubectl logs -l app=backend --tail=30
kubectl describe pod -l app=db
kubectl get endpoints
kubectl get pods -n kube-system        # Calico and CoreDNS health
```

## Cleanup

```bash
kubectl delete -f k8s/
kubectl delete configmap mysql-init
```

## Notes and next steps

- This is a lab setup. The Flask app runs in debug mode and connects to MySQL as `root`. A production setup should use a WSGI server (Gunicorn), a dedicated database user, and resource limits.
- Planned: a Jenkins CI/CD pipeline that builds the images, pushes them to Docker Hub, and deploys to the cluster.

## Author

**Youssef Ahmed Abdelsalam**: [GitHub](https://github.com/youssefabdelsalam11)
