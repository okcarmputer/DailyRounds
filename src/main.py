import argparse
import logging
import os
import time

import schedule

from checks.last_row_check import run_last_row_check
from checks.flow_loader_check import run_flow_loader_check
from checks.gap_check import run_gap_check
from email_report import send_report, write_report_file

# "file" (default) writes the report to REPORT_FILE_PATH for the Windows-side
# pull script to grab, since M365 tenant-wide SMTP AUTH is currently disabled
# (see DAILY_ROUNDS_SETUP.md). Set REPORT_MODE=email in .env once that's fixed.
REPORT_MODE = os.environ.get("REPORT_MODE", "file")
REPORT_FILE_PATH = os.environ.get("REPORT_FILE_PATH", os.path.expanduser("~/daily-rounds-report.html"))


def daily_rounds():
    logging.info("Starting daily rounds")
    sections = {
        "last_row": run_last_row_check(),
        "flow_loader": run_flow_loader_check(),
        "gaps": run_gap_check(),
    }
    if REPORT_MODE == "email":
        send_report(sections)
        logging.info("Daily rounds complete, email sent")
    else:
        write_report_file(sections, REPORT_FILE_PATH)
        logging.info(f"Daily rounds complete, report written to {REPORT_FILE_PATH}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--now", action="store_true",
                         help="Run once immediately and exit, instead of waiting for the schedule.")
    args = parser.parse_args()

    if args.now:
        daily_rounds()
    else:
        schedule.every().day.at("07:30").do(daily_rounds)
        while True:
            schedule.run_pending()
            time.sleep(30)
