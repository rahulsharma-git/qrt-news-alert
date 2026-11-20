# QRT News Alert — Build 1.1

Standalone, lightweight GitHub Actions project for early warning of critical or negative online news. Adapted from the supplied Social Media Intelligence Build 6.1.1 / V10.3, without the dashboard, X collection, Supabase, Word, PDF, Excel or daily report workflow. This is a rapid-alert workflow, not a replacement or a claim of full V10.3 daily-report research compliance.

## 1. Deploy in a new repository

1. Create a **private** GitHub repository named `qrt-news-alert` (suggested). Default branch: `main`.
2. Extract this ZIP. Upload all files and directories, including `.github/workflows/qrt-news-alert.yml` and `state/alert_history.json`, into the repository root. Hidden directories must not be omitted. For command-line deployment in the extracted directory:

   ```sh
   git init -b main
   git add .
   git commit -m "Initial QRT news alert build"
   git remote add origin https://github.com/YOUR-ACCOUNT/qrt-news-alert.git
   git push -u origin main
   ```

   Create an empty repository if using these commands. Replace YOUR-ACCOUNT with your GitHub account name.
3. Go to **Settings → Secrets and variables → Actions → New repository secret** and add the three required secrets. These can use the same Gmail account/app password as the previous project, subject to organizational approval. Secrets are repository-specific; add them anew.

| Secret | Value |
|---|---|
| `SMTP_EMAIL` | Sending Gmail address |
| `SMTP_APP_PASSWORD` | Gmail app password (not the regular password) |
| `ALERT_RECIPIENTS` | One or more email addresses separated by commas, semicolons or newlines |
| `GROQ_API_KEY` | Optional: enables semantic analysis of public article excerpts |

`REPORT_RECIPIENTS` is accepted only as a fallback if `ALERT_RECIPIENTS` is empty. Optional Actions variable `GROQ_MODEL` overrides the default `openai/gpt-oss-20b`. The local classifier runs without an AI account. Only enable the third-party AI provider if permitted by your organization's data-processing rules; it receives public article title, publisher and an excerpt, not SMTP credentials or recipients. No API quota or free-tier availability is guaranteed.

4. Under **Settings → Actions → General**, ensure Actions are enabled, the workflow may use `contents: write`, and branch protection/rulesets allow the GitHub Actions bot to commit the state file on the default branch. No PAT is required with ordinary write access. Do not weaken mandatory organizational protections; use an approved external state store instead if direct pushes are disallowed.
5. Open **Actions → QRT - 15 minute news alert → Run workflow**. Every manual, scheduled and workflow-file update run attempts to send one email, including NIL or WARNING reports when nothing qualifies. Confirm the message and review the job summary. A scan error attempts to send an ERROR report and leaves the job failed. Missing credentials, SMTP errors, runner/setup failures, skipped schedules and cancellations can prevent delivery.
6. For an existing repository, replace `monitor.py`, `.github/workflows/qrt-news-alert.yml`, `README.md`, `SAMPLE_EMAIL.txt` and `test_monitor.py`. Do not overwrite `state/alert_history.json`, `config.json` or secrets. Existing history is preserved.

## 2. Schedule and coverage

Cron `7,22,37,52 * * * *` runs at minutes 07,22,37,52 IST each hour (also every 15 minutes in UTC), approximately 96 scheduled runs per day. This offset avoids the top of the hour. GitHub-hosted schedules are best-effort, may be delayed or dropped, and only run from the default branch. They are not guaranteed 15-minute delivery or a 24x7 service-level agreement. Public repositories may have scheduled workflows disabled after 60 days without activity. Private runners consume Actions minutes; around 2,880 runs in 30 days, billed minutes depend on actual duration and plan. For an operationally critical SLA, use an approved always-on runner/scheduler and independent heartbeat monitoring.

Discovery uses Google News RSS, Bing News RSS, GDELT and configured publisher-native feeds. Seven configurable search strings include DoS, ISRO, IN-SPACe, NSIL, missions, startups and adverse-event terms. Direct publisher pages must establish original article title, article body, English-language relevance and exact first-publication timestamp with timezone evidence. Feed timestamps are NOT substituted for original publication. Official sources are excluded as independent media rows. Inaccessible or date-only sources and unresolved aggregator links are skipped; feed access and indexing coverage are not exhaustive. Publisher claims are attributed, not independently corroborated. The system does not perform the daily report’s 39 queries, two sweeps or official fact verification. This trade-off prioritizes speed. A six-hour rolling lookback catches delayed indexing and skipped runs within that horizon, subject to source and candidate limits. First real run can email qualifying items published in the preceding six hours. Articles published earlier are excluded unless you temporarily enlarge the lookback. Each scan is bounded by candidate count and soft time budget, with a 12-minute GitHub job timeout.

