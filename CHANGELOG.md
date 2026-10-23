# Changelog: from the original project to this release

## 2026-10-23: tests, checks and CI
- The script is split into `transforms.py` (transform steps as functions), `checks.py` (data-quality checks) and `etl_pipeline.py` (read, call, write). Outputs are unchanged except for floating-point noise: state anxiety values are now written exactly as the CDC publishes them (27.7 instead of 27.699999999999996; largest change 1.4e-14).
- Run-time checks: each raw file's columns, a contiguous survey calendar, a complete state × period grid after imputation, and unique keys in every output. Row counts are logged at each stage, including 96 negative state-days (USAFacts corrections) and 102 state-days after the survey that are dropped.
- `final_all_combined.csv` adds `NationalValue`, the CDC's national estimate.
- `src/report.py` regenerates `docs/results.md` (every correlation) and the README figure, which now plots cases per day so the 28-day period 13 no longer looks like a spike.
- 19 pytest tests: transforms on hand-made rows (including the two bugs fixed earlier) and a contract for the committed outputs. `requirements-lock.txt` pins the versions behind the outputs.
- GitHub Actions: tests on Python 3.14 (pinned) and 3.10 (pandas 2), a drift check on `docs/results.md`, and gitleaks. Verified locally that pandas 2.3.3 and 3.0.6 produce byte-identical outputs and results.
- Spearman is computed as Pearson on ranks, because `method='spearman'` needs SciPy on pandas 2.

## 2026-10-23: review fixes
- Dates after the last survey period were assigned to period 40 instead of being dropped. The fix removes 299,383 cases (2021-09-14 and -15) from period 40 in `final_covid_anxiety.csv`; nothing else in that file changes.
- `final_all_combined.csv` now keeps its `TimePeriod` column and adds `PeriodDays` and `SocialDays`, so totals over periods of 6 to 28 days can be compared per day. Every existing value is unchanged.
- An `InstagramPosts` count is added to the daily and period tables. It shows that the rise in Instagram likes comes from the dataset's growing post volume.
- README: results table with per-day correlations (Economist retweets −0.50 per day vs 0.10 on totals), corrected size and date of the COVID snapshot, SHA-256 of the raw files, and no Tableau claims (no dashboard is included).
- The pipeline runs without warnings on pandas 3; leftover commented-out code removed.

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
