import glob
import os
import re

from db import get_connection

# flow_watchdog (flow_monitor/src/data_import/watchdog_trigger.py) runs locally on
# sv-dg-d00-omd, the same host daily-rounds is pinned to — confirmed via
# `docker context ls` showing only the local socket and `docker logs flow_watchdog`
# working with no SSH involved. The compose file's comment claiming it's deployed on
# rewa-vm is stale. No SSH needed here — bind-mount its LOG_PATH read-only instead
# (see stack.yml) and parse the daily run_report_*.txt it already writes.
FLOWLOADER_LOGS_DIR = "/mnt/flowloader-logs"

FLOW_LOADER_TABLES = {
    "flow_summary_stage":  {"date_col": "Flow_Date"},
    "infiltration_stage":  {"date_col": "rain_event_dttm"},
    "RainFall":            {"date_col": "Rain_Date"},
    "raw_flow_data_stage": {"date_col": "Date_Time"},
}


def _latest_run_report():
    reports = sorted(glob.glob(os.path.join(FLOWLOADER_LOGS_DIR, "run_report_*.txt")))
    if not reports:
        return None
    with open(reports[-1], encoding="utf-8") as f:
        return f.read()


def _parse_report(text):
    """Pull the fields we care about out of flow_watchdog's own daily report.
    Field labels/format confirmed against watchdog_trigger.py's DailyHealthChecker._run_report()."""
    info = {}
    m = re.search(r"Most recent file:\s*(.+)", text)
    info["most_recent_file"] = m.group(1).strip() if m else None
    m = re.search(r"Days since update:\s*(.+)", text)
    info["days_since_update"] = m.group(1).strip() if m else None
    m = re.search(r"UNPROCESSED FILES\s*\((\d+) total\)", text)
    info["unprocessed_count"] = int(m.group(1)) if m else None
    return info


def run_flow_loader_check():
    report_text = _latest_run_report()
    report_info = _parse_report(report_text) if report_text else {}

    results = []
    with get_connection("prod") as conn:
        cur = conn.cursor()
        for table, cfg in FLOW_LOADER_TABLES.items():
            cur.execute(f"SELECT MAX({cfg['date_col']}) FROM {table}")
            last_sql_row = cur.fetchone()[0]
            results.append({
                "table": table,
                "last_row_in_sql": last_sql_row,
                "watchdog_most_recent_file": report_info.get("most_recent_file"),
                "watchdog_days_since_update": report_info.get("days_since_update"),
                "watchdog_unprocessed_count": report_info.get("unprocessed_count"),
                # CONFIRM: every sample report pulled so far showed 0 unprocessed
                # files (nothing new has landed recently), so this flagging rule is
                # unverified against a report with real activity in it.
                "flagged": (report_info.get("unprocessed_count") or 0) > 0,
            })
    return results
