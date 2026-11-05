---
name: macos-vst3-pack-install
description: Use when batch-installing macOS VST3 plugin packs.
---

# macOS VST3 pack installation

Install a directory of `.pkg` audio plugins sequentially, VST3 only, using the default all-users location. Preserve existing other formats; do not uninstall them implicitly.

## Saved implementation

- [Saved installer](scripts/install-vst3.py): preserved from the FabFilter batch.
- Original standalone script: `/Users/brooks/install/fabfilter/install-vst3.py`.
- Python 3 standard library only; macOS `/usr/sbin/installer` and `pkgutil`.
- Script discovers `.pkg` files **alongside itself**, previews by default, and installs only with `--install`.
- Selection matches a dot-delimited `VST3` token in choice identifiers, selects its ancestors, deselects other components, and verifies the evaluated leaf selections before any installation.
- Fails closed if no VST3 choice exists or evaluated selections disagree. Stops at first installation or receipt failure. Does not roll back previously completed packages.

## Workflow

1. Inspect the requested directory and package count. Check package signatures with `pkgutil --check-signature`. Prefer official vendor packages; disclose unsigned/repackaged material before privileged execution. Never use `-allowUntrusted`, disable Gatekeeper, remove quarantine, or re-sign vendor plugins merely to force installation.
2. Inspect choices: `installer -pkg '/path/plugin.pkg' -target / -showChoicesXML`. Expand representative packages with `pkgutil --expand` into a temporary directory and read `PackageInfo` to confirm VST3 install location and bundle paths. Expected default: `/Library/Audio/Plug-Ins/VST3`.
3. Copy `scripts/install-vst3.py` into the requested pack directory (do not overwrite existing files without inspecting). Run `python3 '/path/to/pack/install-vst3.py'` to preview **every package**. All must pass before installation.
4. This identifier convention and receipt lookup were verified with FabFilter. Other vendors may use different identifiers, dependencies, mandatory support components, or receipt IDs. Inspect and adapt a pack-local copy; never guess a generic `--vst3` flag. Choice selection does not constrain what privileged package scripts can do.
5. After the user authorizes installation, use the native macOS administrator prompt below. Never ask for a password in chat, put it in arguments/environment/files, or implement a password-collecting dialog. Retain raw installer output in a pack-local log.
6. Verify process exit, final completed count against discovered package count, each selected component receipt/version, and actual VST3 bundle plus `Contents/MacOS/<CFBundleExecutable>` at the default all-users path. `pkgutil --files` may include `._Name.vst3` AppleDouble metadata; exclude `._*` when finding real bundles.
7. Installer success is not DAW-loading success. Verify discovery/loading separately or explicitly state that it is untested.

## Native administrator authorization

Run this Python pattern through a tracked background terminal with completion notification. Resolve the Python executable before elevation; shell-quote paths and JSON-quote the AppleScript string. Substitute the explicitly requested pack path.

```python
import json, shlex, subprocess, sys
from pathlib import Path
script = Path('/path/to/pack/install-vst3.py')
log = script.parent / 'install-vst3.log'
command = shlex.join([sys.executable, str(script), '--install'])
command += ' > ' + shlex.quote(str(log)) + ' 2>&1'
source = 'do shell script ' + json.dumps(command)
source += ' with administrator privileges with prompt ' + json.dumps(
    'Install plugin packages: VST3 only, for all users. Package scripts run as administrator.')
result = subprocess.run(['/usr/bin/osascript', '-e', source], capture_output=True, text=True)
print(result.stdout, result.stderr)
sys.exit(result.returncode)
```

macOS owns credential entry; no password is returned to the agent. Handle cancellation as cancellation, not successful installation. Read the resulting log and verify installed targets before claiming completion.

## Bitwig: installed but hidden

Before reinstalling, changing permissions, signing, quarantine, or deleting caches:

- Check browser location, format and collection filters, and **preferred plugin format**. Bitwig can prefer **CLAP over VST3**, hiding VST3 alternatives. This was the confirmed cause in the original workflow.
- Check `/Library/Audio/Plug-Ins/VST3` in Settings → Locations → Plug-in Locations. Use the rescan control for System VST 3 Plug-ins if needed.
- Read `~/Library/Logs/Bitwig/BitwigStudio.log` and `engine.log`; distinguish CLAP loading from VST3 loading by full path.
- Metadata cache filenames vary by release; discover `~/Library/Caches/Bitwig/vst3-metadata-*` instead of hardcoding a version. A path in a binary cache proves an entry exists, not successful loading.
- Verify architectures with `file`, signatures with `codesign --verify --deep --strict`, and quarantine read-only with `xattr` when logs indicate loading failure. Do not apply blanket security bypass commands.
- Logic uses AU, not VST3. Do not install extra formats unless requested.

## Source check

Run `python3 scripts/test_install_vst3.py` from this skill's directory. This checks
selection and preflight refusal with synthetic package metadata; it does not
qualify a real vendor package, administrator prompt, installation or DAW loading.
