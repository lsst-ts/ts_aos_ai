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

"""CI checks that the committed manifests match the model files on disk.

These guard against the common mistake of adding or updating a model file
without re-running ``scripts/update_manifests.py`` (so ``models.yaml`` and
``model_history.yaml`` drift out of sync with the actual files and checksums).
"""

import importlib.util
import unittest
from pathlib import Path
from types import ModuleType

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_update_manifests() -> ModuleType:
    """Import scripts/update_manifests.py (not an installed package)."""
    path = REPO_ROOT / "scripts" / "update_manifests.py"
    spec = importlib.util.spec_from_file_location("update_manifests", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestManifests(unittest.TestCase):
    """Verify the committed manifests are in sync with the model files."""

    update_manifests: ModuleType
    fresh: dict

    @classmethod
    def setUpClass(cls) -> None:
        cls.update_manifests = _load_update_manifests()
        # Manifest rebuilt from the files currently on disk.
        cls.fresh = cls.update_manifests.build_manifest()

    def _load_yaml(self, name: str) -> dict:
        with open(REPO_ROOT / name) as f:
            return yaml.safe_load(f) or {}

    def testModelsManifestUpToDate(self) -> None:
        """models.yaml matches the files on disk (paths, sizes, checksums).

        Rebuilds the manifest from the working tree and compares the per-file
        entries to the committed models.yaml. Any added, removed, resized, or
        re-checksummed model file that was not followed by
        ``scripts/update_manifests.py`` makes this fail.
        """
        committed = self._load_yaml("models.yaml")
        for method in ("ai_donut", "tarts"):
            self.assertEqual(
                committed.get(method, {}),
                self.fresh.get(method, {}),
                msg=(
                    f"models.yaml is out of date for '{method}'. "
                    f"Run scripts/update_manifests.py and commit the result."
                ),
            )

    def testHistoryCoversCurrentModels(self) -> None:
        """Every current model checksum is recorded in model_history.yaml.

        model_history.yaml is append-only, so it may contain extra (retired)
        hashes, but it must contain an entry for every model file currently on
        disk.
        """
        history = self._load_yaml("model_history.yaml")
        for _, _, _, entry in self.update_manifests.iter_manifest_files(self.fresh):
            self.assertIn(
                entry["sha256"],
                history,
                msg=(
                    f"{entry['path']} (sha256 {entry['sha256']}) is missing from "
                    f"model_history.yaml. Run scripts/update_manifests.py and commit."
                ),
            )


if __name__ == "__main__":
    unittest.main()
