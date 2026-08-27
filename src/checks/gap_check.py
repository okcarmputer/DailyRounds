from datetime import date, timedelta

from db import get_connection

# How far back to look for gaps. Walking a table's entire history (some go back
# to 2025, well before current reporting volume/frequency was in place) buries
# recent, actionable gaps under a flood of ancient/irrelevant ones — a daily
# rounds check only needs to catch problems in the recent window.
LOOKBACK_DAYS = 60

# Derived from the Check 1 freshness rules (1440 minutes / interval), except
# pumpstation_flow_stage — see below.
GAP_CHECK_TABLES = {
    "dev": {
        "DailyPumpRuntimes":        {"date_col": "LoggedAt", "expected_per_day": 1},
        "DailyRainInfo":            {"date_col": "LoggedAt", "expected_per_day": 1},
        "flow_ii_data_stage":       {"date_col": "Date_Time", "expected_per_day": 1},
        "flow_ii_peak_stage":       {"date_col": "Create_Date", "expected_per_day": 1},
        "OPCAudit_Live":            {"date_col": "LastSeenAt", "expected_per_day": 720},   # every 2 min
        "PumpStation_vol_flow":     {"date_col": "Date", "expected_per_day": 1},
        "PumpStation_vol_flow_sum": {"date_col": "Date", "expected_per_day": 1},
        # RiverwoodFarmsFlowLog intentionally NOT gap-checked here: per
        # OPC-UA-Client/opc-dashboard/readme.md, rows are inserted only when a
        # tracked field's value changes (event-driven), not on a fixed interval —
        # a flat expected-rows-per-day count would false-flag normal quiet periods.
        # The freshness rule in last_row_check.py is the right check for this table.
    },
    "prod": {
        "hach_site_measurements": {"date_col": "MeasurementTime", "expected_per_day": 24},
        "hach_site_measures":     {"date_col": "Time", "expected_per_day": 24},
        "opcua_analog_flat":      {"date_col": "ts_utc", "expected_per_day": 288},         # every 5 min
        # Confirmed against missionscrape/find_missing_days.sql: 391 distinct
        # PumpStationID+PumpName combos x 24 hourly readings/day = 9384/day. That
        # comment also says to reverify the 391 constant periodically with:
        #   SELECT COUNT(DISTINCT PumpStationID + '|' + PumpName) FROM dbo.pumpstation_flow_stage;
        "pumpstation_flow_stage": {"date_col": "DateTime", "expected_per_day": 391 * 24},
    },
    # Skipped: tables with no date column (hach_data_channel, hach_flow_monitors,
    # hach_port_info, PumpStationMap) — those are covered by the row-count rule in
    # Check 1 instead. OPCInputsAudit skipped — weekly cadence, not a daily-gap fit.
}


def _find_gaps(cur, table, date_col, expected_per_day):
    """
    Plain SELECT/GROUP BY + gap-walk in Python, deliberately not a stored proc —
    the account this runs as doesn't have CREATE PROCEDURE rights on Prod, and
    this needs no more permission than the other checks already use (SELECT).

    Only looks back LOOKBACK_DAYS from today, not the table's full history.
    """
    cutoff = date.today() - timedelta(days=LOOKBACK_DAYS)
    cur.execute(
        f"SELECT CAST({date_col} AS date) AS [Day], COUNT(*) AS DayRowCount "
        f"FROM {table} WHERE {date_col} >= ? GROUP BY CAST({date_col} AS date)",
        cutoff,
    )
    counts = {row.Day: row.DayRowCount for row in cur.fetchall()}
    if not counts:
        return []

    day, max_day = cutoff, max(counts)
    gaps = []
    while day <= max_day:
        if counts.get(day, 0) < expected_per_day:
            gaps.append(day)
        day += timedelta(days=1)
    return gaps


def run_gap_check():
    results = {"dev": [], "prod": []}
    for env, tables in GAP_CHECK_TABLES.items():
        with get_connection(env) as conn:
            cur = conn.cursor()
            for table, cfg in tables.items():
                gaps = _find_gaps(cur, table, cfg["date_col"], cfg["expected_per_day"])
                if gaps:
                    results[env].append({"table": table, "missing_or_short_days": gaps})
    return results
