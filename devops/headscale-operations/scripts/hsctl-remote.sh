#!/usr/bin/env bash
# hsctl-remote — run Berlin hsctl over SSH from the operator Mac
set -euo pipefail
HOST="${HSCTL_HOST:-root@82.22.174.79}"
KEY="${HSCTL_SSH_KEY:-$HOME/.ssh/id_ed25519}"
ssh -o BatchMode=yes -o ConnectTimeout=20 -i "$KEY" "$HOST" "hsctl $(printf '%q ' "$@")"
