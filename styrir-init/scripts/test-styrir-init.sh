#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
fixture="$(mktemp -d "${TMPDIR:-/tmp}/styrir-init-retired.XXXXXX")"
trap 'rm -rf -- "$fixture"' EXIT
mkdir -p "$fixture/bin" "$fixture/existing"
printf 'preserve me\n' > "$fixture/existing/sentinel"
for command_name in bd git; do
  printf '#!/usr/bin/env bash\nprintf called >> "$STYRIR_TEST_CALLS"\nexit 99\n' > "$fixture/bin/$command_name"
  chmod +x "$fixture/bin/$command_name"
done
export STYRIR_TEST_CALLS="$fixture/calls"
export PATH="$fixture/bin:$PATH"
bash "$SCRIPT_DIR/styrir-init.sh" --help >/dev/null
for target in "$fixture/new" "$fixture/existing"; do
  if bash "$SCRIPT_DIR/styrir-init.sh" --target "$target" > "$fixture/output" 2>&1; then
    echo 'retired initializer unexpectedly succeeded'; exit 1
  fi
  [[ "$(cat "$fixture/output")" == *'Beads is decommissioned'* ]]
done
[[ ! -e "$fixture/new" && ! -e "$fixture/calls" ]]
[[ "$(cat "$fixture/existing/sentinel")" == 'preserve me' ]]
echo 'Retired initializer: no target changes and no tracker/Git invocation'
