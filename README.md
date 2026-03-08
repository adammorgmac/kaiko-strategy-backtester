# Kaiko Options Research Dashboard

A prototype cryptocurrency options research dashboard and snapshot-based signal analysis tool built with Python, Streamlit, and Kaiko market data.

This project is designed for **exploration and strategy prototyping**, not for production trading or fully reliable historical backtesting. Its main goal is to help inspect crypto options surfaces, generate simple signals, store market snapshots, and create a foundation for more rigorous research over time.

## What this project does

This repo provides a lightweight workflow for working with crypto options data:

- fetch current options snapshots from the Kaiko API
- visualize implied volatility, open interest, and Greeks
- run simple signal-generation strategies
- store snapshots locally in SQLite for later analysis
- explore strategies through Streamlit dashboards

The emphasis is on **research tooling and iteration speed**, rather than execution realism or production-grade infrastructure.

## Current status

This is an **early-stage research prototype**.

It is useful for:
- options market exploration
- signal prototyping
- UI-driven inspection of market structure
- building a local archive of option snapshots

It is **not yet a fully valid backtesting engine**.

In particular:

- historical simulation is still limited
- execution assumptions are simplified
- some strategies are experimental
- reported performance metrics should be treated with caution
- this should not be used for live trading decisions

## Why this exists

Crypto options data is complex, and getting from raw API output to usable research tooling takes time. This project was built to create a practical middle layer between raw market data and strategy development.

The idea is simple:
- make the data easy to inspect,
- make strategy ideas easy to test at a basic level,
- and build toward a more rigorous snapshot-based research framework.

## Features

### Research dashboard
The Streamlit apps allow you to:
- select assets
- inspect options chains
- view IV smiles and term structure
- analyze open interest
- explore basic Greeks visualizations
- generate and inspect simple signals

### Strategy framework
The codebase includes modular strategy classes for:
- simple volatility-based screening
- skew-based exploration
- gamma-focused screening
- other experimental options ideas

These are best thought of as **signal generators and research experiments**, not validated trading strategies.

### Snapshot storage
The project can store option market snapshots in SQLite, which is the most promising path toward building a real point-in-time historical dataset for future analysis.

## Limitations

This section is important.

### 1. Not a production backtester
Despite earlier naming, this repo should be viewed as a **research dashboard and prototype framework**, not a production-grade backtesting system.

### 2. Historical coverage is limited
The project currently relies heavily on snapshot collection and current data inspection. Historical analysis is only as good as the snapshots you have collected and the consistency of the stored fields.

### 3. Execution realism is limited
This project does not yet model trading with the rigor required for serious performance evaluation. Depending on the code path used, execution, valuation, and PnL logic may still be simplified.

### 4. Strategies are experimental
The strategies in this repo are intended to help surface ideas and patterns. They have not been validated as robust alpha-generating strategies.

### 5. No live trading use
This repository is not intended for production trading or portfolio risk management.

## Project structure

````text
kaiko-strategy-backtester/
├── app_backtester.py              # Main Streamlit dashboard
├── app_advanced.py                # Advanced strategy exploration UI
├── capture_snapshot.py            # Save current market snapshots to SQLite
├── check_instruments.py           # Utility script for instrument inspection
├── backtester/
│   ├── engine.py                  # Prototype backtest / execution logic
│   ├── historical_data.py         # Current snapshot fetch logic
│   ├── historical_storage.py      # SQLite snapshot storage and retrieval
│   ├── strategies.py              # Core strategy classes
│   ├── advanced_strategies.py     # Experimental strategy ideas
│   ├── plot_utils.py              # Shared plotting helpers
│   └── visualizations.py          # Additional visualization helpers
├── requirements.txt
└── README.md
````

## Setup

### 1. Clone the repo

````bash
git clone https://github.com/adammorgmac/kaiko-strategy-backtester.git
cd kaiko-strategy-backtester
````

### 2. Create a virtual environment

````bash
python -m venv .venv
source .venv/bin/activate
````

### 3. Install dependencies

````bash
pip install -r requirements.txt
````

### 4. Add your API key

Create a local `.env` file:

````text
KAIKO_API_KEY=your_api_key_here
````

Do not commit this file.

If you prefer Streamlit secrets locally, you can also use `.streamlit/secrets.toml`, but keep it out of version control.

### 5. Run the app

````bash
streamlit run app_backtester.py
````

or

````bash
streamlit run app_advanced.py
````

## Recommended workflow

A sensible way to use this repo today is:

1. collect regular snapshots with `capture_snapshot.py`
2. inspect current and stored market structure in the dashboard
3. generate and compare signals
4. improve stored data quality over time
5. only then build more rigorous historical evaluation on top of the snapshot archive

This keeps the project honest about what it can and cannot do today.

## Security notes

- keep API keys in `.env` or local Streamlit secrets
- never commit `.env` or `.streamlit/secrets.toml`
- rotate keys immediately if they are ever exposed
- review git history if you are unsure whether a secret was tracked

## Roadmap

Likely next improvements:

- stronger point-in-time snapshot workflows
- cleaner execution and valuation logic
- more realistic mark-based or bid/ask-based PnL handling
- better test coverage
- improved data validation and schema checks
- clearer separation between screening, signal generation, and backtesting

## Disclaimer

This is a personal research and prototyping project. It is provided for educational and exploratory purposes only. Nothing in this repository should be interpreted as trading advice, investment advice, or a production-ready trading system.

## Author note

This project reflects an interest in quantitative research, market structure, and product-oriented tooling. It is intentionally iterative and still evolving toward greater rigor.

---

If you want, I can also give you:

- a **shorter sharper README for GitHub**, or
- a **README + CV bullet points version**, so the repo and your profile tell the same story.