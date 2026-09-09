#!/usr/bin/env python
# This file is part of ts_aos_ai.
#
# Developed for the Vera C. Rubin Observatory Telescope and Site Systems.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Verify the model files on disk against ``models.yaml``.

Recomputes the SHA-256 of every file listed in ``models.yaml`` and compares it
to the recorded digest. Exits non-zero on any mismatch or missing file, so it
can be used in CI, as a pre-commit hook, or as a sanity check after a git-lfs
pull (a mismatch usually means git-lfs did not fetch the real weights and left
a pointer stub in place).
"""

import argparse
import hashlib
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


def sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    """Return the SHA-256 hex digest of a file, streamed in chunks."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk_size), b""):
            hasher.update(block)
    return hasher.hexdigest()


def iter_entries(manifest: dict):
    """Yield every ``(name, entry)`` pair across ai_donut and tarts."""
    for name, entry in manifest.get("ai_donut", {}).items():
        yield name, entry
    for version, entries in manifest.get("tarts", {}).items():
        for name, entry in entries.items():
            yield f"{version}/{name}", entry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    models_yaml = REPO_ROOT / "models.yaml"
    if not models_yaml.is_file():
        print(f"ERROR: {models_yaml} not found; run scripts/update_manifests.py first.")
        return 1

    with open(models_yaml) as f:
        manifest = yaml.safe_load(f) or {}

    failures: list[str] = []
    checked = 0
    for name, entry in iter_entries(manifest):
        path = REPO_ROOT / entry["path"]
        if not path.is_file():
            failures.append(f"{name}: missing file {entry['path']}")
            continue
        actual = sha256(path)
        if actual != entry["sha256"]:
            failures.append(
                f"{name}: checksum mismatch\n"
                f"    expected {entry['sha256']}\n"
                f"    got      {actual}\n"
                f"    (wrong version, or git-lfs left a pointer stub?)"
            )
        else:
            checked += 1

    if failures:
        print("Model verification FAILED:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"OK: verified {checked} model file(s) against models.yaml.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
