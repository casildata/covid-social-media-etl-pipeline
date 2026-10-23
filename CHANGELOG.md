# Changelog: from the original project to this release

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
