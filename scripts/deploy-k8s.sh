#!/usr/bin/env bash
# Build, push, and deploy webquik-mcp to pitr / infra.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NS="${NAMESPACE:-infra}"
CTX="${KUBE_CONTEXT:-pitr}"
default_image() {
  if [[ -f "$REGISTRY_FILE" ]]; then
    grep 'path:' "$REGISTRY_FILE" | awk '{print $2}'
  else
    echo "cr.selcloud.ru/petrste/mcp-over-quik"
  fi
}
IMAGE="${IMAGE:-$(default_image)}"
TAG="${TAG:-v0.1.5}"
PUSH="${PUSH:-1}"
REGISTRY_FILE="${REGISTRY_FILE:-$ROOT/registry.selectel}"

kubectl_cmd() {
  kubectl --context "$CTX" "$@"
}

registry_value() {
  local section="$1"
  local key="$2"
  awk -v section="$section" -v key="$key" '
    $0 ~ "^  " section ":$" { in_section=1; next }
    in_section && /^  [a-z]+:$/ { in_section=0 }
    in_section && $1 == key ":" { print $2; exit }
  ' "$REGISTRY_FILE"
}

registry_login() {
  if [[ ! -f "$REGISTRY_FILE" ]]; then
    echo "Registry creds not found: $REGISTRY_FILE" >&2
    return 0
  fi
  local url user pass
  url="$(grep '^  url:' "$REGISTRY_FILE" | awk '{print $2}' | sed 's|https://||')"
  user="$(registry_value push username)"
  pass="$(registry_value push password)"
  podman login "$url" -u "$user" -p "$pass"
}

sync_pull_secret() {
  if [[ ! -f "$REGISTRY_FILE" ]]; then
    echo "Registry creds not found: $REGISTRY_FILE" >&2
    return 0
  fi
  local url user pass
  url="$(grep '^  url:' "$REGISTRY_FILE" | awk '{print $2}' | sed 's|https://||')"
  user="$(registry_value pull username)"
  pass="$(registry_value pull password)"
  kubectl_cmd -n "$NS" create secret docker-registry mcp-over-quik-pull \
    --docker-server="$url" \
    --docker-username="$user" \
    --docker-password="$pass" \
    --dry-run=client -o yaml | kubectl_cmd -n "$NS" apply -f -
}

build_image() {
  if ! command -v podman >/dev/null 2>&1; then
    echo "podman is required" >&2
    exit 1
  fi
  registry_login
  echo "Building ${IMAGE}:${TAG}..."
  podman build \
    --platform linux/amd64 \
    -t "${IMAGE}:${TAG}" \
    "$ROOT"
  if [[ "$PUSH" == "1" ]]; then
    podman push "${IMAGE}:${TAG}"
  fi
}

deploy_manifests() {
  tmp="$(mktemp)"
  sed "s|image: cr.selcloud.ru/[^:]*:v[0-9.]*|image: ${IMAGE}:${TAG}|" \
    "$ROOT/k8s/deployment.yaml" >"$tmp"
  kubectl_cmd apply -f "$tmp"
  kubectl_cmd apply -f "$ROOT/k8s/service.yaml"
  rm -f "$tmp"
  kubectl_cmd -n "$NS" rollout status deploy/webquik-mcp --timeout=180s
}

main() {
  build_image
  sync_pull_secret
  deploy_manifests
  kubectl_cmd apply -f "$ROOT/k8s/certificate.yaml"
  kubectl_cmd apply -f "$ROOT/k8s/ingress.yaml"
  echo "Deployed webquik-mcp:"
  echo "  in-cluster: http://webquik-mcp.${NS}.svc.cluster.local:3001/mcp"
  echo "  ingress:    https://webquik-sber-mcp.petrstekunov.ru/mcp"
}

main "$@"
