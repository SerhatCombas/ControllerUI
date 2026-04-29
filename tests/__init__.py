"""Architecture and import-boundary tests.

This package contains tests that verify architectural invariants of the
project (per `06_data_flow_and_architecture.md` §19 ADRs and 
`08_codex_execution_rules.md` §10).

These tests are cheap and are run first in the CI pipeline (Wave 1) so
that violations of fundamental invariants block all other testing.

See `12_ci_cd_pipeline.md` §6.5 for the full list of architecture tests.
"""
