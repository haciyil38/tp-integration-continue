#!/usr/bin/env bash
# Deploy the whole stack to the current Kubernetes context: Postgres, Garage, the pipeline CronJob.
# Idempotent. Works on a kind cluster (CI) as on any other cluster.
set -euo pipefail

cd "$(dirname "$0")/.."

NS=pipeline
ENV_FILE="$(mktemp)"
trap 'rm -f "$ENV_FILE"' EXIT
cp .env.example "$ENV_FILE" # init_garage.sh fills in the S3 keys

kubectl apply -k k8s/

kubectl -n "$NS" rollout status statefulset/postgres --timeout=180s
kubectl -n "$NS" rollout status statefulset/garage --timeout=180s

# Layout, bucket and access key of Garage (the key stays out of the repository).
GARAGE_CMD="kubectl -n $NS exec garage-0 -- /garage" ENV_FILE="$ENV_FILE" ./scripts/init_garage.sh

# shellcheck disable=SC1090
. "$ENV_FILE"
kubectl -n "$NS" create secret generic s3-credentials \
  --from-literal=S3_ACCESS_KEY="$S3_ACCESS_KEY" \
  --from-literal=S3_SECRET_KEY="$S3_SECRET_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "Deployed. CronJob:"
kubectl -n "$NS" get cronjob pipeline
