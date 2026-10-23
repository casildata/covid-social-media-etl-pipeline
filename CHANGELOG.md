# Changelog: from the original project to this release

## Refactor for publication (2026)
- Consolidated the team's script versions into one canonical pipeline (`src/etl_pipeline.py`) under version control.
- Replaced absolute file paths with repository-relative paths; the Census state reference loads from a local file, with the URL as a fallback.
- Updated for pandas 2.x/3.x compatibility.
- Improved gap-period imputation to run per state (`groupby('State').shift()`), so a missing period can never borrow a neighbouring state's value.
- Made output ordering deterministic.
- The dependency check no longer installs packages; it prints the `pip` command and stops.

**Verification:** re-ran on the original raw data with pandas 3.0.5; all three outputs match the 2021 deliverable (max numeric difference < 1e-13).

## Not included
Third-party materials from the original program, raw data and draft reports.
