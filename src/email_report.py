import os
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _row_table_html(rows, key_label):
    html = f"<table border='1' cellpadding='4' cellspacing='0'><tr><th>{key_label}</th><th>Last Value</th><th>Status</th><th>Reason</th></tr>"
    for r in rows:
        status = "FLAGGED" if r.get("flagged") else "OK"
        value = r.get("last_value", r.get("row_count", ""))
        html += f"<tr><td>{r['table']}</td><td>{value}</td><td>{status}</td><td>{r.get('reason') or ''}</td></tr>"
    html += "</table>"
    return html


def build_html(sections):
    html = f"<h2>Daily Rounds — {date.today()}</h2>"

    html += "<h3>Dev — Last Row Check</h3>"
    html += _row_table_html(sections["last_row"]["dev"], "Table")
    html += "<h3>Prod — Last Row Check</h3>"
    html += _row_table_html(sections["last_row"]["prod"], "Table")

    html += "<h3>Flow Loader Folder vs. SQL (Prod)</h3>"
    html += _row_table_html(
        [{"table": r["table"], "last_value": r["last_row_in_sql"],
          "flagged": r["flagged"],
          "reason": (f"watchdog: {r['watchdog_unprocessed_count']} unprocessed, "
                     f"most recent {r['watchdog_most_recent_file']}") if r["flagged"] else None}
         for r in sections["flow_loader"]],
        "Table",
    )

    html += "<h3>Data Gaps</h3>"
    for env in ("dev", "prod"):
        gap_rows = sections["gaps"].get(env, [])
        if not gap_rows:
            html += f"<p><b>{env.upper()}:</b> no gaps found.</p>"
            continue
        html += f"<p><b>{env.upper()}:</b></p><ul>"
        for g in gap_rows:
            days = ", ".join(str(d) for d in g["missing_or_short_days"][:10])
            more = f" (+{len(g['missing_or_short_days'])-10} more)" if len(g["missing_or_short_days"]) > 10 else ""
            html += f"<li><b>{g['table']}</b>: {days}{more}</li>"
        html += "</ul>"

    return html


def send_report(sections):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Daily Rounds — {date.today()}"
    msg["From"] = os.environ["SMTP_FROM"]
    msg["To"] = os.environ["SMTP_TO"]
    msg.attach(MIMEText(build_html(sections), "html"))

    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", 587))) as s:
        s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        s.send_message(msg)
