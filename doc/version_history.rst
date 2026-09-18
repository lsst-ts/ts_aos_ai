.. _ts_aos_ai-version_history:

##################
Version History
##################

.. WARNING: DO NOT MANUALLY EDIT THIS FILE.

   Release notes are now managed using towncrier.
   The following comment marks the start of the automatically managed content.
   For help in how to create the "news fragments" see the README page in the
   doc directory.

   Do not remove the following comment line.

.. towncrier release notes start

v0.2.0 (2026-09-18)
===================

New Features
------------

- Store the AiDonut and TARTS model weights under git-lfs, with `models.yaml` (a manifest of the current model files), an append-only `model_history.yaml` ledger mapping content hash to model version (for tracing on-sky runs), an EUPS table exporting `AI_DONUT_DATA_DIR`/`TARTS_DATA_DIR`, and `scripts/` to regenerate the manifests, verify checksums, and strip training-only state from Lightning checkpoints (TARTS v4 ~554 MB -> ~177 MB). (`RSO-821 <https://rubinobs.atlassian.net//browse/RSO-821>`_)


v0.1.0 (2026-09-09)
===================

Other Changes and Additions
---------------------------

- Added standard Telescope and Site repository boilerplate: pre-commit configuration (`.pre-commit-config.yaml`, `.ts_pre_commit_config.yaml`, `.ruff.toml`, `.mypy.ini`), license headers (`.LICENSE.txt`, `COPYRIGHT`), towncrier-based version history (`towncrier.toml`, `doc/`), packaging/build files (`pyproject.toml`, `setup.cfg`, `SConstruct`, `ups/ts_aos_ai.table`), the `Jenkinsfile`, and GitHub lint/news workflows. (`RSO-923 <https://rubinobs.atlassian.net//browse/RSO-923>`_)
