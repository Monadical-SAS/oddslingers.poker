#!/usr/bin/env python3
"""Generate pip-compatible requirements.txt from a Pipfile.

Used by the Dockerfile to install packages without needing a Pipfile.lock.
Reads the [packages] section and outputs one line per package in pip format.

Usage:
    python3 bin/gen-requirements.py [path/to/Pipfile]

Output goes to stdout; redirect to requirements.txt as needed.
"""

import sys
import tomllib

pipfile = sys.argv[1] if len(sys.argv) > 1 else "Pipfile"

with open(pipfile, "rb") as f:
    data = tomllib.load(f)

packages = data.get("packages", {})
for pkg, ver in packages.items():
    if isinstance(ver, dict):
        # Skip complex specs (git refs, local paths, extras dicts)
        continue
    if ver == "*" or ver == "":
        print(pkg)
    else:
        # ver is already in pip format: ">=3.9.0", "==2.2.11", etc.
        print(f"{pkg}{ver}")
