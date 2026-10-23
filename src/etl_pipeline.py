"""
Multi-source ETL pipeline: COVID-19 cases x CDC anxiety survey x social media engagement.

Extracts four public datasets (USAFacts, CDC/Census Household Pulse, Kaggle Instagram,
Kaggle @TheEconomist tweets), normalises them to a shared bi-weekly survey "time period"
grain, imputes the survey's missing periods, and loads three analysis-ready CSVs.

Original version: four-person graduate project in Business Intelligence, Texas Tech University (2021).
Refactored for public release: relative paths, offline state reference file, pandas 2.x+.
"""

import datetime as dt
import io
from pathlib import Path

from check_requirements import check_requirements

# Before the third-party imports below, so a missing package stops with the install command.
check_requirements(Path(__file__).resolve().parents[1] / "requirements.txt")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
REF = ROOT / "data" / "reference"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

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

def load_states():
    """Read the Census state reference file locally; fall back to the Census URL."""
    local = REF / FDICT['states']
    if local.exists():
        return pd.read_csv(local, delimiter='|', dtype=str)
    import requests
    return pd.read_csv(io.StringIO(requests.get(STATE_URL, timeout=30).text), delimiter='|', dtype=str)

def apply_date_format(df, col='Date', span=False):
    # function that applies date format to dataframe; default column is 'date'
    # get column index number if col in df.columns
    index_no = df.columns.get_loc(col) if col in df.columns.tolist() else -1
    if index_no > -1 and not pd.api.types.is_datetime64_any_dtype(df[col]):
        df[col] = pd.to_datetime(df[col]).dt.floor('D')
    elif index_no > -1:
        df[col] = df[col].dt.floor('D')
    if span and index_no > -1:
        # spans the year, month, day to seperate columns when true
        df.insert(index_no+1, col+'_Year', df[col].dt.year.map("{:02}".format))
        df.insert(index_no+2, col+'_Month', df[col].dt.month.map("{:02}".format))
        df.insert(index_no+3, col+'_Day', df[col].dt.day.map("{:02}".format))

def apply_timeperiod_str(df, start_date, end_date):
    # converts the date interval into a string
    df['TimePeriodGroup'] = (
        df[start_date].dt.month.map("{:02}".format) + "/" +
        df[start_date].dt.day.map("{:02}".format) + "/" +
        df[start_date].dt.year.astype(str) + "-" +
        df[end_date].dt.month.map("{:02}".format) + "/" +
        df[end_date].dt.day.map("{:02}".format) + "/" +
        df[end_date].dt.year.astype(str)
        )

def apply_timeperiod(tp, df, col_name):
    # time_periods need to be passed for this to work
    # applies categorical data to enumerae different time periods
    start_min = tp['TimePeriodStartDate'].min()
    end_max = tp['TimePeriodEndDate'].max()
    
    for i in tp.index:
        # tp is the timeperiod dataframe
        start = tp.loc[i, 'TimePeriodStartDate']
        end = tp.loc[i, 'TimePeriodEndDate']
        # create boolean series to record truths
        truths = df[col_name].between(start, end)
        df.loc[truths, 'TimePeriod'] = tp.loc[i, 'TimePeriod']
    # dates before the survey are marked -1; dates after it get no period and drop out of the groupbys
    df.loc[df[col_name] < start_min, 'TimePeriod'] = -1
    df.loc[df[col_name] > end_max, 'TimePeriod'] = np.nan

def clean_columns(df):
    df.columns = ["".join(x.title().split()) for x in df.columns]
    
# read in the csv files
df_covid = pd.read_csv(RAW / FDICT['covid'])
df_mentalhealth = pd.read_csv(RAW / FDICT['mentalhealth']) 
df_instagram = pd.read_csv(RAW / FDICT['insta'])
df_tweets = pd.read_csv(RAW / FDICT['twitter'], low_memory=False)
df_states = load_states()

# =============================================================================
# Clean data columns
# =============================================================================
clean_columns(df_mentalhealth)
clean_columns(df_instagram)
clean_columns(df_tweets)
clean_columns(df_states)

# =============================================================================
# clean instagram dataframe
# =============================================================================
# changing head due to mispelled word and ease view
df_cleaning_instagram = df_instagram.copy()

