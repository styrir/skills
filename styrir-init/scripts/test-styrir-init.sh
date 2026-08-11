#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
INIT="$SCRIPT_DIR/styrir-init.sh"
[[ -x "$INIT" ]] || { printf 'missing executable initializer: %s\n' "$INIT" >&2; exit 1; }

fixture_parent="$(mktemp -d "${TMPDIR:-/tmp}/styrir-init-test.XXXXXX")"
fixture="$fixture_parent/random-project-$RANDOM-$RANDOM/nested-target"
mkdir -p -- "$(dirname -- "$fixture")"
fixture="$(cd -- "$(dirname -- "$fixture")" && pwd -P)/$(basename -- "$fixture")"
cleanup() {
  if [[ "${KEEP_FIXTURE:-0}" == "1" ]]; then
    printf 'fixture retained: %s\n' "$fixture_parent"
  elif [[ -n "$fixture_parent" && -d "$fixture_parent" ]]; then
    rm -rf -- "$fixture_parent"
  fi
}
trap cleanup EXIT

mkdir -p -- "$fixture/.preexisting-hidden/subdir" "$fixture/visible-folder/subdir" "$fixture/visible folder/Unicode-Þór"
printf 'hidden sentinel\n' > "$fixture/.preexisting-hidden/sentinel.txt"
printf 'visible sentinel\n' > "$fixture/visible-folder/sentinel.txt"
printf 'space unicode sentinel\n' > "$fixture/visible folder/Unicode-Þór/sentinel file.txt"
printf 'dot file sentinel\n' > "$fixture/.env.example"
printf 'visible file sentinel\n' > "$fixture/README.seed"

snapshot_before="$(python3 - "$fixture" <<'PY'
from pathlib import Path
import hashlib, sys
root=Path(sys.argv[1])
for rel in ['.preexisting-hidden/sentinel.txt','visible-folder/sentinel.txt','visible folder/Unicode-Þór/sentinel file.txt','.env.example','README.seed']:
 p=root/rel
 print(rel, hashlib.sha256(p.read_bytes()).hexdigest())
PY
)"

"$INIT" --target "$fixture" --project-name "Random Fixture" --prefix random-fixture
first_status="$(git -C "$fixture" status --porcelain=v1)"
[[ -n "$first_status" ]] || { echo 'expected uncommitted generated files'; exit 1; }
[[ -z "$(git -C "$fixture" remote)" ]] || { echo 'initializer created a Git remote'; exit 1; }
if git -C "$fixture" rev-parse --verify HEAD >/dev/null 2>&1; then echo 'initializer created a commit'; exit 1; fi

snapshot_after="$(python3 - "$fixture" <<'PY'
from pathlib import Path
import hashlib, sys
root=Path(sys.argv[1])
for rel in ['.preexisting-hidden/sentinel.txt','visible-folder/sentinel.txt','visible folder/Unicode-Þór/sentinel file.txt','.env.example','README.seed']:
 p=root/rel
 print(rel, hashlib.sha256(p.read_bytes()).hexdigest())
PY
)"
[[ "$snapshot_before" == "$snapshot_after" ]] || { echo 'pre-existing content changed'; exit 1; }

required=(
  .git .beads .styrir agent-guidance .gitignore .gitnexusignore .gitnexusrc AGENTS.md CLAUDE.md
  .styrir/runs .styrir/analysis/raw .styrir/analysis/reports .styrir/pipelines .styrir/build .styrir/cache .styrir/logs .styrir/tmp
  agent-guidance/beads-and-dolt.md agent-guidance/gitnexus.md agent-guidance/non-interactive-shell.md agent-guidance/styrir-workspace.md
  .preexisting-hidden .preexisting-hidden/subdir visible-folder visible-folder/subdir "visible folder" "visible folder/Unicode-Þór" "visible folder/Unicode-Þór/sentinel file.txt" .env.example README.seed
)
for rel in "${required[@]}"; do [[ -e "$fixture/$rel" ]] || { echo "missing $rel"; exit 1; }; done

# Capture all non-runtime files before the second run; generated tracker runtime is intentionally excluded.
manifest_before="$(python3 - "$fixture" <<'PY'
from pathlib import Path
import hashlib, sys
root=Path(sys.argv[1])
excluded={'.git','.beads','.styrir'}
for p in sorted(root.rglob('*')):
 rel=p.relative_to(root)
 if rel.parts and rel.parts[0] in excluded: continue
 if p.is_file(): print(rel, hashlib.sha256(p.read_bytes()).hexdigest())
