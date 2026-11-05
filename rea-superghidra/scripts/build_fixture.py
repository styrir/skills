#!/usr/bin/env python3
"""Build a disposable ARM64 fixture twice and compare bytes; never execute it."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


def build(output):
    source = Path(__file__).resolve().parents[1] / "tests/fixtures/companion_check.c"
    flags = ["-O0", "-arch", "arm64", "-mmacosx-version-min=14.0", "-Wl,-no_uuid"]
    compiler = "/usr/bin/clang"
    version = subprocess.check_output([compiler, "--version"], text=True).strip()
    output.mkdir(mode=0o700)  # A prior fixture or output must not be overwritten.
    with tempfile.TemporaryDirectory(prefix="fixture-build-", dir=output) as tmp:
        candidates = []
        for name in ("first", "second"):
            directory = Path(tmp) / name
            directory.mkdir()
            target = directory / "companion_check"
            subprocess.run([compiler, *flags, str(source), "-o", str(target)], check=True)
            candidates.append(target)
        if candidates[0].read_bytes() != candidates[1].read_bytes():
            raise ValueError("Separate build directories produced different bytes")
        target = output / "companion_check"
        shutil.copyfile(candidates[0], target)
    manifest = {
        "source": "tests/fixtures/companion_check.c",
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "compiler": compiler, "compiler_version": version, "flags": flags,
        "output": "companion_check",
        "target_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "separate_builds_identical": True, "target_executed": False,
    }
    (output / "build.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="New directory under an existing parent; requires Apple clang")
    build(parser.parse_args().output)