drop = 'Year,Month,Day,UserUuid,DaysPassedFromPost,LikesScore,Type,Hour,Minute'.split(',')
for x in drop:
    df_cleaning_instagram.drop(x, inplace=True, axis=1)
    
df_cleaning_instagram.rename(columns = {'DatePosted':'Date',
                                        'NumerOfTags': 'InstagramTags', 
                                        'Likes': 'InstagramLikes', 
                                        'NumerOfComments' : 'InstagramComments'}, inplace = True)
df_cleaning_instagram['InstagramPosts'] = 1  # summed per day below; the dataset's daily volume grows over time
apply_date_format(df_cleaning_instagram, 'Date', True)

df_cleaning_instagram.set_index('Date', inplace=True)
df_cleaning_instagram = df_cleaning_instagram.sort_index().loc['2019-04-24':'2021-02-27', :]
df_cleaning_instagram.reset_index(inplace=True)
df_cleaning_instagram = df_cleaning_instagram.groupby(['Date', 'Date_Year', 'Date_Month', 'Date_Day']).sum(numeric_only=True)
df_cleaning_instagram.reset_index(inplace=True)

# =============================================================================
# clean twitter dataframe
# =============================================================================
df_cleaning_tweets = df_tweets.copy()

drop = ('id,created_at,conversation_id,time,timezone,user_id,username,name,place,'
        'tweet,language,mentions,urls,photos,cashtags,link,retweet,quote_url,video,thumbnail,'
        'geo,source,user_rt_id,user_rt,retweet_id,reply_to,near,retweet_date,translate,trans_src,trans_dest').split(',')

# drop identifiers and free text (usernames, user ids, tweet bodies) -- only engagement counts are kept
df_cleaning_tweets.drop(columns=[x.title() for x in drop], inplace=True)

df_cleaning_tweets.rename(columns = {'Replies_Count': 'EconReplies', 
                                     'Likes_Count': 'EconLikes', 
                                     'Retweets_Count' : 'EconRetweets', 
                                     'Tags':'EconTags'}, inplace = True)

# filter econ tweets by date
apply_date_format(df_cleaning_tweets, 'Date', False)
df_cleaning_tweets.set_index('Date', inplace=True)
df_cleaning_tweets = df_cleaning_tweets.sort_index().loc['2019-04-24':'2021-02-27', :]
df_cleaning_tweets.reset_index(inplace=True)

# Hashtags holds a list literal such as "['covid', 'economy']": two quotes per tag
df_cleaning_tweets['EconTags'] = df_cleaning_tweets['Hashtags'].str.count('\'') / 2

for x in 'EconReplies, EconRetweets, EconLikes, EconTags'.split(', '):
    df_cleaning_tweets[x] = pd.to_numeric(df_cleaning_tweets[x])
apply_date_format(df_cleaning_tweets, 'Date', True)

df_cleaning_tweets = df_cleaning_tweets.groupby(['Date', 'Date_Year', 'Date_Month', 'Date_Day']).sum(numeric_only=True)
df_cleaning_tweets.reset_index(inplace=True)

# =============================================================================
# transform covid confirmed cases
# =============================================================================
df_cleaning_covid = df_covid.drop(columns='countyFIPS').groupby(['State', 'StateFIPS']).sum(numeric_only=True).copy()  # consolidated, or diff() warns about a fragmented frame
df_cleaning_covid = df_cleaning_covid.diff(axis=1)
df_cleaning_covid.reset_index(inplace=True)
df_cleaning_covid = df_cleaning_covid.melt(id_vars=['State', 'StateFIPS'], value_vars=df_cleaning_covid.columns[2:], var_name='Date', value_name='PositiveCases')
apply_date_format(df_cleaning_covid, 'Date', True)
df_cleaning_covid.fillna(0, inplace=True)
# the survey's time periods are needed to group these further

# =============================================================================
# Isolate time periods from mental health
# =============================================================================
df_time_period = (df_mentalhealth[['TimePeriodStartDate', 'TimePeriodEndDate', 'Phase', 'TimePeriod']].drop_duplicates().reset_index(drop=True))

# apply dateformat to time periods then sort by date
apply_date_format(df_time_period, 'TimePeriodStartDate', False)
apply_date_format(df_time_period, 'TimePeriodEndDate', False)
df_time_period.sort_values(by='TimePeriodStartDate', inplace=True)
# notice time period is 1 when phase is -1

