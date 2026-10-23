"""Data-quality checks run by the pipeline. Each raises DataCheckError with a message
that names the file or table and what is wrong, so a changed download fails early
instead of deep inside a merge."""

import datetime as dt


class DataCheckError(ValueError):
    pass


# Raw columns the transforms read (after clean_columns, except the COVID file)
REQUIRED_COLUMNS = {
    'covid': ['countyFIPS', 'State', 'StateFIPS'],
    'mentalhealth': ['Indicator', 'Group', 'State', 'Phase', 'TimePeriodStartDate',
                     'TimePeriodEndDate', 'Value', 'LowCi', 'HighCi'],
    'insta': ['DatePosted', 'Likes', 'NumerOfTags', 'NumerOfComments'],
    'twitter': ['Date', 'Replies_Count', 'Retweets_Count', 'Likes_Count', 'Hashtags'],
    'states': ['State_Name', 'Stusab'],
}


def require_columns(df, source, filename):
    missing = [c for c in REQUIRED_COLUMNS[source] if c not in df.columns]
    if missing:
        raise DataCheckError(f'{filename}: missing column(s) {", ".join(missing)}. '
                             'Is this the file listed in data/README.md?')


def check_time_periods(tp):
    """Periods must be in order, each at least one day long, and leave no day uncovered."""
    if (tp['TimePeriodEndDate'] < tp['TimePeriodStartDate']).any():
        raise DataCheckError('survey periods: a period ends before it starts')
    next_start = tp['TimePeriodStartDate'].shift(-1).iloc[:-1]
    expected = tp['TimePeriodEndDate'].iloc[:-1] + dt.timedelta(days=1)
    bad = tp['TimePeriod'].iloc[:-1][next_start != expected]
    if len(bad):
        raise DataCheckError(f'survey periods: gap or overlap after period(s) {bad.tolist()}')


def check_unique(df, keys, table):
    dup = df.duplicated(subset=keys)
    if dup.any():
        raise DataCheckError(f'{table}: {dup.sum()} duplicate row(s) for {keys}')


def check_anxiety_complete(anxiety, n_periods):
    """Every state has every period, and imputation left no gaps."""
    per_state = anxiety.groupby('State')['TimePeriod'].nunique()
    short = per_state[per_state != n_periods]
    if len(short):
        raise DataCheckError(f'anxiety: {len(short)} state(s) without all {n_periods} periods, e.g. {short.index[0]}')
    missing = anxiety['Value'].isna().sum()
    if missing:
        raise DataCheckError(f'anxiety: {missing} state-period value(s) still missing after imputation '
                             '(two gap periods in a row cannot be imputed from neighbours)')
