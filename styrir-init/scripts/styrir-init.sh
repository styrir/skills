#!/usr/bin/env bash
set -euo pipefail

message='styrir-init: bootstrap disabled because Beads is decommissioned. Verk migration: vk-2589. No target changes were made.'
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  printf '%s\n' "$message"
  exit 0
fi
printf '%s\n' "$message" >&2
exit 1