## 3. Alert policy (edit `config.json`)

- Negative: critical, accusatory or reputation-damaging coverage directed at the monitored entities. All impact levels alert by default. `negative_min_impact` can be set to `Medium` or `High` for less noise.
- Critical: material adverse developments such as mission anomalies, failures, major programme schedule changes, safety incidents, security issues, material allegations and significant misinformation. A critical event alerts independently of editorial tone; a routine weather postponement or routine positive coverage does not. Impact is independently rated High, Medium or Low. Local critical rules are approximate; semantic analysis is optional and may improve context handling, but both modes can misclassify articles. Human review remains essential.
- Emails are grouped into one message per scan, ordered by impact and recency. Original headline, visible complete source URL, publisher, author, publication time IST, tone, impact, impact analysis and alert reason appear in both HTML and plain-text forms. No attachments. A mandatory status email is sent even if no new items qualify; incomplete coverage is explicitly identified. Impact language is mild, measured and attributed; the rating appears separately from the analysis.

| Setting | Default | Meaning |
|---|---|---|
| `lookback_hours` | 6 | Original publication window |
| `history_days` | 30 | Retain sent hashes for 30 days |
| `max_candidates` | 100 | Maximum candidates processed per run |
| `scan_budget_seconds` | 300 | Soft limit before another verification batch |
| `negative_min_impact` | Low | Alert all negative coverage |
| `queries`, `publisher_feeds` | See config | Discovery scope |
| `google_news`, `bing_news`, `gdelt` | true | Discovery channels |
| `suppress_daily_archive` | false | Optional daily archive URL exclusion |

Deduplication uses normalized URL and publisher-host + title + publication date hashes. Separate publishers on the same event are retained. `state/alert_history.json` is automatically maintained by GitHub Actions; do not manually replace it. Non-alert checks expire after one hour, transient errors after approximately 15 minutes; previously alerted articles are suppressed for the configured retention window (even if the same article is updated). Only successful SMTP acceptance for all recipients marks alerts as sent; if SMTP acceptance succeeds but the history push fails, or SMTP partially accepts recipients, retries can produce duplicates. A workflow failure is visible in Actions. The JSON history stores hashes and timestamps, not article bodies or addresses. Concurrent runs are serialized; queued scheduled runs can be replaced by newer runs under GitHub concurrency behavior. State commits may add repository history; do not delete state or edit it during an active run.

The existing daily-report `latest-archive.csv` is **not required**. This separate alert history is deliberate: a critical article still deserves an alert even if it was in a daily report. If you explicitly want URL suppression against the daily archive, set `suppress_daily_archive` to true and upload `latest-archive.csv` into the root; it is read-only and must have a URL/link column. Missing or malformed archive then fails the scan rather than silently claiming deduplication.

## 4. Local tests

```sh
python -m pip install -r requirements.txt
python -m unittest -v
python monitor.py --dry-run
```

The thirteen included tests cover local tone vs critical classification, routine news suppression, denied claims, canonical deduplication, independent publishers, formatted email escaping, state integrity, verified publication time and expiry, and successful/failed delivery state handling with mocked network/SMTP. Live GitHub scheduling, publisher availability, Gmail delivery, and optional Groq access require a deployment test; none is certified by local tests.

## 5. Relevant files

- `monitor.py` — source discovery, verification, alert routing, email and persistent state.
- `editorial.py` — selected and adapted local V10.3 tone/impact helper functions from the supplied Build 6.1.1.
- `config.json` — monitoring policy and source configuration.
- `.github/workflows/qrt-news-alert.yml` — scheduled and manual execution, state push and diagnostics.
- `state/alert_history.json` — automatically maintained duplicate protection.
- `requirements.txt` — two runtime packages.
- `test_monitor.py` — offline unit tests.

At 96 planned daily scans, expect approximately 96 emails per recipient daily, plus manual and workflow-update runs. Local `--dry-run` remains preview-only for development.

GitHub schedule documentation: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
