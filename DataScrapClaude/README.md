# Bank Branch Locator Scraper

Scrapes every bank branch from **bankbranchlocator.com** into an Excel tree:

```
USA Bank/<State>/<City>.xlsx        # one workbook per city
   └─ one sheet per bank (A→Z)      # that bank's branches in that city
Final Data Scraping/
   ├─ USA Bank/...                  # a copy of the whole tree
   ├─ USA_Banks_All.xlsx            # flat master: State|City|URL|Phone|Branch Name|Bank Name|Zip Code
   └─ master.csv                    # same, as CSV
```

Each per-city sheet has 8 columns: **Branch Name · State & County · Zip Code · Office Address · Service Type · City or Town · Phone Number · URL**.

## Requirements
- Node.js 18+ (tested on v24). No Python needed.

## Install
```bash
npm install
```

## Run

Pilot one state (recommended first):
```bash
node src/main.js --state Alaska
```

Rerun / resume (already-scraped branches are skipped automatically):
```bash
node src/main.js --state Alaska
```

Rebuild Excel from cached data only, no network:
```bash
node src/main.js --state Alaska --write-only
```

One state at a time (repeat per state as you like):
```bash
node src/main.js --state "New York"
node src/main.js --state Texas
```

Everything (long, multi-day — see warning below):
```bash
node src/main.js --all
```

### Options
| Flag | Default | Meaning |
|------|---------|---------|
| `--state <name>` | — | State name, abbr, or slug (e.g. `Alaska`, `AK`, `alaska`) |
| `--all` | — | All 52 states/territories |
| `--write-only` | off | Skip network; rebuild Excel from cached data |
| `--delay <ms>` | `2500` | Min time between requests (global) |
| `--concurrency <n>` | `1` | Parallel requests (keep at 1 for this site) |
| `--cooldown <ms>` | `300000` | Pause length after repeated failures |
| `--maxfails <n>` | `6` | Consecutive failures that trigger a cooldown |
| `--refresh` | off | Ignore cache and re-download |
| `--out <dir>` | cwd | Output base directory |

## ⚠️ IMPORTANT: this site rate-limits / IP-blocks aggressive crawling
During testing, ~100 requests in a few minutes got the machine's IP **temporarily blocked** (TCP connections refused for 30–60+ min). The defaults (1 request at a time, 2.5s apart, with an automatic cooldown circuit-breaker) are deliberately gentle to avoid this. **Do not lower `--delay` or raise `--concurrency`** unless you know the site tolerates it. If you get blocked, wait (or switch networks) and just rerun — progress is saved.

## How resume works
- Every scraped branch is appended to `data/branches.ndjson` immediately.
- Rerunning skips any URL already in that file, so you can stop/start freely.
- Raw HTML is cached under `.cache/`, so reruns and `--write-only` are instant.
- Failed URLs are logged to `data/failed.ndjson`.

## Project layout
```
src/
  main.js     # CLI + crawl orchestration + circuit-breaker
  fetch.js    # HTTP: cache, rate-limit, timeout, retry
  parse.js    # cheerio parsers (state/city/branch)
  excel.js    # workbook + master writers, sanitization
  store.js    # resumable checkpoint store
  states.js   # the 52 state/territory definitions
```

See `bank-branch-scraper-architecture.md` for the full design.
