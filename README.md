# GHL daily 24h report

`node report.mjs [hours]` prints a markdown status report for the last N hours (default 24) for two GHL sub-accounts. It covers new leads by source, tag and country; new opportunities; stage movements; won/lost; conversations; and appointments. Node 18+, no dependencies.

## Config (environment variables, or a `.env` file next to the script)

```
INDIA_TOKEN=pit-...
INDIA_LOCATION_ID=<India sub-account location id>
INTL_TOKEN=pit-...
INTL_LOCATION_ID=<International sub-account location id>
```

Each Private Integration token needs these scopes: `contacts.readonly`, `opportunities.readonly`, `conversations.readonly`, `calendars.readonly`, `calendars/events.readonly`, `locations.readonly`.
Never commit tokens. `.env` is gitignored.

## Routine prompt (Claude Code on the web, daily 10:00 IST)

> Run `node ghl-daily-report/report.mjs 24` from the repo root (allow up to 5 minutes). Reply with a 3–5 line executive summary covering new leads per account and where they came from, stage movements, won/lost, conversations still waiting for a reply, and anything unusual. Then paste the full markdown report exactly as printed. If a section says "missing this scope", name the account and the scope to add in GHL → Settings → Private Integrations. If the script fails, report the error and do not invent numbers.