# fix timeperiods
df_time_period.index += 1
df_time_period.reset_index(inplace = True)
df_time_period['TimePeriod'] = df_time_period['index']
df_time_period.drop(columns='index', inplace = True)

# Fix missing trailing date for mental health time period
last_day = df_time_period.TimePeriodEndDate.max() + dt.timedelta(days = 1)
df_time_period.loc[df_time_period['Phase'] != str(-1), 'TimePeriodEndDate'] = df_time_period['TimePeriodStartDate'].shift(periods=-1, fill_value=last_day) - dt.timedelta(days = 1)
df_time_period.drop(columns='Phase', inplace=True)

df_time_period1 = df_time_period.copy()

apply_date_format(df_time_period, 'TimePeriodStartDate', True)
apply_date_format(df_time_period, 'TimePeriodEndDate', True)
apply_timeperiod_str(df_time_period, 'TimePeriodStartDate', 'TimePeriodEndDate')

# =============================================================================
# clean mental health dataframe
# =============================================================================
# change the indicator of mentalhealth for easier viewing and to extract anxiety
df_mentalhealth.loc[df_mentalhealth['Indicator'] == "Symptoms of Depressive Disorder", 'Indicator'] = "depression"
df_mentalhealth.loc[df_mentalhealth['Indicator'] == "Symptoms of Anxiety Disorder", 'Indicator'] = "anxiety"
df_mentalhealth.loc[df_mentalhealth['Indicator'] == "Symptoms of Anxiety Disorder or Depressive Disorder", 'Indicator'] = "both"

df_cleaning_mental = df_mentalhealth.copy()

# drop unneeded columns
drop = 'Subgroup, TimePeriodLabel, ConfidenceInterval, QuartileRange'.split(', ')
df_cleaning_mental.drop(drop, axis=1, inplace=True)

# =============================================================================
# Isolate anxiety from mental health and clean anxiety dataset
# =============================================================================
df_anxiety_states = df_cleaning_mental[(df_cleaning_mental['Group'] == "By State") & (df_cleaning_mental['Indicator'] == 'anxiety')]

keep = ['State', 'TimePeriodStartDate', 'Value', 'LowCi', 'HighCi']
df_anxiety_states = df_anxiety_states[keep]

apply_date_format(df_anxiety_states, 'TimePeriodStartDate', False)

# cross join (pandas >= 1.2) builds a complete State x TimePeriod grid so missing survey periods surface as NaN
# =============================================================================
# Get unique states from df_anxiety_states and cross join with df_time_period to get cartesian product
# =============================================================================
df_state_time_period = pd.DataFrame(df_anxiety_states['State'].drop_duplicates()).merge(df_time_period.TimePeriodStartDate, how='cross')

# left join to get remaining data
df_state_time_period = df_state_time_period.merge(df_time_period,
                                                  how='left', on=['TimePeriodStartDate'])

df_anxiety_states = df_state_time_period.merge(df_anxiety_states,
                                               how='left', on=['State', 'TimePeriodStartDate'])

   

# =============================================================================
# How we replaced value, HighCi, and LowCi according to time period before and after missing one for each state
# =============================================================================
# Four survey periods (CDC "Phase -1" gaps) have no state estimates. Each gap is a single
# interior period, so impute as the mean of the previous and next period *within the same state*.
ci_cols = ['Value', 'LowCi', 'HighCi']
df_avg_value = (df_anxiety_states[['State', 'TimePeriod'] + ci_cols]
                .sort_values(['State', 'TimePeriod']).copy())
by_state = df_avg_value.groupby('State')[ci_cols]
df_avg_value[ci_cols] = df_avg_value[ci_cols].fillna((by_state.shift(1) + by_state.shift(-1)) / 2)

df_anxiety_states = df_anxiety_states.merge(df_states.drop(columns=['State','Statens']), how = 'inner', left_on = 'State', right_on = 'State_Name')
df_anxiety_states.drop('State_Name', axis = 1, inplace = True)

df_final_anxiety = df_anxiety_states.merge(df_avg_value, how = 'inner', on = ['State', 'TimePeriod'])
df_final_anxiety = df_final_anxiety.drop(['Value_x', 'LowCi_x','HighCi_x'], axis = 1)
df_final_anxiety.rename(columns = {'Value_y':'Value', 'LowCi_y':'LowCi', 'HighCi_y' : 'HighCi', 'Stusab':'State_Abr'}, inplace = True)

