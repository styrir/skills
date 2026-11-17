"""Check curated manifest, real linker installation, idempotence and rollback."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

repo = Path(__file__).resolve().parents[2]
manifest = json.loads((repo / 'harness-links.json').read_text())
info = json.loads((repo / 'design-policy/installation.json').read_text())
names = ['design-policy', *info['skills']]
assert manifest['agents']['links']['design-policy'] == 'design-policy'
for name in info['skills']:
    assert manifest['agents']['links'][name] == f"{info['upstream_root']}/skills/{name}"
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / 'scripts').mkdir()
    script = root / 'scripts/link-harness-skills.py'
    script.write_bytes((repo / 'scripts/link-harness-skills.py').read_bytes())
    destination = root / 'installed'
    destination.mkdir()
    (destination / 'unrelated').write_text('keep')
    sources = {}
    for name in names:
        source = root / 'sources' / name
        source.mkdir(parents=True)
        (source / 'SKILL.md').write_text(f'---\nname: {name}\n---\n')
        (source / 'reference.md').write_text('relative resource')
        sources[name] = str(source)
    (root / 'harness-links.json').write_text(json.dumps({'agents': {'dir': str(destination), 'links': sources}}))
    def run(flag):
        subprocess.run([sys.executable, str(script), '--harness', 'agents', flag], check=True, capture_output=True)
    run('--apply')
    run('--check')
    targets = {n: (destination / n).readlink() for n in names}
    run('--apply')
    assert targets == {n: (destination / n).readlink() for n in names}
    for name in names:
        link = destination / name
        assert link.resolve() == Path(sources[name]).resolve()
        assert (link / 'reference.md').read_text() == 'relative resource'
        link.unlink()
    assert list(destination.iterdir()) == [destination / 'unrelated']
    assert (destination / 'unrelated').read_text() == 'keep'
print('PASS: manifest, whole-folder links, resources, idempotence, scoped rollback')
