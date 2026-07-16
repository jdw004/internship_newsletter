# intern_pos_emailer

Forked from https://github.com/vatsalm30/internship_emailer

A bot that **runs daily on GitHub Actions** and sends you **new US software /
quant / consulting internship openings** (Summer & Spring / off-cycle) by email
and optionally Discord.
It pulls from community internship aggregators and directly from company career
sites (via their ATS APIs), filters to what you care about, remembers what it has
already shown you, and only alerts on **new** postings.

```
sources (github lists + Greenhouse/Lever/Ashby/Workday)
   → normalize → filter (internship · season · category · US)
   → dedup vs data/seen_jobs.json (using normalized job links)
   → email digest (Gmail) + Discord webhook
   → commit updated state back to the repo
```

> Discord sends when `DISCORD_WEBHOOK_URL` is set. SMS (Twilio) is supported but
> **off by default**; to turn it on later, see "Optional: SMS" below.

## What it tracks
- **Roles:** internships only — Summer & Spring / off-cycle / co-op (configurable).
- **Categories:** software engineering, software development, quant dev, quant
  trading, big tech, unicorns, startups, consulting (tech tracks).
- **Location:** United States (incl. US-remote).

All of this is tunable in `config/` — no code changes needed.

## Layout
```
config/        # all tunables (no code): companies, github lists, filters, settings
src/sources/   # one module per source type (github lists + 4 ATS APIs)
src/filters.py # internship / season / category / US-location rules
src/dedup.py   # seen-jobs state (data/seen_jobs.json)
src/notify/    # email.py (Gmail SMTP) + discord.py (webhook) + sms.py (Twilio)
src/apply/     # FUTURE auto-apply scaffold (not yet implemented)
src/main.py    # orchestrator + CLI
.github/workflows/daily.yml  # the daily cron
tests/         # pytest: filters + dedup
```

## Quick start (local)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# See what it would send today — fetches live sources, no email/SMS/Discord, no state write:
python -m src.main --dry-run
```

Add credentials to send for real:
```bash
cp .env.example .env      # then fill in email and/or Discord credentials
python -m src.main --test-notify   # sends one sample notification to verify creds
python -m src.main                 # full run
```

**First-run tip:** with an empty `data/seen_jobs.json`, the first real run will
email the *entire current backlog* (~hundreds of postings) in one digest. If you'd
rather start clean and only get *new* postings from then on, seed the state once:
```bash
python -m src.main --seed   # marks everything currently open as "seen", sends nothing
```

Run the tests:
```bash
pytest
```

## Credentials
Set these as **GitHub repo Secrets** (Settings → Secrets and variables → Actions),
and/or in a local `.env` (see `.env.example`). With none set, the bot still runs in
`--dry-run` and prints results.

| Secret | What it is |
| --- | --- |
| `GMAIL_USER` | Gmail address to send from |
| `GMAIL_APP_PASSWORD` | 16-char [App Password](https://myaccount.google.com/apppasswords) (needs 2FA on) — **not** your login password |
| `EMAIL_TO` | where the digest goes (comma-separate for multiple) |
| `DISCORD_WEBHOOK_URL` | Discord channel webhook URL for posting the digest |

Email and Discord webhooks are free and need no other accounts beyond Gmail and
Discord.

## Deploy (private repo + daily cron)
1. Create a **private** GitHub repo and push this project.
2. Add the secrets above.
3. (Optional) Run `python -m src.main --seed` locally once and commit the updated
   `data/seen_jobs.json`, so your first scheduled email is a small delta rather than
   the whole backlog.
4. The workflow `.github/workflows/daily.yml` runs at **10:00 AM, 12:00 PM,
   2:00 PM, 4:00 PM, and 7:00 PM EST** and also on-demand from the **Actions
   tab** (`workflow_dispatch`, with a dry-run toggle).
5. Each run commits the updated `data/seen_jobs.json` back to the repo, so the bot
   remembers what it already sent.

Notes:
- Private-repo Actions get 2,000 free minutes/month; a run is ~1–2 min → effectively free.
- GitHub disables scheduled workflows after **60 days of no repo activity** — the daily
  state commit normally counts, but you can also re-trigger manually to keep it alive.
- Adjust the time by editing the UTC `cron:` entries and the EST gate in
  `.github/workflows/daily.yml`.

## Tuning
- **`config/companies.yaml`** — add companies by ATS + token. Quant firms and
  consulting are seeded here because the community lists skew SWE. Some seed tokens
  are best-effort — run `--dry-run` and disable any that 404 (`enabled: false`).
- **`config/github_lists.yaml`** — the community `listings.json` URLs. These repos
  roll names each cycle (`Summer2026` → `Summer2027`); update the URL when the new
  cycle's repo appears.
- **`config/filters.yaml`** — keywords, allowed seasons/years, and US location terms.
- **`config/settings.yaml`** — digest format, Discord options, state pruning, suppression.

## Discord webhook
Discord is enabled by default in `config/settings.yaml`, but it only sends when
`DISCORD_WEBHOOK_URL` exists. Create a webhook for the channel, add the URL as a
GitHub Actions secret, and the scheduled workflow will post the same new-job
digest there. Use `python -m src.main --no-discord` for a one-off run without it.

## Optional: SMS
An SMS-nudge channel (`src/notify/sms.py`, via Twilio) ships dormant. To enable
it later:
1. In `config/settings.yaml`, set `sms.enabled: true`.
2. Uncomment `twilio>=8` in `requirements.txt` and reinstall.
3. Add `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM`, `SMS_TO` (E.164)
   as secrets / `.env` values, and uncomment them in `.github/workflows/daily.yml`.

It sends a short "N new internships today" text alongside the email digest. Twilio
costs a few cents per message.

## Auto-apply (local) — implemented
`src/apply/` is a working local tool that opens Greenhouse / Lever / Ashby
application forms in a real browser and fills your details. It defaults to
**review before every submission**. Cover letters and auto-submit are explicit
opt-ins because they transmit personal data to third parties.

```bash
pip install -r requirements.txt -r requirements-apply.txt
python -m playwright install chromium
python -m src.apply --prepare-only      # safe first run: fills but never submits
python -m src.apply                     # fill + pause for your review before submit
```

Runs on your machine (not CI) so you can watch, solve CAPTCHAs, and review before
submit. It needs your resume in `resumes/` and a filled `config/profile.yaml`
(copy `config/profile.example.yaml`). If you opt in with `--cover-letter`, it uses
`GEMINI_API_KEY` and sends job/profile context to Google. Every attempt is logged
to `data/applications.json` so re-runs never double-apply.

**See [APPLYING.md](APPLYING.md) for the full guide, modes, and what to provide.**

## Legal / etiquette
Uses official public JSON APIs (Greenhouse, Lever, Ashby, Workday) and open,
community-maintained data — no scraping of LinkedIn/Indeed or other anti-bot sites.
Requests are rate-limited and retried politely. Respect each site's Terms of Service.
