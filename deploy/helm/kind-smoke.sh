#!/usr/bin/env bash
# Install the chart into a local kind cluster and run `helm test`, as a check before releasing the chart.
# Needs docker, kind, kubectl and helm; builds the images with docker compose first.
set -euo pipefail

CLUSTER=${CLUSTER:-appfit}
NAMESPACE=${NAMESPACE:-appfit}
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
VERSION=$(sed -n 's/^appVersion: *"\{0,1\}\([^"]*\)"\{0,1\}$/\1/p' "$HERE/appfit/Chart.yaml")

docker compose -f "$ROOT/compose.yaml" build backend frontend
for image in backend frontend; do
  docker tag "appfit-$image:latest" "appfit-$image:$VERSION"
done

kind get clusters | grep -qx "$CLUSTER" || kind create cluster --name "$CLUSTER" --wait 120s
kind load docker-image --name "$CLUSTER" "appfit-backend:$VERSION" "appfit-frontend:$VERSION"

# The namespace enforces the "restricted" Pod Security Standard, which the chart must meet.
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
kubectl label namespace "$NAMESPACE" --overwrite \
  pod-security.kubernetes.io/enforce=restricted pod-security.kubernetes.io/warn=restricted

# Two API replicas start together, so the migration lock is exercised as well.
helm upgrade --install appfit "$HERE/appfit" -n "$NAMESPACE" -f "$HERE/appfit/ci/kind-values.yaml" \
  --set backend.replicaCount=2 --wait --timeout 10m
helm test appfit -n "$NAMESPACE" --logs

echo "OK. Try it: kubectl -n $NAMESPACE port-forward service/appfit-frontend 8081:80"
echo "Clean up: kind delete cluster --name $CLUSTER"
