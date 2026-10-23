# Data

Put these files in `data/raw/`. They are not committed because they are third-party data, and the social media files contain account identifiers.

| File | Source | Licence / terms |
|---|---|---|
| `covid_confirmed_usafacts.csv` | [USAFacts COVID-19 data](https://usafacts.org/visualizations/coronavirus-covid-19-spread-map/) (snapshot through 2021-09-15) | Free to use with attribution |
| `Indicators_of_Anxiety_or_Depression_Based_on_Reported_Frequency_of_Symptoms_During_Last_7_Days.csv` | [CDC NCHS / Census Household Pulse](https://data.cdc.gov/NCHS/Indicators-of-Anxiety-or-Depression-Based-on-Repor/8pt5-q6wp) | U.S. government, public domain |
| `Instagram_Data.csv` | Kaggle, Instagram posts dataset (Mpletsos, V.) | Per Kaggle dataset terms |
| `tweets_eco.csv` | Kaggle, @TheEconomist tweets (Bhatia, R.) | X/Twitter content, per platform terms |

The committed outputs were built from these exact 2021 snapshots. The sources have changed since, so a fresh download will run but give slightly different numbers. To check whether your copies match:

| File | SHA-256 |
|---|---|
| `covid_confirmed_usafacts.csv` | `14edecf2723aa571b4987146cc55d33c815c4d46e222ef0d4c1483a556fa51df` |
| `Indicators_of_Anxiety_or_Depression_…_Last_7_Days.csv` | `92a0c8c867065a9a288242bfffc1a641a06246df5cb55c3c7264802bea1d6468` |
| `Instagram_Data.csv` | `239bd72d3e6e6314cfde0f69eb18f8451a990199188c234f8e66e466a38d2a9d` |
| `tweets_eco.csv` | `b42679d2bd137c9a87601f963aaefeb2869bde118b874de08de7bb4b899157aa` |

`reference/state_fips.txt` is the U.S. Census Bureau state reference file (public domain). It's committed so the pipeline runs offline.

`processed/` holds the three pipeline outputs. They are aggregated counts and survey percentages, with no user identifiers or post text, and are safe to publish.
