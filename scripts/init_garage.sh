#!/usr/bin/env bash
# Initialise a single-node Garage: layout, bucket, access key. Idempotent.
# Writes S3_ACCESS_KEY / S3_SECRET_KEY into $ENV_FILE (default .env, created from .env.example).
#
# Targets the docker compose Garage by default. Override GARAGE_CMD to target another one, e.g.
#   GARAGE_CMD="kubectl -n pipeline exec garage-0 -- /garage" ENV_FILE=/tmp/k8s.env ./scripts/init_garage.sh
set -euo pipefail

cd "$(dirname "$0")/.."

BUCKET="${S3_BUCKET:-transactions}"
KEY_NAME="pipeline-key"
G="${GARAGE_CMD:-docker compose exec -T garage /garage}"
ENV_FILE="${ENV_FILE:-.env}"

[ -f "$ENV_FILE" ] || cp .env.example "$ENV_FILE"

echo "Waiting for Garage..."
for _ in $(seq 1 30); do
  $G status >/dev/null 2>&1 && break
  sleep 1
done
$G status >/dev/null

NODE_ID=$($G status | awk '/==== HEALTHY NODES ====/{f=1;next} f&&NF&&$1!="ID"{print $1; exit}')

if ! $G layout show | grep -q "$NODE_ID"; then
  $G layout assign -z dc1 -c 1G "$NODE_ID"
  $G layout apply --version 1
fi

$G bucket create "$BUCKET" 2>/dev/null || true

if ! $G key info "$KEY_NAME" >/dev/null 2>&1; then
  $G key create "$KEY_NAME" >/dev/null
fi
$G bucket allow --read --write --owner "$BUCKET" --key "$KEY_NAME" >/dev/null

INFO=$($G key info "$KEY_NAME" --show-secret)
ACCESS=$(echo "$INFO" | awk '/Key ID:/{print $3}')
SECRET=$(echo "$INFO" | awk '/Secret key:/{print $3}')

sed -i.bak -e "s|^S3_ACCESS_KEY=.*|S3_ACCESS_KEY=$ACCESS|" \
           -e "s|^S3_SECRET_KEY=.*|S3_SECRET_KEY=$SECRET|" "$ENV_FILE" && rm -f "$ENV_FILE.bak"

echo "Garage ready: bucket=$BUCKET key=$ACCESS"
