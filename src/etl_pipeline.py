"""
Multi-source ETL pipeline: COVID-19 cases x CDC anxiety survey x social media engagement.

Extracts four public datasets (USAFacts, CDC/Census Household Pulse, Kaggle Instagram,
Kaggle @TheEconomist tweets), normalises them to a shared bi-weekly survey "time period"
grain, imputes the survey's missing periods, and loads three analysis-ready CSVs.
The transforms live in transforms.py and the data-quality checks in checks.py.

Original version: four-person graduate project in Business Intelligence, Texas Tech University (2021).
Refactored for public release: relative paths, offline state reference file, pandas 2.x+.
"""

import io
import logging
from pathlib import Path

from check_requirements import check_requirements

ROOT = Path(__file__).resolve().parents[1]

# Before the third-party imports below, so a missing package stops with the install command.
check_requirements(ROOT / "requirements.txt")

import pandas as pd  # noqa: E402

import checks  # noqa: E402
import transforms as tf  # noqa: E402

RAW = ROOT / "data" / "raw"
REF = ROOT / "data" / "reference"
OUT = ROOT / "data" / "processed"

FDICT = {
    'covid': 'covid_confirmed_usafacts.csv',
    'mentalhealth': 'Indicators_of_Anxiety_or_Depression_Based_on_Reported_Frequency_of_Symptoms_During_Last_7_Days.csv',
    'insta': 'Instagram_Data.csv',
    'twitter': 'tweets_eco.csv',
    'states': 'state_fips.txt',  # U.S. Census Bureau state reference (public domain)
    'out1': 'final_covid_anxiety.csv',
    'out2': 'final_covid_socialmedia.csv',
    'out3': 'final_all_combined.csv',
}
STATE_URL = 'https://www2.census.gov/geo/docs/reference/state.txt'

log = logging.getLogger('etl')


def load_states():
    """Read the Census state reference file locally; fall back to the Census URL."""
    local = REF / FDICT['states']
    if local.exists():
        return pd.read_csv(local, delimiter='|', dtype=str)
    import requests
    return pd.read_csv(io.StringIO(requests.get(STATE_URL, timeout=30).text), delimiter='|', dtype=str)


def extract():
    """Read the raw files and check that each has the columns the transforms need."""
    missing = [FDICT[k] for k in ('covid', 'mentalhealth', 'insta', 'twitter') if not (RAW / FDICT[k]).exists()]
    if missing:
        raise SystemExit(f'Missing in {RAW}: {", ".join(missing)}. See data/README.md for downloads.')
    raw = {
        'covid': pd.read_csv(RAW / FDICT['covid']),
        'mentalhealth': tf.clean_columns(pd.read_csv(RAW / FDICT['mentalhealth'])),
        'insta': tf.clean_columns(pd.read_csv(RAW / FDICT['insta'])),
        'twitter': tf.clean_columns(pd.read_csv(RAW / FDICT['twitter'], low_memory=False)),
        'states': tf.clean_columns(load_states()),
    }
    for source, df in raw.items():
        checks.require_columns(df, source, FDICT[source])
        log.info(f'read {FDICT[source][:40]:<40} {len(df):>9,} rows x {df.shape[1]} columns')
    return raw


def main():
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    raw = extract()

    tp = tf.build_time_periods(raw['mentalhealth'])
    checks.check_time_periods(tp)
    log.info(f'survey periods: {len(tp)} ({tp.TimePeriodStartDate.min():%Y-%m-%d} to '
             f'{tp.TimePeriodEndDate.max():%Y-%m-%d}), contiguous')

    anxiety = tf.anxiety_by_state(raw['mentalhealth'], tp, raw['states'])
    checks.check_anxiety_complete(anxiety, len(tp))
    log.info(f'anxiety: {anxiety.State.nunique()} states x {len(tp)} periods, gap periods imputed within state')
    national = tf.anxiety_national(raw['mentalhealth'], tp)

    cases = tf.daily_new_cases(raw['covid'])
    checks.check_unique(cases, ['State', 'Date'], 'new cases')
    cases['TimePeriod'] = tf.assign_time_period(cases['Date'], tp)
    log.info(f'new cases: {len(raw["covid"]):,} counties -> {cases.State.nunique()} states x '
             f'{cases.Date.nunique()} days; {(cases.PositiveCases < 0).sum()} negative state-days kept '
             f'(USAFacts corrections); {cases.TimePeriod.isna().sum()} state-days after the survey dropped')

    instagram = tf.clean_instagram(raw['insta'])
    tweets = tf.clean_tweets(raw['twitter'])
    for df in (instagram, tweets):
        df['TimePeriod'] = tf.assign_time_period(df['Date'], tp)
    log.info(f'social: {len(raw["insta"]):,} posts -> {len(instagram)} days; '
             f'{len(raw["twitter"]):,} tweets -> {len(tweets)} days')

    out1 = tf.covid_anxiety(cases, anxiety)
    out2 = tf.covid_social(tweets, instagram, cases)
    out3 = tf.all_combined(out2, out1, tp, national)
    checks.check_unique(out1, ['State_x', 'TimePeriod'], FDICT['out1'])
    checks.check_unique(out2, ['Date'], FDICT['out2'])
    checks.check_unique(out3, ['TimePeriod'], FDICT['out3'])

    OUT.mkdir(parents=True, exist_ok=True)
    for name, df in (('out1', out1), ('out2', out2), ('out3', out3)):
        df.to_csv(OUT / FDICT[name], index=False, lineterminator='\n')
        log.info(f'wrote {FDICT[name]:<28} {len(df):>5} rows')


if __name__ == '__main__':
    main()
