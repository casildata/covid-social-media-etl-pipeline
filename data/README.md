# Data

Put these files in `data/raw/`. They are not committed because they are third-party data, and the social media files contain account identifiers.

| File | Source | Licence / terms |
|---|---|---|
| `covid_confirmed_usafacts.csv` | [USAFacts COVID-19 data](https://usafacts.org/visualizations/coronavirus-covid-19-spread-map/) (snapshot through 2021-09-29) | Free to use with attribution |
| `Indicators_of_Anxiety_or_Depression_Based_on_Reported_Frequency_of_Symptoms_During_Last_7_Days.csv` | [CDC NCHS / Census Household Pulse](https://data.cdc.gov/NCHS/Indicators-of-Anxiety-or-Depression-Based-on-Repor/8pt5-q6wp) | U.S. government, public domain |
| `Instagram_Data.csv` | Kaggle, Instagram posts dataset (Mpletsos, V.) | Per Kaggle dataset terms |
| `tweets_eco.csv` | Kaggle, @TheEconomist tweets (Bhatia, R.) | X/Twitter content, per platform terms |

`reference/state_fips.txt` is the U.S. Census Bureau state reference file (public domain). It's committed so the pipeline runs offline.

`processed/` holds the three pipeline outputs. They are aggregated counts and survey percentages, with no user identifiers or post text, and are safe to publish.
