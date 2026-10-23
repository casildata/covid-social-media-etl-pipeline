"""Transform steps of the pipeline: DataFrames in, DataFrames out, no file access.

etl_pipeline.py reads the raw files, calls these in order and writes the outputs.
Keeping them free of I/O lets tests/test_transforms.py run each one on a few hand-made rows.
"""

import datetime as dt

import numpy as np
import pandas as pd

SOCIAL_START, SOCIAL_END = '2019-04-24', '2021-02-27'  # window covered by both social datasets

# Allow-lists: only these columns survive cleaning, so identifiers and free text can't leak through
INSTAGRAM_KEEP = {'DatePosted': 'Date', 'Likes': 'InstagramLikes',
                  'NumerOfTags': 'InstagramTags', 'NumerOfComments': 'InstagramComments'}
TWEETS_KEEP = {'Date': 'Date', 'Replies_Count': 'EconReplies', 'Retweets_Count': 'EconRetweets',
               'Likes_Count': 'EconLikes', 'Hashtags': 'Hashtags'}


def clean_columns(df):
    """'Time Period Start Date' -> 'TimePeriodStartDate', 'replies_count' -> 'Replies_Count'."""
    df.columns = ["".join(x.title().split()) for x in df.columns]
    return df


def to_day(s):
    """Parse dates (or timestamps) and drop the time of day."""
    if not pd.api.types.is_datetime64_any_dtype(s):
        s = pd.to_datetime(s)
    return s.dt.floor('D')


def assign_time_period(dates, tp):
    """Survey TimePeriod for each date: -1 before the first period, NaN after the last.

    NaN rows drop out of the later groupbys, so dates past the survey are never
    folded into one of its periods.
    """
    out = pd.Series(np.nan, index=dates.index)
    for row in tp.itertuples():
        out[dates.between(row.TimePeriodStartDate, row.TimePeriodEndDate)] = row.TimePeriod
    out[dates < tp['TimePeriodStartDate'].min()] = -1
    return out


def build_time_periods(mh):
    """One row per survey period, numbered 1..n by start date, with contiguous end dates.

    The CDC's "Phase -1" rows are gaps between survey phases; they become periods
    of their own. Other periods end the day before the next one starts, because the
    published end dates leave a day or two uncovered between periods.
    """
    tp = (mh[['TimePeriodStartDate', 'TimePeriodEndDate', 'Phase']].drop_duplicates()
          .assign(TimePeriodStartDate=lambda d: to_day(d['TimePeriodStartDate']),
                  TimePeriodEndDate=lambda d: to_day(d['TimePeriodEndDate']))
          .sort_values('TimePeriodStartDate').reset_index(drop=True))
    tp.insert(0, 'TimePeriod', np.arange(1, len(tp) + 1))
    last_day = tp['TimePeriodEndDate'].max() + dt.timedelta(days=1)
    next_start = tp['TimePeriodStartDate'].shift(periods=-1, fill_value=last_day)
    not_gap = tp['Phase'] != '-1'
    tp.loc[not_gap, 'TimePeriodEndDate'] = next_start[not_gap] - dt.timedelta(days=1)
    return tp.drop(columns='Phase')


def clean_instagram(df):
    """Posts -> one row per day: likes, tags, comments and the number of posts."""
    df = df[list(INSTAGRAM_KEEP)].rename(columns=INSTAGRAM_KEEP)
    df['InstagramPosts'] = 1  # the dataset's daily volume grows over time, so keep the count
    df['Date'] = to_day(df['Date'])
    df = df[df['Date'].between(pd.Timestamp(SOCIAL_START), pd.Timestamp(SOCIAL_END))]
    return df.groupby('Date').sum().reset_index()


def clean_tweets(df):
    """Tweets -> one row per day: replies, retweets, likes and hashtags."""
    df = df[list(TWEETS_KEEP)].rename(columns=TWEETS_KEEP)
    df['Date'] = to_day(df['Date'])
    df = df[df['Date'].between(pd.Timestamp(SOCIAL_START), pd.Timestamp(SOCIAL_END))].copy()
    # Hashtags holds a list literal such as "['covid', 'economy']": two quotes per tag
    df['EconTags'] = df.pop('Hashtags').str.count('\'') / 2
    return df.groupby('Date').sum().reset_index()


def daily_new_cases(df_covid):
    """County x day cumulative cases (one column per date) -> state x day new cases (long)."""
    wide = df_covid.drop(columns='countyFIPS').groupby(['State', 'StateFIPS']).sum(numeric_only=True)
    new = wide.copy().diff(axis=1).reset_index()  # copy: consolidated, or diff() warns about a fragmented frame
    long = new.melt(id_vars=['State', 'StateFIPS'], var_name='Date', value_name='PositiveCases')
    long['Date'] = to_day(long['Date'])
    return long.fillna({'PositiveCases': 0})  # the first day has no previous total


