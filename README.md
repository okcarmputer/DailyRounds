# DailyRounds

Automating my morning checks.

A scheduled job that runs at 7:30 AM daily, checks Dev and Prod `flow_monitor` for
freshness/row-count issues and data gaps, and emails an HTML summary. No CI/CD —
this is a repo + one container, built and deployed manually.

## Repo structure

```
daily-rounds/
├── README.md
├── requirements.txt
├── .env.example
├── config/
│   ├── config.yaml            # non-secret settings (not committed)
│   └── config.example.yaml    # committed template
├── src/
│   ├── db.py                  # connection helper — supports "dev" and "prod"
│   ├── main.py                # orchestrator + CLI entrypoint (scheduled or --now)
│   ├── email_report.py
│   └── checks/
│       ├── last_row_check.py      # Check 1 — dev + prod table health
│       ├── flow_loader_check.py   # Check 2 — ENG folder vs SQL
│       └── gap_check.py           # Check 3 — day-by-day gap detection
├── sql/
│   └── usp_GapCheck.sql       # reusable stored proc for gap detection
└── docker/
    ├── Dockerfile
    └── stack.yml
```

## Setup

1. Copy `.env.example` to `.env` and fill in real connection strings / SMTP creds.
2. Copy `config/config.example.yaml` to `config/config.yaml` if you need to override
   defaults.
3. Run `sql/usp_GapCheck.sql` against both Dev and Prod to install the stored proc.
4. Confirm `/opt/flowloader/logs` exists on `sv-dg-d00-omd` (it's flow_watchdog's
   local log directory — see `docker/stack.yml`'s bind mount). No SSH setup needed.

## Running

```bash
pip install -r requirements.txt
python src/main.py --now     # run once immediately
python src/main.py           # run on the 07:30 schedule
```

## Docker build & deploy (manual — no pipeline)

```bash
docker build -t rewacr-e2cfbhdwfhfbewad.azurecr.io/daily-rounds:latest -f docker/Dockerfile .
docker push rewacr-e2cfbhdwfhfbewad.azurecr.io/daily-rounds:latest
docker stack deploy -c docker/stack.yml daily-rounds
```

Rerun after changes:

```bash
docker exec -it $(docker ps -q -f name=daily-rounds) python src/main.py --now
docker service logs -f daily-rounds_daily-rounds
```

## Open items

See `DAILY_ROUNDS_SETUP.md` for the full write-up. Table names/columns/rule values
were checked against `flow_monitor/src/data_import`, `missionscrape`, and
`OPC-UA-Client` — see that doc's "Verification pass against source repos" section
for exactly what was corrected and confirmed. Still open:

- Whether the `flagged` rule in `flow_loader_check.py` (unprocessed-file count from
  flow_watchdog's report) is right — every sample report pulled so far showed zero
  new files, so it's unverified against a report with real activity in it.
- Whether `loader_audit.json`'s `rows_inserted` history is worth cross-referencing
  alongside the daily report for a fuller picture.
- The stale `docker-compose.yml` comment claiming `flow_watchdog` runs on
  `rewa-vm` — worth flagging to whoever maintains that file, since it actually
  runs locally on `sv-dg-d00-omd` (this is why Check 2 no longer needs SSH).
- All `hach_*` tables, `comparison_results`, and `PumpStationMap` — no source repo
  located for these yet; row/column assumptions in `last_row_check.py` remain
  guesses (marked `CONFIRM` in-line).
- SMTP: confirm with IT whether authenticated SMTP is enabled for the mailbox, or
  whether an existing no-auth internal relay should be used instead.
