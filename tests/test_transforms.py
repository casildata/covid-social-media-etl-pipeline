"""Each transform on a few hand-made rows, so the logic is checked without the raw data."""

import numpy as np
import pandas as pd
import pytest

import checks
import transforms as tf

TP = pd.DataFrame({'TimePeriod': [1, 2],
                   'TimePeriodStartDate': pd.to_datetime(['2020-01-01', '2020-01-08']),
                   'TimePeriodEndDate': pd.to_datetime(['2020-01-07', '2020-01-14'])})


def survey(rows):
    """A tiny Household Pulse table in the shape clean_columns produces."""
    cols = ['Indicator', 'Group', 'State', 'Phase', 'TimePeriodStartDate', 'TimePeriodEndDate', 'Value', 'LowCi', 'HighCi']
    return pd.DataFrame(rows, columns=cols)


def test_clean_columns_matches_the_raw_headers():
    df = tf.clean_columns(pd.DataFrame(columns=['Time Period Start Date', 'replies_count', 'Numer of Tags']))
    assert df.columns.tolist() == ['TimePeriodStartDate', 'Replies_Count', 'NumerOfTags']


def test_period_boundaries_and_sentinels():
    dates = pd.Series(pd.to_datetime(['2019-12-31', '2020-01-01', '2020-01-07', '2020-01-08', '2020-01-15']))
    got = tf.assign_time_period(dates, TP)
    assert got.iloc[:4].tolist() == [-1, 1, 1, 2]
    assert np.isnan(got.iloc[4])  # after the last period: dropped, not folded into period 2


def test_time_periods_are_numbered_by_date_and_made_contiguous():
    mh = survey([
        # file order is not date order; phase 1 ends leave a day uncovered; the gap row keeps its own end
        ('x', 'By State', 'A', '1', '05/07/2020', '05/12/2020', 1, 1, 1),
        ('x', 'By State', 'A', '1', '04/23/2020', '05/05/2020', 1, 1, 1),
        ('x', 'By State', 'A', '-1', '05/13/2020', '05/20/2020', 1, 1, 1),
        ('x', 'By State', 'A', '2', '05/21/2020', '05/26/2020', 1, 1, 1),
    ])
    tp = tf.build_time_periods(mh)
    assert tp['TimePeriod'].tolist() == [1, 2, 3, 4]
    assert tp['TimePeriodStartDate'].dt.strftime('%m-%d').tolist() == ['04-23', '05-07', '05-13', '05-21']
    assert tp['TimePeriodEndDate'].dt.strftime('%m-%d').tolist() == ['05-06', '05-12', '05-20', '05-26']
    checks.check_time_periods(tp)  # contiguous: does not raise


def test_overlapping_periods_are_rejected():
    tp = TP.assign(TimePeriodEndDate=pd.to_datetime(['2020-01-09', '2020-01-14']))
    with pytest.raises(checks.DataCheckError, match='period'):
        checks.check_time_periods(tp)


def test_new_cases_decumulate_and_roll_up_to_state():
    cov = pd.DataFrame({'countyFIPS': [1, 2, 3], 'County Name': ['a', 'b', 'c'], 'State': ['TX', 'TX', 'OK'],
                        'StateFIPS': [48, 48, 40], '1/1/2020': [1, 2, 0], '1/2/2020': [4, 2, 5], '1/3/2020': [4, 3, 5]})
    out = tf.daily_new_cases(cov).set_index(['State', 'Date'])['PositiveCases']
    assert out.loc['TX'].tolist() == [0, 3, 1]  # first day has no previous total
    assert out.loc['OK'].tolist() == [0, 5, 0]


def test_imputation_never_borrows_from_another_state():
    df = pd.DataFrame({'State': ['A', 'A', 'A', 'B', 'B', 'B'], 'TimePeriod': [1, 2, 3] * 2,
                       'Value': [10, np.nan, 20, 90, np.nan, 100],
                       'LowCi': [9, np.nan, 19, 89, np.nan, 99], 'HighCi': [11, np.nan, 21, 91, np.nan, 101]})
    out = tf.impute_gaps_within_state(df).set_index(['State', 'TimePeriod'])
    assert out.loc[('A', 2), 'Value'] == 15
    assert out.loc[('B', 2), 'Value'] == 95
    assert out.loc[('B', 2), 'HighCi'] == 96


