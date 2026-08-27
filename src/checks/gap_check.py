from db import get_connection

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


def run_gap_check():
    results = {"dev": [], "prod": []}
    for env, tables in GAP_CHECK_TABLES.items():
        with get_connection(env) as conn:
            cur = conn.cursor()
            for table, cfg in tables.items():
                cur.execute(
                    "EXEC dbo.usp_GapCheck @TableName=?, @DateColumn=?, @ExpectedRowsPerDay=?",
                    table, cfg["date_col"], cfg["expected_per_day"],
                )
                gaps = [row[0] for row in cur.fetchall()]  # list of missing/short days
                if gaps:
                    results[env].append({"table": table, "missing_or_short_days": gaps})
    return results
