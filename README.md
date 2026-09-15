# ts_aos_ai

Versioned storage for the Rubin Observatory Active Optics System (AOS) AI model
weights used for Zernike estimation: **AIDonut** and **TARTS**. Large model
files are stored with [git-lfs](https://git-lfs.com/).

## Layout

```
ts_aos_ai/
├── models.yaml                       # AUTO-GENERATED manifest of the CURRENT model files (path, sha256, size)
├── model_history.yaml                # APPEND-ONLY ledger: content hash -> model version (all versions, forever)
├── ups/
│   └── ts_aos_ai.table               # EUPS table; exports AI_DONUT_DATA_DIR and TARTS_DATA_DIR
├── scripts/
│   ├── strip_checkpoint.py           # remove training-only state (optimizer/LR) from Lightning .ckpt files
│   ├── update_manifests.py           # regenerate models.yaml + model_history.yaml; print hashes to pin
│   └── verify.py                     # verify files on disk against models.yaml (CI / pre-commit / post-pull)
├── ai_donut/model/
│   └── aidonut_*_v<N>_<YYYYMMDD>.pt   # AIDonut TorchScript model(s)
└── tarts/model/
    └── v<N>/
        ├── best_*.ckpt               # TARTS model weights
        └── ood_model.joblib          # out-of-distribution model
```

`dataset_params.yaml` is **not** stored here; it lives with the `tarts` package
(`$TARTS_DIR/python/tarts/dataset_params.yaml`) because it is coupled to that
code, and it is not checksum-verified.

## Tracing a hash back to a model version (`model_history.yaml`)

`models.yaml` describes only the *current* commit, so it cannot identify a model
from an old on-sky run whose weights have since been replaced. `model_history.yaml`
is an **append-only** ledger for exactly that: it maps every model file's SHA-256
content hash to its identity (method, version, filename), and entries are **never
removed** — so a hash recorded in butler provenance always resolves, even years
later.

`scripts/update_manifests.py` maintains it automatically: each run adds any new
hashes and leaves existing entries untouched. Example entry:

```yaml
f440caa8...6066:
  method: tarts
  version: v4
  file: best_finetuned_wavennet_coral.ckpt
  path: tarts/model/v4/best_finetuned_wavennet_coral.ckpt
  size: 173036073
  first_recorded: '2026-09-04'
  notes: ''            # free for manual annotation, e.g. the git tag it shipped under
```

To trace an on-sky run: take the model hash from butler (for AIDonut, the
`estimateZernikes.modelSha256` recorded in the task config; for TARTS, the
`wavenetSha256` / `alignetSha256` / ... config values, or the `modelChecksums`
string recorded in the task metadata) and look it up in `model_history.yaml`.

> Note: because the ledger records the hashes of the files *as stored*, TARTS
> entries hold the **stripped** checkpoint hashes (see below) — the same hashes
> ts_wep verifies at load time.

## Setup (EUPS)

This is a data-only package; setting it up exports the model data directories
the AOS pipelines reference. From a checkout:

```bash
setup -r .        # or: eups declare ts_aos_ai <version> -r . && setup ts_aos_ai <version>
```

That exports (see `ups/ts_aos_ai.table`):

```bash
AI_DONUT_DATA_DIR=$TS_AOS_AI_DIR/ai_donut/model
TARTS_DATA_DIR=$TS_AOS_AI_DIR/tarts/model
```

(`TS_AOS_AI_DIR` is set automatically by EUPS on setup.) The donut_viz pipelines
reference `$AI_DONUT_DATA_DIR` / `$TARTS_DATA_DIR`, so they resolve to this
package once it is set up.

## Checkpoint size (TARTS)

TARTS models are PyTorch Lightning training checkpoints. As trained, they carry
optimizer state (Adam's moment buffers, ~2x the model weights) and LR-scheduler
state that are only needed to *resume training* — inference does not use them.
TARTS loads its models with `<Module>.load_from_checkpoint(...)`, which reads
only `state_dict`, `hyper_parameters`, and `pytorch-lightning_version`.

So TARTS checkpoints are stored here **stripped** of that training-only state
via `scripts/strip_checkpoint.py`. The model weights are preserved
byte-for-byte, so the stripped model is numerically identical. This is a large
win — the v4 set drops from ~554 MB to ~177 MB:

| file | as trained | stored (stripped) |
| --- | --- | --- |
| best_finetuned_wavennet_coral.ckpt | 518 MB | 173 MB |
| best_alignnet_120.ckpt | 35 MB | 12 MB |
| best_aggregator_coral_rotate_mrsse.ckpt | 0.6 MB | 0.2 MB |

`strip_checkpoint.py` is idempotent (re-running on an already-stripped file is a
no-op), so it is safe to run on a whole version directory.

AIDonut `.pt` files are TorchScript inference models with no optimizer state to
strip, and their float32 weights do not compress meaningfully; they are stored
as-is.

## Branch and version model

**Every branch tree holds only the *latest* version of each model.** Historical
versions are recovered from **git history and tags**, not by keeping old files
in the tree. This keeps git-lfs downloads minimal.

- `develop` — integration branch; holds only the latest models.
- `main` — production branch; tagged to mark which version production uses.

### Why only the latest downloads from git-lfs

git-lfs fetches only the LFS objects reachable from the **checked-out tree**.
`git clone`, `git checkout <tag|branch>`, and `git pull` download only the files
present at that commit; full history is never fetched unless you explicitly run
`git lfs fetch --all`. Because each tree contains only the current version, any
clone or tag checkout downloads exactly one version per model. Old tags remain
usable — checking one out fetches that version's object on demand (the server
LFS store retains every version; this only limits *client download*).

## Updating a model (per-bump workflow)

Do this on a branch off `develop`, never by committing directly to `develop` or
`main`.

```bash
# 0. Make sure git-lfs is available (e.g. via your LSST stack setup) and set up:
git lfs install

# 1. Branch off develop
git checkout develop && git pull
git checkout -b <ticket>-update-model

# 2. Replace the model file: remove the superseded version, add the new one.
#    Filenames carry a version and date (aidonut_<...>_v<N>_<YYYYMMDD>.pt), so
#    the tree never accumulates versions.
git rm ai_donut/model/aidonut_unbinned_v1_20260903.pt
cp /path/to/new/aidonut_unbinned_v2_20261115.pt ai_donut/model/
git add ai_donut/model/aidonut_unbinned_v2_20261115.pt
#    For TARTS, replace the whole version dir, e.g. tarts/model/v4 -> v5.

# 3. TARTS only: strip training-only state from the Lightning checkpoints
#    before committing (see "Checkpoint size" below). Skip for AIDonut .pt.
python scripts/strip_checkpoint.py tarts/model/v5/*.ckpt

# 4. Regenerate models.yaml + the model_history.yaml ledger. This also prints
#    the SHA-256 of every model to paste into the donut_viz pipeline configs.
python scripts/update_manifests.py
git add models.yaml model_history.yaml

# 5. Sanity-check that on-disk files match the manifest.
python scripts/verify.py

# 6. Commit (the .pt/.ckpt/.joblib files go in via git-lfs).
git commit -m "Update <model> to v<N>"
git lfs ls-files            # confirm the model files are tracked as LFS objects

# 7. Open a PR to merge the branch back into develop.

# 8. Once merged, update production: merge develop -> main and tag the version.
git checkout main && git merge --no-ff develop
git tag -a v<N> -m "Production model set v<N>"
git push origin main --tags
```

### Tagging convention

Tag `main` for each production model set (e.g. `v5`, or a dated/semantic tag of
your choosing). The tag is what production deployments check out.

### Update the consuming pipelines (ts_wep / donut_viz)

The pinned checksums live in the donut_viz production pipeline YAMLs, so after a
bump also update those:

- **AIDonut** blueprints
  (`lsstCamRapidAnalysisPipeline_AiDonut_Bin1x.yaml` / `_Bin2x.yaml`): set
  `estimateZernikes.modelPath` to the new filename and
  `estimateZernikes.modelSha256` to the new hash printed by
  `update_manifests.py`.
- **TARTS** pipeline (`lsstCamRapidAnalysisTartsUnpairedPipeline.yaml`): set the
  path and hash for each model — `wavenetPath`/`wavenetSha256`,
  `alignetPath`/`alignetSha256`, `aggregatornetPath`/`aggregatornetSha256`,
  `oodModelPath`/`oodModelSha256` — using the hashes printed by
  `update_manifests.py`. Each file is verified against its `*Sha256` at task
  construction (empty digest skips the check), mirroring AiDonut.

ts_wep verifies these checksums when loading (`AiDonutAlgorithm` /
`CalcZernikesNeuralTask`), so a wrong version or an unfetched git-lfs pointer
stub fails fast with a clear error instead of silently producing bad Zernikes.

## Deploying / consuming a specific version

```bash
# Fresh clone of a specific production tag downloads only that version's files.
git clone -b v<N> <repo-url> ts_aos_ai

# On a long-lived checkout, drop superseded LFS objects to reclaim space:
git lfs prune
```

Set the package up so the pipelines resolve the model directories (see
[Setup (EUPS)](#setup-eups)):

```bash
setup -r .   # exports AI_DONUT_DATA_DIR and TARTS_DATA_DIR
```

Track `main` (or a tag), **not** `develop`, for production. Never run
`git lfs fetch --all` on a production checkout — it would pull every historical
version.
