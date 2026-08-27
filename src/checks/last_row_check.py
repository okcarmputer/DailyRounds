from datetime import datetime, timedelta

from db import get_connection

# rule types:
#   "log_only"      -> just report the last row's date/time, never flags
#   "freshness"      -> flags if last row older than max_age
#   "daily"          -> flags if no row with today's or yesterday's date
#   "yesterday"      -> flags if last row's date isn't exactly yesterday
#   "weekly_monday"  -> flags if last row's date isn't the most recent Monday
#   "row_count"      -> no date column; flags if COUNT(*) != expected
#   "populated"      -> no date column; flags only if COUNT(*) == 0

# Table/column names below were checked against flow_monitor/src/data_import,
# missionscrape, and OPC-UA-Client (opc-dashboard + opcua_logger). Every table with
# a "# confirmed" tag has its name/column verified against real source in one of
# those repos. Tables still tagged CONFIRM are not referenced in any of the three
# and remain guesses — most likely hach_* (a Hach hardware/API integration with no
# repo of its own that we've found) and comparison_results/PumpStationMap.

DEV_TABLES = {
    # CONFIRM: not found in flow_monitor, missionscrape, or OPC-UA-Client — no
    # source repo located for this table yet.
    "comparison_results":          {"order_col": "compared_at",              "rule": "log_only"},
    "DailyPumpRuntimes":           {"order_col": "LoggedAt",                 "rule": "daily"},  # confirmed: OPC-UA-Client/opc-dashboard/daily_totals_logger.py
    "DailyRainInfo":                {"order_col": "LoggedAt",                 "rule": "daily"},  # confirmed: same file
    "flow_ii_data_stage":           {"order_col": "Date_Time",                "rule": "daily"},  # confirmed: flow_monitor/src/data_import/file_parser.py processIIData()
    "flow_ii_peak_stage":           {"order_col": "Create_Date",              "rule": "daily"},  # confirmed: same file (Create_Date column exists; key is actually [SiteID, II_Week_Start])
    # hach_* tables aren't in any of the 3 source repos checked (likely a separate
    # Hach hardware/API integration with no repo located yet), but all three
    # row-count guesses below matched live Dev data exactly on 2026-08-27 —
    # confirmed empirically rather than from source.
    "hach_api_sites":               {"order_col": "lastmeasures_recorded_dttm", "rule": "log_only"},
    "hach_data_channel":            {"rule": "row_count", "expected": 376},  # confirmed live: matched exactly
    "hach_flow_monitors":           {"rule": "row_count", "expected": 151},  # confirmed live: matched exactly
    "hach_port_info":               {"rule": "row_count", "expected": 72},  # confirmed live: matched exactly (was "72 columns" in original notes, treated as rows — correct)
    "OPC_Anomalies":                {"order_col": "DetectedAt", "rule": "log_only"},  # not in prod yet
    # confirmed table/column: OPC-UA-Client/opc-dashboard/sql/db.py. LastSeenAt is
    # refreshed on every MQTT message the ingest processes; the OPC UA subscription
    # period is 5s (SUBSCRIPTION_PERIOD_MS), so a 2-minute freshness window is
    # generous under normal operation.
    "OPCAudit_Live":                {"order_col": "LastSeenAt", "rule": "freshness", "max_age": timedelta(minutes=2)},
    # confirmed table/column + weekly cadence: OPC-UA-Client/opc-dashboard/build_inputs_audit.py
    # checks "already has a row for the current ISO week (Mon-Sun)" before running.
    "OPCInputsAudit":               {"order_col": "CreateDate", "rule": "weekly_monday"},
    # confirmed table/column: missionscrape/create_daily_report_tables.sql. Same
    # daily-report shape as PumpStation_vol_flow/PumpStation_vol_flow_sum below, so
    # given the "daily" rule to match rather than defaulting to log_only.
    "PumpStation_daily_pump_data":  {"order_col": "Date", "rule": "daily"},
    "PumpStation_vol_flow":         {"order_col": "Date", "rule": "daily"},  # confirmed: missionscrape/create_daily_report_tables.sql
    "PumpStation_vol_flow_sum":     {"order_col": "Date", "rule": "daily"},  # confirmed: missionscrape/create_daily_report_tables.sql
    # confirmed table/column: OPC-UA-Client/opc-dashboard/sql/riverwood_farms_flow_log.sql.
    # CONFIRM the 15-minute freshness window itself, though — per opc-dashboard/readme.md,
    # rows are inserted only when a tracked field's *value* changes (event-driven), not on
    # a fixed interval, so a quiet 15+ minutes can be genuinely normal (stable wet well
    # level, pumps idle) rather than a real outage.
    "RiverwoodFarmsFlowLog":        {"order_col": "Timestamp", "rule": "freshness", "max_age": timedelta(minutes=15)},
}

