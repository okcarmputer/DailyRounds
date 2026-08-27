import argparse
import logging
import time

import schedule

from checks.last_row_check import run_last_row_check
from checks.flow_loader_check import run_flow_loader_check
from checks.gap_check import run_gap_check
from email_report import send_report


def daily_rounds():
    logging.info("Starting daily rounds")
    sections = {
        "last_row": run_last_row_check(),
        "flow_loader": run_flow_loader_check(),
        "gaps": run_gap_check(),
    }
    send_report(sections)
    logging.info("Daily rounds complete, email sent")


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
