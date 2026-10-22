# hsi-data

Daily Hang Seng Index close and Hong Kong market turnover, published as JSON for the HSI Trend app.

- Data file: `https://sycheng0924.github.io/hsi-data/hsi.json`
- Columns: `date` (HKT), `close`, `prevClose`, `turnover` (HKEX Main Board total trading value, HK$), `halfDay` (1 = half-day session)
- Updated by GitHub Actions on weekday evenings (Hong Kong time) from the HKEX Daily Quotations sheet.
- History: HKEX Securities Statistics Archive (turnover) and Yahoo Finance (index closes).

Informational only. Figures come from public sources and may contain errors; this is not investment advice.

## Local use

```
python3 scripts/hsidata.py update
python3 scripts/hsidata.py backfill --since 2016-01-01
python3 -m unittest discover -s tests
```
