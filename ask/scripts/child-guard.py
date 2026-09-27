#!/usr/bin/env python3
"""Drain a consultation's group if its attached watcher disappears."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

owner = os.getppid()
outdir = Path(sys.argv[1])
child = subprocess.Popen(sys.argv[2:])
while child.poll() is None:
    if os.getppid() != owner:
        (outdir / 'watcher-loss.json').write_text(json.dumps({'status': 'failed', 'reason': 'watcher_lost', 'guard_pid': os.getpid()}) + '\n')
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        os.killpg(os.getpgrp(), signal.SIGTERM)
        time.sleep(0.5)
        os.killpg(os.getpgrp(), signal.SIGKILL)
    time.sleep(0.1)
sys.exit(child.returncode if child.returncode >= 0 else 128 - child.returncode)