PROD_TABLES = {
    "flow_summary_stage":    {"order_col": "Flow_Date",   "rule": "log_only", "flow_loader": True},  # confirmed: flow_monitor/src/data_import/file_parser.py processFlowSummary()
    # CONFIRM: hach_* — see note above DEV_TABLES.
    "hach_api_sites":        {"order_col": "lastmeasures_recorded_dttm", "rule": "log_only"},
    "hach_flow_monitors":    {"rule": "populated"},
    "hach_site_measurements": {"order_col": "MeasurementTime", "rule": "freshness", "max_age": timedelta(hours=1)},
    "hach_site_measures":    {"order_col": "Time", "rule": "freshness", "max_age": timedelta(hours=1)},
    "infiltration_stage":    {"order_col": "rain_event_dttm", "rule": "log_only", "flow_loader": True},  # confirmed: flow_monitor/src/data_import/file_parser.py processInfiltrationRates()
    # confirmed table/column: OPC-UA-Client/opcua_logger/db.py + config/mission_properties.json
    # ("TABLE": "OPCDataLog", INSERT INTO dbo.OPCDataLog (Timestamp, NodeId, Value)).
    # CONFIRM the rule itself — no cadence evidence found, still defaulting to log_only.
    "OPCDataLog":            {"order_col": "Timestamp", "rule": "log_only"},
    "opcua_analog_flat":     {"order_col": "ts_utc", "rule": "freshness", "max_age": timedelta(minutes=5)},  # confirmed table: OPC-UA-Client/opcua_logger
    # confirmed table/column: missionscrape/find_missing_days*.sql, mission_pump_import2.py
    "pumpstation_flow_stage": {"order_col": "DateTime", "rule": "yesterday"},
    # CONFIRM: PumpStationMap not found in any of the 3 repos checked.
    "PumpStationMap":        {"rule": "row_count", "expected": 89},
    "RainFall":              {"order_col": "Rain_Date", "rule": "log_only", "flow_loader": True},  # confirmed: flow_monitor/src/data_import/file_parser.py processRainData()
    "raw_flow_data_stage":   {"order_col": "Date_Time", "rule": "log_only", "flow_loader": True},  # confirmed: flow_monitor/src/data_import/file_parser.py processRawFlowReports()
}


def _evaluate(row_value, rule):
    if rule["rule"] == "log_only":
        return True, None

    if rule["rule"] == "freshness":
        # pyodbc returns naive datetimes for SQL Server DATETIME columns
        # (server local time, no tzinfo) — compare against naive local now,
        # not an aware UTC now, or the subtraction raises TypeError.
        now = datetime.now()
        ok = (now - row_value) <= rule["max_age"]
        return ok, None if ok else f"last row is older than {rule['max_age']}"

    # SQL Server DATE columns come back from pyodbc as datetime.date, not
    # datetime.datetime — .date() only exists on the latter, so branch on type
    # instead of assuming every column is a full datetime.
    row_date = row_value.date() if isinstance(row_value, datetime) else row_value
    today = datetime.now().date()

    if rule["rule"] == "daily":
        ok = row_date >= today - timedelta(days=1)
        return ok, None if ok else "no row today or yesterday"
    if rule["rule"] == "yesterday":
        ok = row_date == today - timedelta(days=1)
        return ok, None if ok else "latest row isn't dated yesterday"
    if rule["rule"] == "weekly_monday":
        most_recent_monday = today - timedelta(days=today.weekday())
        ok = row_date == most_recent_monday
        return ok, None if ok else "latest row isn't dated the most recent Monday"
    return True, None


def _check_table(cur, table, rule):
    if rule["rule"] in ("row_count", "populated"):
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        if rule["rule"] == "populated":
            flagged = count == 0
            reason = "table is empty" if flagged else None
        else:
            flagged = count != rule["expected"]
            reason = f"row count is {count}, expected {rule['expected']}" if flagged else None
        return {"table": table, "row_count": count, "flagged": flagged, "reason": reason}

    order_col = rule["order_col"]
    cur.execute(f"SELECT TOP 1 * FROM {table} ORDER BY {order_col} DESC")
    row = cur.fetchone()
    if row is None:
        return {"table": table, "last_value": None, "flagged": True, "reason": "table is empty"}
    cols = [d[0] for d in cur.description]
    row_dict = dict(zip(cols, row))
    row_value = row_dict[order_col]
    ok, reason = _evaluate(row_value, rule)
    return {"table": table, "last_value": row_value, "flagged": not ok, "reason": reason}


def run_last_row_check():
    results = {"dev": [], "prod": []}
    for env, tables in (("dev", DEV_TABLES), ("prod", PROD_TABLES)):
        with get_connection(env) as conn:
            cur = conn.cursor()
            for table, rule in tables.items():
                results[env].append(_check_table(cur, table, rule))
    return results
