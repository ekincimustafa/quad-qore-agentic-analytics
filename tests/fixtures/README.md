# EVDS producer/consumer contract fixture

`evds_manifest_v1/` is copied **byte for byte** from Afra's PR #58 commit
`75159498c545fe21cf385b4a826566a87172ea02`, under the same fixture path.
It contains synthetic observations for January–February 2021, three raw
responses and their receipts, the five-column Silver CSV, the coverage report,
and the manifest. It needs neither credentials nor network access.

Do not regenerate its hashes or remove `weekly_coverage` to make consumer
tests pass. `.gitattributes` preserves these exact bytes on Windows and Linux.
The embedded manifest object has only `overall_status`,
`calendar_verification`, and `months`; the standalone coverage report also
contains `schema_version` and `silver_sha256` and is not embedded wholesale.

`test_evds_weekly_coverage_integration.py` copies this fixture to a temporary
project and exercises `load_and_validate_manifest` and the actual CLI module
with `--html`. The same invalid-fixture matrix is checked through the loader
and CLI, including source-byte and existing-output preservation checks.
The BDDK parquet in those tests is independently synthetic and is not part
of the EVDS producer fixture.

These tests demonstrate contract compatibility, not acceptance of the real
60-month run or the three real sample-month comparisons tracked in #40.