def impute_gaps_within_state(df, cols=('Value', 'LowCi', 'HighCi')):
    """Fill a single missing period with the mean of its neighbours in the same state."""
    cols = list(cols)
    df = df.sort_values(['State', 'TimePeriod']).copy()
    by_state = df.groupby('State')[cols]
    df[cols] = df[cols].fillna((by_state.shift(1) + by_state.shift(-1)) / 2)
    return df


def anxiety_by_state(mh, tp, df_states):
    """Share of adults with anxiety symptoms, state x period, gaps imputed within state."""
    anx = mh[(mh['Group'] == 'By State') & (mh['Indicator'] == 'Symptoms of Anxiety Disorder')]
    anx = anx[['State', 'TimePeriodStartDate', 'Value', 'LowCi', 'HighCi']].copy()
    anx['TimePeriodStartDate'] = to_day(anx['TimePeriodStartDate'])

    # complete State x TimePeriod grid, so periods with no estimates surface as NaN
    grid = (pd.DataFrame(anx['State'].drop_duplicates())
            .merge(tp[['TimePeriodStartDate']], how='cross')
            .merge(tp[['TimePeriodStartDate', 'TimePeriod']], how='left', on='TimePeriodStartDate')
            .merge(anx, how='left', on=['State', 'TimePeriodStartDate']))

    # The four gap periods have no state estimates. Each is a single interior period.
    filled = impute_gaps_within_state(grid[['State', 'TimePeriod', 'Value', 'LowCi', 'HighCi']])

    codes = df_states[['State_Name', 'Stusab']].rename(columns={'State_Name': 'State', 'Stusab': 'State_Abr'})
    return grid[['State', 'TimePeriod']].merge(codes, how='inner', on='State').merge(
        filled, how='inner', on=['State', 'TimePeriod'])


def anxiety_national(mh, tp):
    """The CDC's national estimate per period (missing in the gap periods)."""
    nat = mh[(mh['Group'] == 'National Estimate') & (mh['Indicator'] == 'Symptoms of Anxiety Disorder')]
    nat = nat[['TimePeriodStartDate', 'Value']].assign(TimePeriodStartDate=lambda d: to_day(d['TimePeriodStartDate']))
    return (tp[['TimePeriodStartDate', 'TimePeriod']].merge(nat, how='left', on='TimePeriodStartDate')
            .set_index('TimePeriod')['Value'].rename('NationalValue'))


def covid_anxiety(cases, anxiety):
    """Output 1: state x period new cases with the period's anxiety estimate."""
    merged = cases.merge(anxiety, how='left', left_on=['State', 'TimePeriod'], right_on=['State_Abr', 'TimePeriod'])
    out = (merged[['State_x', 'TimePeriod', 'PositiveCases', 'Value', 'LowCi', 'HighCi']]
           .groupby(['State_x', 'TimePeriod'])
           .agg({'PositiveCases': 'sum', 'Value': 'mean', 'LowCi': 'mean', 'HighCi': 'mean'})
           .reset_index())
    return out.sort_values(by=['TimePeriod', 'State_x'], kind='stable')


def covid_social(tweets, instagram, cases):
    """Output 2: one row per day with social engagement and national new cases."""
    social = tweets.merge(instagram, how='left', on=['Date', 'TimePeriod'])
    by_date = cases.drop(columns=['State', 'StateFIPS']).groupby(['TimePeriod', 'Date']).sum().reset_index()
    out = social.merge(by_date, how='left', on=['TimePeriod', 'Date'])
    out.insert(0, 'TimePeriod', out.pop('TimePeriod'))
    return out.sort_values(by=['Date'])


def all_combined(social, covid_anx, tp, national):
    """Output 3: one row per period. PeriodDays and SocialDays turn totals into per-day rates."""
    social_by_period = social.drop(columns='Date').groupby('TimePeriod').sum()
    anx_by_period = (covid_anx.drop(columns='State_x').groupby('TimePeriod')
                     .agg({'PositiveCases': 'sum', 'Value': 'mean', 'LowCi': 'mean', 'HighCi': 'mean'}))
    out = (social_by_period.merge(anx_by_period, how='inner', on='TimePeriod')
           .drop(columns='PositiveCases_x').rename(columns={'PositiveCases_y': 'PositiveCases'}))
    period_days = (tp['TimePeriodEndDate'] - tp['TimePeriodStartDate']).dt.days + 1
    out.insert(0, 'PeriodDays', period_days.set_axis(tp['TimePeriod']))  # length of the survey period
    out.insert(1, 'SocialDays', social.groupby('TimePeriod').size())     # days with social data
    out['NationalValue'] = national                                       # aligned on TimePeriod
    return out.reset_index()
