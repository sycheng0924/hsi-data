# Changelog

## v0.1.1 - 2026-11-03
- Daily update now runs hourly 20:05-00:05 HKT (was 17:05-00:05). HKEX's sheet has been ready
  between about 21:40 and 22:45 HKT on every trading day so far, so the earlier runs found nothing.
  The 08:30 HKT catch-up run is unchanged.
- Checked the HKEX Daily Quotations format change of 2026-11-02 (S&P index lines removed): the
  parser reads the new sheet correctly; no code change needed.

## v0.1.0 - 2026-10-22
- Daily update script for the HKEX Daily Quotations sheet (HSI close, previous close, HK$ turnover, half-day flag).
- One-time backfill from the HKEX turnover archive and Eastmoney index closes.
- GitHub Actions: hourly weekday-evening update and a manual backfill workflow.
- `docs/hsi.json` served on GitHub Pages.