# =============================================================================
# apply timeperiod groups to instagram, twitter and covid df
# =============================================================================
apply_timeperiod(df_time_period, df_cleaning_instagram, 'Date')
df_final_instagram = df_cleaning_instagram.copy()
apply_timeperiod(df_time_period, df_cleaning_tweets, 'Date')
df_final_tweets = df_cleaning_tweets.copy()
apply_timeperiod(df_time_period, df_cleaning_covid, 'Date')
df_final_covid = df_cleaning_covid.copy()

# =============================================================================
# 1st dataframe: merge covid and anxiety dataframes by State and Time Period
# =============================================================================
df_covid_anxiety = df_final_covid.merge(df_final_anxiety, how = 'left', left_on = ['State','TimePeriod'], right_on = ['State_Abr','TimePeriod'])

df_covid_anxiety_final = df_covid_anxiety[['State_x', 'TimePeriod','PositiveCases', 'Value', 'LowCi', 'HighCi']].groupby(
    ['State_x', 'TimePeriod']).agg(
    {'PositiveCases': np.sum,
    'Value': np.mean,
    'LowCi': np.mean,
    'HighCi': np.mean})
df_covid_anxiety_final.reset_index(inplace = True)
del df_covid_anxiety
# write to file
df_covid_anxiety_final.sort_values(by=['TimePeriod', 'State_x'], kind='stable').to_csv(OUT / FDICT['out1'], sep=',', index = False)

# =============================================================================
# 2nd dataframe: merge covid, twitter, and instagram by Year, Month, Day
# =============================================================================
df_social = df_final_tweets.merge(df_final_instagram, how = 'left', on = ['Date','Date_Year', 'Date_Month', 'Date_Day', 'TimePeriod'])
df_covid_bydate = df_final_covid.drop(columns=['State', 'StateFIPS']).groupby(['TimePeriod', 'Date','Date_Year', 'Date_Month', 'Date_Day']).sum(numeric_only=True)
df_covid_bydate.reset_index(inplace=True)

df_covid_social_final = df_social.merge(df_covid_bydate, how='left', on = ['TimePeriod', 'Date','Date_Year', 'Date_Month', 'Date_Day'])
col = df_covid_social_final.pop('TimePeriod')
df_covid_social_final.insert(0, "TimePeriod", col)
df_covid_social_final.drop(columns=['Date_Year', 'Date_Month', 'Date_Day'], inplace=True)

# write to file
df_covid_social_final.sort_values(by=['Date']).to_csv(OUT / FDICT['out2'], sep=',', index = False)

# =============================================================================
# 3rd dataframe: all combined by time period
# =============================================================================
df_covid_social_byperiod = df_covid_social_final.drop(columns='Date').groupby(by=['TimePeriod']).sum(numeric_only=True)
df_covid_anxiety_byperiod = df_covid_anxiety_final.drop(columns='State_x').groupby(by=['TimePeriod']).agg(
    {'PositiveCases': np.sum,
    'Value': np.mean,
    'LowCi': np.mean,
    'HighCi': np.mean})

df_all_final = df_covid_social_byperiod.merge(df_covid_anxiety_byperiod, how='inner', on='TimePeriod')
df_all_final.drop(columns='PositiveCases_x', inplace=True)
df_all_final.rename(columns={'PositiveCases_y': 'PositiveCases'}, inplace=True)

# periods last 6 to 28 days, so totals need these lengths to be compared per day
period_days = (df_time_period1['TimePeriodEndDate'] - df_time_period1['TimePeriodStartDate']).dt.days + 1
df_all_final.insert(0, 'PeriodDays', period_days.set_axis(df_time_period1['TimePeriod']))  # length of the survey period
df_all_final.insert(1, 'SocialDays', df_covid_social_final.groupby('TimePeriod').size())   # days with social data
df_all_final.reset_index(inplace=True)

# write to file
df_all_final.to_csv(OUT / FDICT['out3'], sep=',', index = False)

print(f'Wrote {FDICT["out1"]}, {FDICT["out2"]}, {FDICT["out3"]} to {OUT}')