def test_gap_at_a_state_boundary_stays_missing():
    # sorted by state, B's first period sits right after A's last: a plain shift would average A3 and B2
    df = pd.DataFrame({'State': ['A', 'A', 'A', 'B', 'B', 'B'], 'TimePeriod': [1, 2, 3] * 2,
                       'Value': [10, 15, 20, np.nan, 95, 100], 'LowCi': 0.0, 'HighCi': 0.0})
    out = tf.impute_gaps_within_state(df).set_index(['State', 'TimePeriod'])
    assert np.isnan(out.loc[('B', 1), 'Value'])


def test_anxiety_grid_imputes_the_gap_and_adds_state_codes():
    mh = survey([
        ('Symptoms of Anxiety Disorder', 'By State', 'Texas', '1', '01/01/2020', '01/07/2020', 30, 28, 32),
        ('Symptoms of Anxiety Disorder', 'By State', 'Texas', '1', '01/15/2020', '01/21/2020', 40, 38, 42),
        ('Symptoms of Depressive Disorder', 'By State', 'Texas', '1', '01/01/2020', '01/07/2020', 99, 99, 99),
        ('Symptoms of Anxiety Disorder', 'National Estimate', 'United States', '-1', '01/08/2020', '01/14/2020', np.nan, np.nan, np.nan),
    ])
    tp = tf.build_time_periods(mh)
    states = pd.DataFrame({'State_Name': ['Texas'], 'Stusab': ['TX']})
    out = tf.anxiety_by_state(mh, tp, states).set_index('TimePeriod')
    assert out['State_Abr'].unique().tolist() == ['TX']
    assert out['Value'].tolist() == [30, 35, 40]  # the gap period is the mean of its neighbours
    checks.check_anxiety_complete(out.reset_index(), len(tp))


def test_social_cleaning_keeps_only_dates_and_counts():
    insta = pd.DataFrame({'UserUuid': ['u1', 'u2', 'u1'], 'Likes': [10, 20, 5], 'DaysPassedFromPost': [1, 1, 1],
                          'LikesScore': [1, 1, 1], 'Type': ['p', 'p', 'p'], 'NumerOfTags': [1, 0, 2],
                          'NumerOfComments': [3, 4, 5],
                          'DatePosted': ['2020-01-01 08:00', '2020-01-01 21:00', '2020-01-02 09:30']})
    out = tf.clean_instagram(insta)
    assert out.columns.tolist() == ['Date', 'InstagramLikes', 'InstagramTags', 'InstagramComments', 'InstagramPosts']
    assert out['InstagramLikes'].tolist() == [30, 5]
    assert out['InstagramPosts'].tolist() == [2, 1]

    tweets = pd.DataFrame({'Id': [1, 2], 'User_Id': [7, 7], 'Username': ['econ', 'econ'], 'Name': ['E', 'E'],
                           'Tweet': ['text', 'text'], 'Date': ['2020-01-01', '2020-01-01'],
                           'Replies_Count': [1, 2], 'Retweets_Count': [3, 4], 'Likes_Count': [5, 6],
                           'Hashtags': ["['covid', 'economy']", '[]']})
    out = tf.clean_tweets(tweets)
    assert out.columns.tolist() == ['Date', 'EconReplies', 'EconRetweets', 'EconLikes', 'EconTags']
    assert out.iloc[0, 1:].tolist() == [3, 7, 11, 2]


def test_social_window_is_inclusive_and_drops_older_posts():
    tweets = pd.DataFrame({'Date': ['2019-04-23', tf.SOCIAL_START, tf.SOCIAL_END, '2021-02-28'],
                           'Replies_Count': 1, 'Retweets_Count': 1, 'Likes_Count': 1, 'Hashtags': '[]'})
    out = tf.clean_tweets(tweets)
    assert out['Date'].dt.strftime('%Y-%m-%d').tolist() == [tf.SOCIAL_START, tf.SOCIAL_END]


def test_missing_raw_column_names_the_file():
    with pytest.raises(checks.DataCheckError, match='tweets_eco.csv: missing column.*Likes_Count'):
        checks.require_columns(pd.DataFrame(columns=['Date', 'Replies_Count', 'Retweets_Count', 'Hashtags']),
                               'twitter', 'tweets_eco.csv')


def test_duplicate_keys_are_rejected():
    with pytest.raises(checks.DataCheckError, match='2 duplicate'):
        checks.check_unique(pd.DataFrame({'Date': [1, 1, 1]}), ['Date'], 'out2')
