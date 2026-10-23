"""Contract for the committed outputs. Runs without the raw data, so CI checks what readers download."""

from pathlib import Path

import pandas as pd
import pytest

import report

PROCESSED = Path(__file__).resolve().parents[1] / "data" / "processed"


@pytest.fixture(scope='module')
def out():
    return {name: pd.read_csv(PROCESSED / f'final_{name}.csv') for name in ('covid_anxiety', 'covid_socialmedia', 'all_combined')}


def test_schemas(out):
    assert out['covid_anxiety'].columns.tolist() == ['State_x', 'TimePeriod', 'PositiveCases', 'Value', 'LowCi', 'HighCi']
    assert out['covid_socialmedia'].columns.tolist() == [
        'TimePeriod', 'Date', 'EconReplies', 'EconRetweets', 'EconLikes', 'EconTags',
        'InstagramLikes', 'InstagramTags', 'InstagramComments', 'InstagramPosts', 'PositiveCases']
    assert out['all_combined'].columns.tolist() == [
        'TimePeriod', 'PeriodDays', 'SocialDays', 'EconReplies', 'EconRetweets', 'EconLikes', 'EconTags',
        'InstagramLikes', 'InstagramTags', 'InstagramComments', 'InstagramPosts', 'PositiveCases',
        'Value', 'LowCi', 'HighCi', 'NationalValue']


def test_no_identifier_or_text_columns(out):
    raw_identifiers = {'useruuid', 'user_id', 'username', 'name', 'tweet', 'id', 'link', 'urls', 'mentions', 'place', 'geo'}
    for df in out.values():
        assert not raw_identifiers & {c.lower() for c in df.columns}
        # the only text left is the date and the two-letter state code
        text = df.select_dtypes(exclude='number')
        assert set(text.columns) <= {'Date', 'State_x'}
        if 'State_x' in text:
            assert text['State_x'].str.fullmatch(r'[A-Z]{2}').all()


def test_state_by_period_grid_is_complete(out):
    df = out['covid_anxiety']
    assert df['State_x'].nunique() == 51
    assert df['TimePeriod'].nunique() == 42  # 41 survey periods plus -1 (before the survey)
    assert not df.duplicated(['State_x', 'TimePeriod']).any()
    assert len(df) == 51 * 42
    assert df.loc[df['TimePeriod'] > 0, 'Value'].notna().all()  # gap periods imputed


def test_daily_table_has_every_day_once(out):
    dates = pd.to_datetime(out['covid_socialmedia']['Date'])
    assert dates.is_unique and dates.is_monotonic_increasing
    assert (dates.diff().dropna().dt.days == 1).all()
    assert (dates.min(), dates.max()) == (pd.Timestamp('2019-04-24'), pd.Timestamp('2021-02-27'))


def test_period_table_matches_the_others(out):
    period = out['all_combined'].set_index('TimePeriod')
    assert period.index.tolist() == [-1] + list(range(1, 28))
    assert period['SocialDays'].sum() == len(out['covid_socialmedia'])
    assert period.loc[1:, 'PeriodDays'].between(6, 28).all()
    # cases add up across tables: state x period -> period
    by_state = out['covid_anxiety'].groupby('TimePeriod')['PositiveCases'].sum()
    assert (by_state.loc[period.index] == period['PositiveCases']).all()
    # and day -> period, for every period the social data covers in full (27 is cut at 2021-02-27)
    by_day = out['covid_socialmedia'].groupby('TimePeriod')['PositiveCases'].sum()
    assert (by_day.loc[1:26] == period.loc[1:26, 'PositiveCases']).all()


def test_results_file_is_current(out):
    expected = report.render_results(out['all_combined'])
    assert report.RESULTS.read_text(encoding='utf-8') == expected, 'run python src/report.py'


def test_headline_correlation(out):
    rows = {label: (t, d, c) for label, n, t, d, c in report.correlations(out['all_combined'])}
    total, per_day, changes = rows['Adults with anxiety symptoms (mean of 51 state estimates)']
    assert round(total, 2) == 0.80 and round(per_day, 2) == 0.83 and round(changes, 2) == 0.54
