#!/usr/bin/env bash
# Check a deployment end to end: seed CSV files in S3, trigger the CronJob once, check the database.
set -euo pipefail

cd "$(dirname "$0")/.."

NS=pipeline
EXPECTED_FILES=3
EXPECTED_TRANSACTIONS=16
EXPECTED_FLAGGED=6

psql_count() {
  kubectl -n "$NS" exec postgres-0 -- psql -U pipeline -d pipeline -tAc "$1"
}

echo "== 1. Seed the S3 bucket with the demo CSV files"
kubectl -n "$NS" delete job seed-data --ignore-not-found
kubectl apply -f k8s/demo/seed-job.yaml
kubectl -n "$NS" wait --for=condition=complete job/seed-data --timeout=120s
kubectl -n "$NS" logs job/seed-data

echo "== 2. Trigger the CronJob now (same job template as the scheduled runs)"
RUN="pipeline-manual-$(date +%s)"
kubectl -n "$NS" create job --from=cronjob/pipeline "$RUN"
kubectl -n "$NS" wait --for=condition=complete "job/$RUN" --timeout=120s
kubectl -n "$NS" logs "job/$RUN"

echo "== 3. Check the data in the database"
files=$(psql_count "SELECT count(*) FROM processed_files")
transactions=$(psql_count "SELECT count(*) FROM transactions")
flagged=$(psql_count "SELECT count(*) FROM transactions WHERE flagged")
echo "files=$files transactions=$transactions flagged=$flagged"
[ "$files" = "$EXPECTED_FILES" ] && [ "$transactions" = "$EXPECTED_TRANSACTIONS" ] \
  && [ "$flagged" = "$EXPECTED_FLAGGED" ] || { echo "Unexpected database content" >&2; exit 1; }

echo "== 4. Run again: nothing must be processed twice"
RUN2="pipeline-manual-again-$(date +%s)"
kubectl -n "$NS" create job --from=cronjob/pipeline "$RUN2"
kubectl -n "$NS" wait --for=condition=complete "job/$RUN2" --timeout=120s
kubectl -n "$NS" logs "job/$RUN2"
[ "$(psql_count 'SELECT count(*) FROM transactions')" = "$EXPECTED_TRANSACTIONS" ] \
  || { echo "Duplicates after the second run" >&2; exit 1; }

echo "OK: deployment verified"
