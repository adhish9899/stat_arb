# STATISTICAL ARBITRAGE BACKTESTING

## What is it?
This repository contains code and data to conduct stat arb backtesting over for the last 1 month.

## Dependencies
```bash
pip install -r requirements.txt
```

## Usage
```bash
python stat_arb_backtesting.py
```

## NOTES
  1. Only 3 pair of stocks have taken for simplicity sake and easy management of capital for backtesting.
  2. Intra day data source is [IEX](https://iexcloud.io/)
  3. End of data souce is [Yahoo Finance](https://in.finance.yahoo.com/)

## Future Work
  1. The idea is still in intial stages and can be used to exploit inefficiencies in other highly corelates stocks
  2. Efficient capital allocation between long and short positions.
  
