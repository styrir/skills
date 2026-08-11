#!/usr/bin/env bash
# lab-recon.sh — fast macOS .app recon dump for defender self-tests
# Usage: lab-recon.sh /path/to/App.app
set -euo pipefail

APP="${1:-}"
if [[ -z "$APP" || ! -d "$APP" ]]; then
  echo "Usage: $0 /path/to/App.app" >&2
  exit 2
fi

APP="$(cd "$APP" && pwd)"
BIN="$(find "$APP/Contents/MacOS" -type f -perm +111 2>/dev/null | head -1 || true)"
BID="$(defaults read "$APP/Contents/Info" CFBundleIdentifier 2>/dev/null || echo "?")"
OUT="${TMPDIR:-/tmp}/lab-recon-$(basename "$APP" .app)-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"

{
  echo "=== APP ==="
  echo "$APP"
  echo "=== BIN ==="
  echo "$BIN"
  echo "=== BID ==="
  echo "$BID"
  echo
  echo "=== file ==="
  file "$BIN" 2>/dev/null || true
  echo
  echo "=== codesign -dv ==="
  codesign -dv --verbose=4 "$APP" 2>&1 || true
  echo
  echo "=== entitlements ==="
  codesign -d --entitlements :- "$APP" 2>/dev/null | plutil -convert xml1 -o - - 2>/dev/null || true
  echo
  echo "=== spctl ==="
  spctl -a -vv "$APP" 2>&1 || true
  echo
  echo "=== otool -L (head) ==="
  otool -L "$BIN" 2>/dev/null | head -60 || true
  echo
  echo "=== helpers/dylibs/xpc ==="
  find "$APP/Contents" \( -name '*.xpc' -o -name '*Helper*' -o -name '*.dylib' \) 2>/dev/null | head -80 || true
  echo
  echo "=== electron/asar ==="
  find "$APP/Contents" \( -name 'app.asar' -o -name 'Electron Framework' -o -name 'electron' \) 2>/dev/null | head -40 || true
  echo
  echo "=== license-ish strings ==="
  if [[ -n "$BIN" && -f "$BIN" ]]; then
    strings -a "$BIN" | rg -i 'license|licence|trial|serial|activat|subscri|premium|pro\b|expir|invalid|register|purchase|receipt|jwt' | sort -u | head -200 || true
  fi
  echo
  echo "=== urls ==="
  if [[ -n "$BIN" && -f "$BIN" ]]; then
    strings -a "$BIN" | rg -o 'https?://[^"'\'' ]+' | sort -u | head -100 || true
  fi
} | tee "$OUT/recon.txt"

echo
echo "Wrote $OUT/recon.txt"
