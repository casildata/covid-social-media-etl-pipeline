# COVID-19 × Anxiety × Social Media: Multi-Source ETL Pipeline

**A Python/pandas pipeline that integrates four public datasets with incompatible grains, keys and date formats into analysis-ready tables, then explores how pandemic case counts tracked reported anxiety and social media engagement.**

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-2.x%20%7C%203.x-150458?logo=pandas)
![Tableau](https://img.shields.io/badge/viz-Tableau-E97627?logo=tableau&logoColor=white)
![Type](https://img.shields.io/badge/type-ETL%20%7C%20Data%20Integration-informational)
![License](https://img.shields.io/badge/license-MIT-green)

> **Origin:** a four-person graduate project in **Business Intelligence** at Texas Tech University (2021). Refactored in 2026 to run on current pandas. The refactored outputs were checked against the 2021 deliverable and match it exactly.

---

## TL;DR

- **Pipeline:** integrates four public datasets (COVID-19 cases, a CDC anxiety survey, Instagram posts and @TheEconomist tweets) plus a Census state reference, each with a different grain, key and date format, into three analysis-ready tables.
- **Finding:** new COVID-19 cases and the share of adults reporting anxiety symptoms moved together across 27 survey periods (**Pearson r = 0.80**). This is a correlation, not evidence of causation.
- **Privacy:** user IDs, usernames and post text are dropped before aggregation; only aggregated tables with no PII are published.
- **Reproducibility:** the 2026 refactor reproduces the 2021 deliverable's outputs exactly.

---

## Approach

### The integration problem

| Source | Grain | Size | Key challenge |
|---|---|---|---|
| [USAFacts](https://usafacts.org/visualizations/coronavirus-covid-19-spread-map/) COVID-19 confirmed cases | County × **day**, cumulative, *wide* (one column per date) | 3,193 × 621 | Un-pivot, de-cumulate, roll up to state |
| [CDC / Census Household Pulse](https://data.cdc.gov/NCHS/Indicators-of-Anxiety-or-Depression-Based-on-Repor/8pt5-q6wp) anxiety indicators | State × **irregular bi-weekly survey period** | 8,136 × 14 | Defines the common time grain; 4 periods have no state data |
| Kaggle Instagram posts | Post × timestamp | 178,922 posts / 1,089 users | Remove user IDs, aggregate to day |
| Kaggle @TheEconomist tweets | Tweet × timestamp | 254k × 36 | Strip PII and text, parse hashtag arrays, aggregate to day |
| [Census state reference](https://www2.census.gov/geo/docs/reference/state.txt) | State | 57 rows | Map full state names ↔ USPS codes |

### Architecture

```mermaid
flowchart TB
    subgraph Extract
        S1[USAFacts COVID<br/>county × day, cumulative]
        S2[CDC anxiety survey<br/>state × survey period]
        S3[Instagram posts]
        S4["@TheEconomist tweets"]
        S5[Census state FIPS ref]
    end

    subgraph Transform
        T1["Group to state → diff() daily new cases<br/>melt wide → long"]
        T2["Build TimePeriod dimension<br/>fix missing end-dates"]
        T3["State × TimePeriod cross join<br/>impute 4 gap periods<br/>(mean of neighbours, within state)"]
        T4["Drop IDs/usernames/text<br/>count hashtags · daily sums"]
        T5["Assign every daily record<br/>to its survey TimePeriod"]
    end

    subgraph Load["Load (data/processed)"]
        L1[final_covid_anxiety.csv<br/>state × period]
        L2[final_covid_socialmedia.csv<br/>day]
        L3[final_all_combined.csv<br/>period]
    end

    S1 --> T1 --> T5
    S2 --> T2 --> T3
    S5 --> T3
    S3 --> T4
    S4 --> T4 --> T5
    T2 --> T5
    T3 --> L1
    T5 --> L1 & L2
    L1 & L2 --> L3
    L3 --> V[Tableau dashboards<br/>correlation analysis]
```

## Results

![New COVID-19 cases vs reported anxiety](docs/figures/cases_vs_anxiety.png)

- New COVID-19 cases and the share of adults reporting anxiety symptoms moved together across 27 survey periods (**Pearson r = 0.80**).
- Instagram likes also tracked case counts (r = 0.59). @TheEconomist retweets did not (r = 0.10).

## Limitations & lessons learned

These are correlations between two time series that share a trend, with n = 27, so they are not evidence of causation. The four gap periods are longer than a normal survey window, so their case totals are inflated (for example, the spike at period 13). The Twitter data represents one publisher's engagement, not public social media use.

## Getting started

### Requirements

- Python 3.10 or later (tested on 3.14) and the packages in `requirements.txt`.
- The four raw CSVs in `data/raw/`. They aren't redistributed here; [`data/README.md`](data/README.md) lists where to download each one.

### Install

Missing or outdated packages from `requirements.txt` are installed automatically when you run the pipeline; from a terminal it asks first. To install everything up front instead:

```bash
pip install -r requirements.txt
```

### Run

```bash
python src/etl_pipeline.py
```

### Output

Three CSVs in `data/processed/`: `final_covid_anxiety.csv` (state × period), `final_covid_socialmedia.csv` (day) and `final_all_combined.csv` (period).

## Repository structure

```
covid-social-media-etl-pipeline/
├── src/
│   ├── etl_pipeline.py          # extract → transform → load
│   └── check_requirements.py    # installs missing packages from requirements.txt
├── data/
│   ├── README.md                # where to download each raw file
│   ├── raw/                     # .gitignored (third-party / contains user identifiers)
│   ├── reference/state_fips.txt # Census state reference (public domain)
│   └── processed/               # pipeline outputs, aggregated, no PII
├── docs/figures/
├── requirements.txt
├── CHANGELOG.md
└── LICENSE
```

## Skills demonstrated

`ETL design` · `Data integration across mismatched grains` · `Reshaping (melt, cross join, merge)` · `Time-dimension modeling` · `Missing-data imputation` · `PII minimization` · `pandas` · `Tableau` · `Regression testing against prior outputs`

## Data & citations

Source links for each input are in the [integration table](#the-integration-problem). Download steps and terms of use: [`data/README.md`](data/README.md).

## Credits & Collaboration

The original 2021 pipeline was a four-person graduate project in Business Intelligence at Texas Tech University.

* **Lead Developer:** Javier Casildo
* **Team Members:** three collaborators (names omitted for privacy)

*Note: Team member profiles will be linked with their permission.*

## License

Code: MIT. See [LICENSE](LICENSE). Each dataset keeps its original license and terms of use.
