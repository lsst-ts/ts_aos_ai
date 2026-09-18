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

"""Strip training-only state from PyTorch Lightning ``.ckpt`` files.

A Lightning training checkpoint carries optimizer state (e.g. Adam's moment
buffers, typically ~2x the size of the model weights) and LR-scheduler state
that are only needed to *resume training*. Inference does not use them: TARTS
loads its models with ``<Module>.load_from_checkpoint(...)``, which reads only
``state_dict``, ``hyper_parameters``, and ``pytorch-lightning_version``.

This tool removes the training-only keys and rewrites the checkpoint. The model
weights (``state_dict``) and everything ``load_from_checkpoint`` needs are
preserved byte-for-byte, so the stripped model is numerically identical. For
the TARTS v4 wavenet this takes the file from ~518 MB to ~173 MB.

Run this on new TARTS checkpoints before committing them (see README.md), then
regenerate the manifests with ``scripts/update_manifests.py``.

Usage:
    python scripts/strip_checkpoint.py tarts/model/v4/*.ckpt
"""

import argparse
import os
import tempfile

import torch

# Keys written only for resuming training; not read by load_from_checkpoint.
TRAINING_ONLY_KEYS = ("optimizer_states", "lr_schedulers")


def strip_file(path: str) -> None:
    """Remove training-only keys from a single checkpoint, in place."""
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(ckpt, dict):
        print(f"  {path}: not a dict checkpoint, skipping")
        return
    present = [k for k in TRAINING_ONLY_KEYS if k in ckpt]
    if not present:
        print(f"  {path}: already lean (no {'/'.join(TRAINING_ONLY_KEYS)}), skipping")
        return

    before = os.path.getsize(path)
    for key in present:
        del ckpt[key]

    # Write to a temp file in the same directory, then atomically replace, so
    # an interrupted save cannot corrupt the original.
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(suffix=".ckpt", dir=directory)
    os.close(fd)
    try:
        torch.save(ckpt, tmp)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise

    after = os.path.getsize(path)
    print(f"  {path}: removed {present}  {before / 1e6:.1f} -> {after / 1e6:.1f} MB")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("checkpoints", nargs="+", help="Checkpoint file(s) to strip.")
    args = parser.parse_args()

    print("Stripping training-only state from checkpoint(s):")
    for path in args.checkpoints:
        strip_file(path)


if __name__ == "__main__":
    main()
