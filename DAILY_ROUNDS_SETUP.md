# Daily Rounds — Repo Creation Guide (v3)

**Purpose:** A scheduled job that runs at 7:30 AM daily, checks Dev and Prod
`flow_monitor` for freshness/row-count issues and data gaps, and emails an HTML
summary. No CI/CD — this is a repo + one container, built and deployed manually.

See `README.md` for the built repo's structure and run/deploy instructions. This
file is kept as the original design doc / rationale reference.

## Design change (v3): Check 2 no longer uses SSH

`flow_watchdog` (flow_monitor/src/data_import/watchdog_trigger.py) runs locally on
`sv-dg-d00-omd` — confirmed via `docker context ls` showing only the local socket
and `docker logs flow_watchdog` working with no SSH involved. The compose file's
comment claiming it's deployed on `rewa-vm` is stale (worth flagging to whoever
maintains `/data/flowloader/docker-compose.yml`). Since daily-rounds is pinned to
that same host, `src/checks/flow_loader_check.py` now bind-mounts
`/opt/flowloader/logs` read-only and parses the daily `run_report_*.txt`
flow_watchdog already writes — no SSH key, no folder re-scan. Field labels
("Most recent file:", "Days since update:", "UNPROCESSED FILES (N total)") were
confirmed against `DailyHealthChecker._run_report()` in that file.

Real ENG filename convention (fallback only, not used by the current
implementation): `<YYYY> Flow Monitoring Data/<MM> <MonthName> <YYYY>/Site <N>
Report.xlsx` — folder-encoded dates, from `processed_files.json`.

## Verification pass against source repos (v3)

Before committing, table names/columns/rule values in `src/checks/*.py` were
checked against `flow_monitor/src/data_import`, `missionscrape`, and
`OPC-UA-Client`. Summary:

**Corrected:**
- `pumpstation_flow_stage` gap-check expected rows/day: was `1`, corrected to
  `391 * 24 = 9384` per `missionscrape/find_missing_days.sql`'s comment (391
  distinct PumpStationID+PumpName combos × 24 hourly readings). That file also
  says to reverify the 391 constant periodically.
- `RiverwoodFarmsFlowLog` removed from the gap check entirely — per
  `OPC-UA-Client/opc-dashboard/readme.md`, rows are inserted only when a tracked
  field's value changes (event-driven), not on a fixed interval, so a flat
  expected-rows-per-day count would false-flag normal quiet periods. The
  freshness rule in `last_row_check.py` is the right check for this table
  instead.
- `PumpStation_daily_pump_data` rule: was `log_only` (unconfirmed), changed to
  `daily` to match its siblings `PumpStation_vol_flow`/`PumpStation_vol_flow_sum`
  — all three are created together in `missionscrape/create_daily_report_tables.sql`
  with the same daily-report shape.
- DEV SQL Server hostname: was `DEV-SQL-00`, corrected to `DEV-SQL-00-IG` per
  `properties.json` and `mission_properties.json` in both other repos.
- DB name casing: both dev and prod databases are actually named `flow_monitor`
  lowercase in every config file found (not `Flow_Monitor` on prod) — cosmetic
  only since SQL Server names are case-insensitive by default, but corrected in
  `.env.example` for accuracy.

**Confirmed correct as-is** (see inline `# confirmed` comments in
`last_row_check.py`): `raw_flow_data_stage`/`Date_Time`, `flow_ii_data_stage`/`Date_Time`,
`flow_summary_stage`/`Flow_Date`, `infiltration_stage`/`rain_event_dttm`,
`RainFall`/`Rain_Date`, `PumpStation_vol_flow`/`Date`, `PumpStation_vol_flow_sum`/`Date`,
`pumpstation_flow_stage`/`DateTime`, `DailyPumpRuntimes`/`LoggedAt`,
`DailyRainInfo`/`LoggedAt`, `OPCAudit_Live`/`LastSeenAt`, `OPCInputsAudit`/`CreateDate`
(weekly cadence explicitly confirmed), `OPCDataLog`/`Timestamp` (table+column name
confirmed; rule itself still open), `opcua_analog_flat` (table name confirmed),
`RiverwoodFarmsFlowLog`/`Timestamp`.

**Still unverifiable from these 3 repos** — not found in flow_monitor,
missionscrape, or OPC-UA-Client, so left as guesses (`# CONFIRM` comments in
`last_row_check.py`): all `hach_*` tables (`hach_api_sites`, `hach_data_channel`,
`hach_flow_monitors`, `hach_port_info`, `hach_site_measurements`,
`hach_site_measures` — likely a Hach hardware/API integration with no repo found
yet), `comparison_results`, `PumpStationMap`.

**Not re-derived** (out of scope for this pass — flag if you want these checked
too): whether `pumpstation_flow_stage`'s `"yesterday"` last-row rule is right
given the table receives hourly readings and known multi-day gap windows exist in
prod history; whether `OPCAudit_Live`'s 2-minute freshness window is exactly
right (the OPC UA subscription period is confirmed at 5s, so 2 minutes is
generous under normal operation, but LastSeenAt's exact refresh behavior under
the retained-replay dedup logic wasn't fully traced).

## Known finding (not a code bug) — Dev pump-station data gap

Testing Check 1 against live Dev on 2026-08-27 surfaced a real data issue, not a
check-logic issue: `PumpStation_daily_pump_data`, `PumpStation_vol_flow`, and
`PumpStation_vol_flow_sum` were all last updated 2026-08-10/11 (16-17 days stale)
despite being expected to be live/current in Dev. Likely `missionscrape`'s loader
isn't running against Dev. Worth chasing down separately from this repo — the
check correctly flagged it once the datetime-handling bugs above were fixed.

`flow_ii_data_stage`/`flow_ii_peak_stage` are also stale in Dev but are NOT
expected to be live there, so their staleness is fine/expected.

## Still open

1. Whether the `flagged` rule in `flow_loader_check.py` is right — every sample
   `run_report_*.txt` pulled so far showed zero new files/folders, so the rule is
   unverified against a report with real activity in it.
2. Whether `loader_audit.json`'s `rows_inserted` history is worth cross-referencing
   alongside the daily report for a fuller picture.
3. The stale `docker-compose.yml` comment claiming `flow_watchdog` runs on
   `rewa-vm` — worth flagging to whoever maintains that file, since it actually
   runs locally on `sv-dg-d00-omd`.
4. All `hach_*` tables, `comparison_results`, and `PumpStationMap` — no source
   repo located for these yet; row/column assumptions remain guesses.
5. SMTP: confirm with IT whether authenticated SMTP is enabled for your mailbox,
   or whether an existing no-auth internal relay already exists for jobs like
   this.
