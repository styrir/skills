#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: styrir-init.sh --target PATH [--project-name NAME] [--prefix PREFIX] [--dry-run]

Creates a local Styrir repository foundation without commits, remotes, or pushes.
Existing files are preserved; managed text files are created only when absent,
except .gitignore where missing canonical rules are appended.
EOF
}

fail() { printf 'styrir-init: %s\n' "$*" >&2; exit 1; }
log() { printf '%s\n' "$*"; }

TARGET=""
PROJECT_NAME=""
PREFIX=""
DRY_RUN=0

while (($#)); do
  case "$1" in
    --target) (($# >= 2)) || fail "--target requires a path"; TARGET="$2"; shift 2 ;;
    --project-name) (($# >= 2)) || fail "--project-name requires a value"; PROJECT_NAME="$2"; shift 2 ;;
    --prefix) (($# >= 2)) || fail "--prefix requires a value"; PREFIX="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) fail "unknown argument: $1" ;;
  esac
done

[[ -n "$TARGET" ]] || fail "--target is required"
for command_name in git bd python3; do command -v "$command_name" >/dev/null 2>&1 || fail "$command_name is required"; done
BD_VERSION="$(bd version | awk 'NR==1 {print $3}')"
[[ "$BD_VERSION" =~ ^1\.1\. ]] || fail "tested with Beads 1.1.x; found $BD_VERSION"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SKILL_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
TEMPLATES="$SKILL_DIR/templates"
[[ -d "$TEMPLATES" ]] || fail "template directory is missing: $TEMPLATES"

TARGET="$(python3 - "$TARGET" <<'PY'
import os, sys
print(os.path.abspath(os.path.expanduser(sys.argv[1])))
PY
)"
unset BD_DB BEADS_DB BD_GLOBAL BEADS_GLOBAL BEADS_DIR || true
[[ ! -L "$TARGET" ]] || fail "target must not be a symlink: $TARGET"
HOME_ROOT="$(cd -- "$HOME" && pwd -P)"
[[ "$TARGET" != "/" ]] || fail "refusing to initialize filesystem root"
[[ "$TARGET" != "$HOME_ROOT" ]] || fail "refusing to initialize the home directory"

existing_ancestor="$TARGET"
while [[ ! -e "$existing_ancestor" ]]; do
  parent="$(dirname -- "$existing_ancestor")"
  [[ "$parent" != "$existing_ancestor" ]] || break
  existing_ancestor="$parent"
done
existing_ancestor="$(cd -- "$existing_ancestor" && pwd -P)"
existing_real_target=""
[[ -e "$TARGET" ]] && existing_real_target="$(cd -- "$TARGET" && pwd -P)"
if super_root="$(git -C "$existing_ancestor" rev-parse --show-toplevel 2>/dev/null)"; then
  super_root="$(cd -- "$super_root" && pwd -P)"
  [[ -n "$existing_real_target" && "$super_root" == "$existing_real_target" ]] || fail "target is inside another Git repository: $super_root"
fi

basename_target="$(basename -- "$TARGET")"
[[ -n "$PROJECT_NAME" ]] || PROJECT_NAME="$basename_target"
if [[ -z "$PREFIX" ]]; then
  PREFIX="$(python3 - "$basename_target" <<'PY'
import re, sys
s=re.sub(r'[^a-z0-9]+','-',sys.argv[1].lower()).strip('-')
print(s or 'project')
PY
)"
fi
[[ "$PREFIX" =~ ^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$|^[a-z0-9]$ ]] || fail "prefix must use lowercase letters, digits, and internal hyphens (1-64 chars)"
PROJECT_SLUG="$(python3 - "$PROJECT_NAME" <<'PY'
import re, sys
s=re.sub(r'[^a-z0-9]+','-',sys.argv[1].lower()).strip('-')
print(s or 'project')
PY
)"

if ((DRY_RUN)); then
  cat <<EOF
Styrir init preview
  target:       $TARGET
  project name: $PROJECT_NAME
  project slug: $PROJECT_SLUG
  beads prefix: $PREFIX
  actions: initialize local Git on main if absent; initialize/bootstrap local Beads; install local hooks; create missing Styrir files/directories
  excluded: commits, remotes, repository creation, pushes, dependency installation
EOF
  exit 0
fi

mkdir -p -- "$TARGET"
TARGET="$(cd -- "$TARGET" && pwd -P)"

require_regular_or_absent() {
  local path="$1"
  [[ ! -e "$path" && ! -L "$path" ]] || [[ -f "$path" && ! -L "$path" ]] || fail "expected a regular file or absent path: $path"
}

render_template() {
  local src="$1" dest="$2"
  require_regular_or_absent "$dest"
  [[ ! -e "$dest" ]] || { log "preserved existing ${dest#"$TARGET"/}"; return 0; }
  python3 - "$src" "$dest" "$PROJECT_NAME" "$PROJECT_SLUG" "$PREFIX" <<'PY'
from pathlib import Path
import sys
src, dest, name, slug, prefix = sys.argv[1:]
text=Path(src).read_text()
text=text.replace('{{PROJECT_NAME}}', name).replace('{{PROJECT_SLUG}}', slug).replace('{{BEADS_PREFIX}}', prefix)
Path(dest).write_text(text)
PY
  log "created ${dest#"$TARGET"/}"
}

append_missing_lines() {
  local template="$1" dest="$2"
  require_regular_or_absent "$dest"
  touch -- "$dest"
  python3 - "$template" "$dest" <<'PY'
from pathlib import Path
import sys
src, dst = map(Path, sys.argv[1:])
current=dst.read_text().splitlines()
required=src.read_text().splitlines()
missing=[]
for line in required:
    if not line or line.startswith('#'):
        continue
    if line not in current:
        missing.append(line)
if missing:
    text=dst.read_text()
    if text and not text.endswith('\n'):
        text += '\n'
    if text and not text.endswith('\n\n'):
        text += '\n'
    text += '# Styrir init managed rules\n' + '\n'.join(missing) + '\n'
    dst.write_text(text)
print(len(missing))
PY
}

if [[ -e "$TARGET/.git" && ! -d "$TARGET/.git" ]]; then
  fail "linked worktrees, submodules, and non-directory .git entries require manual adoption"
fi
if [[ ! -d "$TARGET/.git" ]]; then
  git -C "$TARGET" init -b main >/dev/null
  log "initialized Git on main"
else
  [[ "$(git -C "$TARGET" rev-parse --is-bare-repository)" == "false" ]] || fail "bare Git repositories are not supported"
  current_branch="$(git -C "$TARGET" branch --show-current)"
  [[ -n "$current_branch" ]] || fail "detached HEAD is not supported for initialization"
  [[ "$current_branch" == "main" ]] || fail "existing Git branch must be main; found $current_branch"
  log "preserved existing Git repository on $current_branch"
fi

existing_hooks_path="$(git -C "$TARGET" config --local --get core.hooksPath || true)"
if [[ -n "$existing_hooks_path" && "$existing_hooks_path" != "$TARGET/.beads/hooks" ]]; then
  fail "custom core.hooksPath requires manual integration: $existing_hooks_path"
fi

# Beads 1.1.x infers a Dolt remote from Git origin during first-time init. That
# would silently cross the initializer's local-only remote boundary, so require
# explicit manual Beads adoption whenever an existing repository already has
# Git origin and no tracker metadata/seed exists yet.
if [[ ! -f "$TARGET/.beads/metadata.json" && ! -f "$TARGET/.beads/config.yaml" && ! -f "$TARGET/.beads/issues.jsonl" ]] \
  && git -C "$TARGET" remote get-url origin >/dev/null 2>&1; then
  fail "existing Git origin requires explicit Beads/Dolt remote adoption before styrir-init; refusing inferred tracker remote"
fi

git -C "$TARGET" config --local --get beads.role >/dev/null 2>&1 || git -C "$TARGET" config beads.role maintainer

for directory in \
  "$TARGET/agent-guidance" \
  "$TARGET/.styrir" \
  "$TARGET/.styrir/runs" \
  "$TARGET/.styrir/analysis" \
  "$TARGET/.styrir/analysis/raw" \
  "$TARGET/.styrir/analysis/reports" \
  "$TARGET/.styrir/pipelines" \
  "$TARGET/.styrir/build" \
  "$TARGET/.styrir/cache" \
  "$TARGET/.styrir/logs" \
  "$TARGET/.styrir/tmp"; do
  [[ ! -L "$directory" ]] || fail "managed directories must not be symlinks: $directory"
  [[ ! -e "$directory" || -d "$directory" ]] || fail "managed directory collides with a non-directory: $directory"
  mkdir -p -- "$directory"
done

missing_count="$(append_missing_lines "$TEMPLATES/gitignore" "$TARGET/.gitignore")"
log "ensured .gitignore rules ($missing_count added)"
render_template "$TEMPLATES/gitnexusignore" "$TARGET/.gitnexusignore"
if [[ -e "$TARGET/.gitnexusrc" ]]; then
  require_regular_or_absent "$TARGET/.gitnexusrc"
  python3 - "$TARGET/.gitnexusrc" <<'PY'
import json, sys
with open(sys.argv[1]) as f: json.load(f)
PY
  log "preserved existing .gitnexusrc"
else
  render_template "$TEMPLATES/gitnexusrc.tmpl" "$TARGET/.gitnexusrc"
fi
if [[ -e "$TARGET/Agents.md" && ! -e "$TARGET/AGENTS.md" ]]; then
  require_regular_or_absent "$TARGET/Agents.md"
  cp -- "$TARGET/Agents.md" "$TARGET/AGENTS.md"
  log "copied existing Agents.md to canonical AGENTS.md"
else
  render_template "$TEMPLATES/AGENTS.md.tmpl" "$TARGET/AGENTS.md"
fi
if [[ -e "$TARGET/Claude.md" && ! -e "$TARGET/CLAUDE.md" ]]; then
  require_regular_or_absent "$TARGET/Claude.md"
  cp -- "$TARGET/Claude.md" "$TARGET/CLAUDE.md"
  log "copied existing Claude.md to canonical CLAUDE.md"
else
  render_template "$TEMPLATES/CLAUDE.md" "$TARGET/CLAUDE.md"
fi
render_template "$TEMPLATES/beads-and-dolt.md.tmpl" "$TARGET/agent-guidance/beads-and-dolt.md"
render_template "$TEMPLATES/handoffs.md" "$TARGET/agent-guidance/handoffs.md"
render_template "$TEMPLATES/gitnexus.md" "$TARGET/agent-guidance/gitnexus.md"
render_template "$TEMPLATES/non-interactive-shell.md" "$TARGET/agent-guidance/non-interactive-shell.md"
render_template "$TEMPLATES/styrir-workspace.md" "$TARGET/agent-guidance/styrir-workspace.md"

export BEADS_DIR="$TARGET/.beads"
bd_here() { (cd -- "$TARGET" && bd "$@"); }
HAD_HEAD=0
PRE_INIT_HEAD=""
if PRE_INIT_HEAD="$(git -C "$TARGET" rev-parse --verify HEAD 2>/dev/null)"; then HAD_HEAD=1; fi
CURRENT_REF="$(git -C "$TARGET" symbolic-ref -q HEAD)"
[[ -n "$CURRENT_REF" ]] || fail "detached HEAD is not supported for initialization"
CREATED_BEADS=0
if [[ -L "$TARGET/.beads" || ( -e "$TARGET/.beads" && ! -d "$TARGET/.beads" ) ]]; then
  fail ".beads must be an ordinary directory or absent"
elif [[ -f "$TARGET/.beads/metadata.json" ]]; then
  python3 - "$TARGET/.beads/metadata.json" <<'PY'
import json, sys
d=json.load(open(sys.argv[1]))
if d.get('backend') != 'dolt' or d.get('dolt_mode') != 'embedded':
    raise SystemExit('existing .beads workspace is not embedded Dolt')
PY
  bd_here bootstrap --yes >/dev/null
  log "validated existing Beads workspace"
elif [[ -d "$TARGET/.beads" ]] && find "$TARGET/.beads" -mindepth 1 -maxdepth 1 -print -quit | grep -q .; then
  [[ -f "$TARGET/.beads/issues.jsonl" || -d "$TARGET/.beads/backup" || -f "$TARGET/.beads/config.yaml" ]] || fail "unrecognized existing .beads contents require manual adoption"
  bd_here bootstrap --yes >/dev/null
  log "bootstrapped existing Beads seed/configuration"
else
  init_log="$(mktemp "${TMPDIR:-/tmp}/styrir-bd-init.XXXXXX")"
  temp_index="$(mktemp "${TMPDIR:-/tmp}/styrir-bd-index.XXXXXX")"
  rm -f -- "$temp_index"
  if ! (cd -- "$TARGET" && GIT_INDEX_FILE="$temp_index" GIT_AUTHOR_NAME='' GIT_AUTHOR_EMAIL='' GIT_COMMITTER_NAME='' GIT_COMMITTER_EMAIL='' bd init --prefix "$PREFIX" --skip-agents --skip-hooks --non-interactive --role maintainer) >"$init_log" 2>&1; then
    cat "$init_log" >&2
    rm -f -- "$init_log" "$temp_index"
    fail "Beads initialization failed"
  fi
  rm -f -- "$init_log" "$temp_index"
  CREATED_BEADS=1
  log "initialized repository-local Beads/Dolt tracker"
fi
bd_here hooks install --beads >/dev/null

# bd 1.1.0 creates a Git commit during first-time tracker initialization. The
# Styrir local-init contract leaves the initial commit and publication checkpoint to the operator, so
# remove only that freshly-created commit when this script started with no HEAD.
if ((CREATED_BEADS)) && git -C "$TARGET" rev-parse --verify HEAD >/dev/null 2>&1; then
  post_init_head="$(git -C "$TARGET" rev-parse HEAD)"
  if ((HAD_HEAD == 0)); then
    commit_count="$(git -C "$TARGET" rev-list --count HEAD)"
    subject="$(git -C "$TARGET" log -1 --format=%s)"
    [[ "$commit_count" == "1" && "$subject" == "bd init: initialize beads issue tracking" ]] || fail "Beads created an unexpected Git history; refusing to rewrite it"
    empty_tree="$(git -C "$TARGET" hash-object -t tree /dev/null)"
    git -C "$TARGET" read-tree "$empty_tree"
    git -C "$TARGET" update-ref -d "$CURRENT_REF"
    git -C "$TARGET" read-tree --reset "$empty_tree"
    log "removed Beads' automatic initialization commit; files remain uncommitted"
  elif [[ "$post_init_head" != "$PRE_INIT_HEAD" ]]; then
    fail "Beads unexpectedly changed existing Git history"
  fi
fi

# Guard the no-publication contract mechanically.
[[ -z "$(git -C "$TARGET" remote)" ]] || log "preserved pre-existing Git remote(s); no remote was added"

python3 - "$TARGET" "$PREFIX" <<'PY'
from pathlib import Path
import json, subprocess, sys
root=Path(sys.argv[1]); prefix=sys.argv[2]
required=[
 '.git','.beads','.styrir','agent-guidance','.gitignore','.gitnexusignore','.gitnexusrc','AGENTS.md','CLAUDE.md',
 '.styrir/runs','.styrir/analysis/raw','.styrir/analysis/reports','.styrir/pipelines','.styrir/build','.styrir/cache','.styrir/logs','.styrir/tmp',
 'agent-guidance/beads-and-dolt.md','agent-guidance/handoffs.md','agent-guidance/gitnexus.md','agent-guidance/non-interactive-shell.md','agent-guidance/styrir-workspace.md',
]
missing=[p for p in required if not (root/p).exists()]
if missing: raise SystemExit('missing generated paths: '+', '.join(missing))
json.loads((root/'.gitnexusrc').read_text())
branch=subprocess.check_output(['git','-C',str(root),'branch','--show-current'],text=True).strip()
if not branch: raise SystemExit('Git branch is unresolved')
where=subprocess.check_output(['bd','where'],text=True,cwd=root)
if str(root/'.beads') not in where: raise SystemExit('Beads resolved outside target')
print(f'validated target={root} branch={branch} prefix={prefix}')
PY

log "Styrir local initialization complete. No commit, remote, or push was created by this script."