PY
)"
"$INIT" --target "$fixture" --project-name "Random Fixture" --prefix random-fixture
manifest_after="$(python3 - "$fixture" <<'PY'
from pathlib import Path
import hashlib, sys
root=Path(sys.argv[1])
excluded={'.git','.beads','.styrir'}
for p in sorted(root.rglob('*')):
 rel=p.relative_to(root)
 if rel.parts and rel.parts[0] in excluded: continue
 if p.is_file(): print(rel, hashlib.sha256(p.read_bytes()).hexdigest())
PY
)"
[[ "$manifest_before" == "$manifest_after" ]] || { echo 'second run changed managed/source files'; diff <(printf '%s\n' "$manifest_before") <(printf '%s\n' "$manifest_after") || true; exit 1; }

export BEADS_DIR="$fixture/.beads"
(cd -- "$fixture" && bd where) | grep -F "$fixture/.beads" >/dev/null
(cd -- "$fixture" && bd dolt remote list) | grep -F 'No remotes configured.' >/dev/null
git -C "$fixture" check-ignore -q .styrir/tmp
git -C "$fixture" check-ignore -q .gitnexus/example
git -C "$fixture" check-ignore -q .beads/embeddeddolt
if git -C "$fixture" check-ignore -q .beads/config.yaml; then echo '.beads/config.yaml must remain trackable'; exit 1; fi
if git -C "$fixture" check-ignore -q .beads/metadata.json; then echo '.beads/metadata.json must remain trackable'; exit 1; fi
[[ "$(git -C "$fixture" branch --show-current)" == "main" ]]
[[ "$(git -C "$fixture" symbolic-ref HEAD)" == "refs/heads/main" ]]
[[ "$(git -C "$fixture" rev-parse --is-bare-repository)" == "false" ]]
[[ "$(git -C "$fixture" config --local --get beads.role)" == "maintainer" ]]
[[ "$(git -C "$fixture" config --local --get core.hooksPath)" == "$fixture/.beads/hooks" ]]
(cd -- "$fixture" && bd hooks list) | grep -F 'pre-commit: installed' >/dev/null

python3 - "$fixture/.gitnexusrc" <<'PY'
import json, sys
p=sys.argv[1]
d=json.load(open(p))
assert d['analyze']['indexOnly'] is True
assert d['analyze']['name']=='random-fixture'
PY

# Failure cases: nested repository, non-main repository, custom hooks path,
# symlink collision, and incompatible existing .beads content must fail closed.
failure_root="$fixture_parent/failure-cases"
mkdir -p -- "$failure_root/parent/nested"
git -C "$failure_root/parent" init -b main >/dev/null
if "$INIT" --target "$failure_root/parent/nested" --prefix nested-project >/dev/null 2>&1; then echo 'nested repository safety check failed'; exit 1; fi

mkdir -p -- "$failure_root/non-main"
git -C "$failure_root/non-main" init -b develop >/dev/null
if "$INIT" --target "$failure_root/non-main" --prefix non-main >/dev/null 2>&1; then echo 'non-main safety check failed'; exit 1; fi

mkdir -p -- "$failure_root/custom-hooks"
git -C "$failure_root/custom-hooks" init -b main >/dev/null
git -C "$failure_root/custom-hooks" config core.hooksPath .custom-hooks
if "$INIT" --target "$failure_root/custom-hooks" --prefix custom-hooks >/dev/null 2>&1; then echo 'custom hooks safety check failed'; exit 1; fi

mkdir -p -- "$failure_root/symlink-collision"
ln -s /tmp "$failure_root/symlink-collision/.styrir"
if "$INIT" --target "$failure_root/symlink-collision" --prefix symlink-collision >/dev/null 2>&1; then echo 'symlink collision safety check failed'; exit 1; fi

mkdir -p -- "$failure_root/bad-beads/.beads"
printf 'unknown\n' > "$failure_root/bad-beads/.beads/unrecognized"
if "$INIT" --target "$failure_root/bad-beads" --prefix bad-beads >/dev/null 2>&1; then echo 'incompatible beads safety check failed'; exit 1; fi

printf 'PASS: random fixture initialized twice with hidden and visible content preserved: %s\n' "$fixture"
