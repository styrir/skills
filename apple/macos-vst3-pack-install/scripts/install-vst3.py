#!/usr/bin/env python3
"""Preview: python3 install-vst3.py | Install: python3 install-vst3.py --install"""
import argparse
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile

INSTALLER = '/usr/sbin/installer'


def output(*args):
    return subprocess.check_output(args)


def choices(nodes):
    result = []
    for node in nodes:
        children = node.get('childItems', [])
        child_changes = choices(children)
        selected = (any(c['attributeSetting'] for c in child_changes)
                    if children else 'VST3' in node['choiceIdentifier'].split('.'))
        result.append({'choiceIdentifier': node['choiceIdentifier'],
                       'choiceAttribute': 'selected', 'attributeSetting': int(selected)})
        result.extend(child_changes)
    return result


def main():
    parser = argparse.ArgumentParser(description='Sequential FabFilter VST3-only, all-users installer. Preview by default.')
    parser.add_argument('--install', action='store_true', help='Actually install; requires root or sudo authorization.')
    args = parser.parse_args()
    packages = sorted(Path(__file__).resolve().parent.glob('*.pkg'))
    if not packages:
        parser.error('No .pkg files alongside this script.')
    with tempfile.TemporaryDirectory(prefix='fabfilter-vst3-') as tmp:
        plans = []
        for i, pkg in enumerate(packages):
            tree = plistlib.loads(output(INSTALLER, '-pkg', str(pkg), '-target', '/', '-showChoicesXML'))
            changes = choices(tree)
            leaves = []
            def collect(nodes):
                for node in nodes:
                    if node.get('childItems'):
                        collect(node['childItems'])
                    elif node.get('pathsOfActivePackagesInChoice'):
                        leaves.append(node['choiceIdentifier'])
            collect(tree)
            vst3 = {c for c in leaves if 'VST3' in c.split('.')}
            if not vst3:
                raise RuntimeError(f'{pkg.name}: no identifiable VST3 component; refusing to guess.')
            path = Path(tmp) / f'{i}.plist'
            path.write_bytes(plistlib.dumps(changes))
            applied = plistlib.loads(output(INSTALLER, '-pkg', str(pkg), '-target', '/',
                                           '-showChoicesAfterApplyingChangesXML', str(path)))
            selected = {c['choiceIdentifier'] for c in applied
                        if c['choiceAttribute'] == 'selected' and c['attributeSetting']}
            if selected.intersection(leaves) != vst3:
                raise RuntimeError(f'{pkg.name}: installer did not honor VST3-only selection.')
            plans.append((pkg, path, vst3))
            print(f'OK: {pkg.name} — VST3 only', flush=True)
        print(f'\nPreflight passed: {len(plans)}/{len(packages)} packages. Target: / (all users).', flush=True)
        print('Default VST3 folder: /Library/Audio/Plug-Ins/VST3', flush=True)
        print('Package scripts still run; choice selection is not a security sandbox.', flush=True)
        if not args.install:
            print('Nothing installed. Run again with --install to install sequentially.')
            return
        prefix = [] if os.geteuid() == 0 else ['/usr/bin/sudo']
        if prefix:
            subprocess.run(prefix + ['-v'], check=True)
        for i, (pkg, path, identifiers) in enumerate(plans, 1):
            print(f'\n[{i}/{len(plans)}] Installing {pkg.name}', flush=True)
            subprocess.run(prefix + [INSTALLER, '-pkg', str(pkg), '-target', '/',
                                    '-applyChoiceChangesXML', str(path), '-dumplog'], check=True)
            for identifier in identifiers:
                receipt = plistlib.loads(output('/usr/sbin/pkgutil', '--pkg-info-plist', identifier))
                print(f'Verified receipt: {identifier} {receipt["pkg-version"]}', flush=True)
        print(f'\nFinished: {len(plans)}/{len(packages)} packages installed.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (subprocess.CalledProcessError, RuntimeError, OSError, ValueError) as error:
        raise SystemExit(f'Stopped: {error}')
