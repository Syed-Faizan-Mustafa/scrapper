# Bank Branch Locator — Data Scraping Architecture

**Source:** https://www.bankbranchlocator.com/
**Goal:** Scrape every bank branch in all 52 U.S. state/territory listings and export the data into a structured tree of Excel workbooks, organized by **USA Bank → State → City (workbook) → Bank (sheet)**.
**Status:** Architecture / build specification (v1). This document is the blueprint for the scraper script; it is not the script itself.

---

## 1. Executive Summary

We build a polite, resumable web scraper that walks the public pages of `bankbranchlocator.com`, extracts 7 fields per branch, and writes them into Excel files laid out as a folder tree. The output structure is:

```
USA Bank/
└─ <State>/                 (52 folders: 50 states + DC + Puerto Rico)
   └─ <City>.xlsx           (one workbook per city/town)
      └─ [<Bank Name>]      (one sheet per bank, A→Z; that bank's branches in that city)
```

Each sheet contains these columns for every branch:

| # | Column | Example |
|---|--------|---------|
| 1 | Branch Name | `Winter Park` |
| 2 | State & County | `Florida - Orange` |
| 3 | Zip Code | `32789` |
| 4 | Office Address | `1211 Orange Ave, Winter Park, FL 32789` |
| 5 | Service Type | `Full-Service, Office` |
| 6 | City or Town | `Winter Park` |
| 7 | Phone Number | `407-755-6707` |

When the run finishes, the completed tree is copied/moved into a **`Final Data Scraping/`** folder as the delivered artifact.

---

## 1.1 Confirmed Decisions (locked 2026-08-27)

The following client confirmations **refine** §1, §8, and §9:

1. **Naming:** workbook filename = **city name**; it lives in a folder named after its **state**. Each workbook holds many tabs (one sheet per bank). *(Structure A — as designed.)*
2. **State & County** stays a **single column** (`"Florida - Orange"`).
3. **Pilot first:** build + run **one state**, verify, then the client manually triggers the remaining states (`--state` filter).
4. **Add a `URL` column** to every per-bank sheet so a user can open that exact branch page. Per-sheet columns become **8**: Branch Name, State & County, Zip Code, Office Address, Service Type, City or Town, Phone Number, **URL**.
5. **Master compilation:** after the per-city workbooks are done, compile **one flat master sheet** with these columns, in this exact order:
   `State | City | URL | Phone | Branch Name | Bank Name | Zip Code`

---

## 2. Source Website Analysis (verified)

The site is **static HTML** with predictable URL patterns and no JavaScript rendering required. This is ideal for scraping.

### 2.1 Page types & URL patterns

| Level | Page type | URL pattern | Example |
|-------|-----------|-------------|---------|
| 0 | Home / state index | `/` | `https://www.bankbranchlocator.com/` |
| 1 | **State** page | `/{state-name}-banks.html` | `/alabama-banks.html` |
| 2 | **City** page | `/banks-in-{city}-{st}.html` | `/banks-in-houston-tx.html` |
| 3 | **Branch detail** page | `/{bank}-{branch}-{city}-branch.html` | `/amegy-bank-hobby-houston-branch.html` |
| — | Bank landing (optional) | `/{bank}/` | `/chase-bank/` |
| — | Bank-in-state (optional) | `/{bank}-locations-in-{state}.html` | `/amegy-bank-locations-in-texas.html` |

- `{state-name}`: lowercase, hyphenated (e.g., `district-of-columbia`, `puerto-rico`).
- `{city}`: lowercase, spaces → hyphens (`bay-minette`, `alexander-city`).
- `{st}`: 2-letter state abbreviation (`al`, `tx`).
- Branch URLs: when the branch name already contains the city, the extra city token is dropped (`/bank-of-houston-head-office-branch.html`). **Do not construct branch URLs by hand — always follow the real links or the sitemap.**

### 2.2 The 52 "states"

50 U.S. states **+ District of Columbia (`/district-of-columbia-banks.html`) + Puerto Rico (`/puerto-rico-banks.html`)** = **52 entries**. That is the "52 states" from the requirement.

### 2.3 Where each field actually lives — CRITICAL

This is the single most important architectural fact:

| Field | City page (level 2) | Branch detail page (level 3) |
|-------|:---:|:---:|
| Branch Name | ✅ | ✅ |
| Office Address | ✅ | ✅ |
| Zip Code | ✅ | ✅ |
| Service Type | ⚠️ (per bank-group) | ✅ |
| Bank Name | ✅ (group heading) | ✅ |
| **State & County** | ❌ | ✅ |
| **City or Town** | ❌ (implied by page) | ✅ |
| **Phone Number** | ❌ | ✅ |

➡️ **County, City/Town, and Phone Number are ONLY on the individual branch detail page.** Because you require all 7 fields, the scraper **must visit every branch detail page**. The city page alone is not enough.

### 2.4 Grouping & ordering on city pages

City pages already list branches **grouped by bank, in alphabetical order** (Agility Bank, Amegy Bank, Amerant Bank, …). This maps 1:1 onto our "one sheet per bank, sorted A→Z" output — the site does half the organizing work for us.

### 2.5 Scale (estimate — verify from sitemap)

The U.S. has roughly **75,000–85,000 bank branches**. Since we must fetch one detail page per branch, expect **~80,000 HTTP requests** for a full run, plus ~52 state pages and a few thousand city pages. **Plan for a long, resumable, checkpointed run — not a single quick script.** Confirm the true count from `sitemap.xml` before committing.

### 2.6 Throttling / IP-block behavior (OBSERVED during pilot)

⚠️ **The site actively blocks bursty crawling.** During the pilot, ~100 requests over a few minutes (concurrency 3, 0.5 s delay) caused the server to **refuse TCP connections from our IP entirely** (`Failed to connect ... port 443`), and the block persisted **40+ minutes**. A neutral site (example.com) stayed reachable throughout, confirming a *targeted* block — not a local network problem.

**Consequences for the design:**
- Run **serially and slowly**: concurrency **1**, delay **2.5–4 s** between requests (≈ 0.25–0.4 req/s).
- Include a **circuit-breaker**: after N consecutive failures, pause several minutes, then continue (implemented in `main.js`).
- **Realistic throughput** is ~1 branch / 3 s ≈ **1,200/hour**, so ~80,000 branches ≈ **many hours of fetching spread across days**, with cooldowns. This is a **chunked, per-state, multi-session effort**, not one script run. The built-in resumability makes this safe.
- If blocked: wait it out or switch networks/IP, then simply rerun — the checkpoint skips everything already scraped.

---

## 3. robots.txt & Legal / Politeness

Verified `robots.txt`:

```
User-agent: *
Disallow: /includes/banks.json
Disallow: /js/rating/rpc.php
Disallow: /plugins/feedback.php
Disallow: /includes/edit-branch.php
Sitemap: https://www.bankbranchlocator.com/sitemap.xml
```

- ✅ **All state / city / branch pages are allowed.** Only 4 backend endpoints are disallowed — **do not fetch `/includes/banks.json`** even though it looks tempting.
- ⚠️ **No `Crawl-delay`** is declared, so we impose our own (see §7).
- ✅ **A `sitemap.xml` exists** — use it for fast, complete URL discovery (§5.1).

**Ethics/compliance rules baked into the design:**
1. Honor `robots.txt` (skip the 4 disallowed paths).
2. Identify with a real, descriptive `User-Agent` including contact info.
3. Rate-limit and cap concurrency; never hammer the server.
4. Cache pages so re-runs don't re-download.
5. Review the site's Terms of Service before large-scale/commercial use. This data is factual and public, but respect the source. If they ask you to stop, stop.

---

## 4. Output Structure (recommended layout)

**Chosen layout: City = workbook, Bank = sheet.** (Matches your detailed description and the site's own bank-grouped city pages.)

```
USA Bank/
├─ Alabama/
│  ├─ Birmingham.xlsx
│  │   ├─ [Regions Bank]        ← sheet: all Regions branches in Birmingham
│  │   ├─ [ServisFirst Bank]    ← sheet
│  │   └─ [Wells Fargo Bank]    ← sheet
│  ├─ Mobile.xlsx
│  │   ├─ [BankFirst]
│  │   └─ [Regions Bank]
│  └─ Huntsville.xlsx
│      └─ ...
├─ Alaska/
│  └─ ...
├─ ...
├─ District of Columbia/
└─ Puerto Rico/
```

### 4.1 Ordering rules (your "alphabetic ascending" requirement)

- **State folders:** A→Z by display name.
- **City workbooks:** filenames sort A→Z naturally in the folder.
- **Bank sheets within a workbook:** inserted A→Z by bank name (case-insensitive).
- **Rows within a sheet:** sort by Branch Name A→Z (secondary: Address).

### 4.2 Naming & sanitization rules

Windows filenames and Excel sheet names have hard limits — the writer must sanitize:

**City workbook filenames**
- Use the display city name (Title Case): `Bay Minette.xlsx`, `St. Marys.xlsx`.
- Strip/replace illegal Windows chars: `\ / : * ? " < > |`.
- Trim trailing dots/spaces. Avoid reserved names (`CON`, `PRN`, `AUX`, `NUL`, `COM1`…`LPT9`) by suffixing `_` if hit.

**Bank sheet names (Excel constraints)**
- Max **31 characters** → truncate longer names (e.g., `Federal Reserve Non-member B…` → keep first 31).
- Illegal chars `: \ / ? * [ ]` → replace with space/`-`.
- Must be non-empty and **unique within the workbook**. If truncation causes a collision, append ` (2)`, ` (3)`, … while staying ≤ 31 chars.
- Keep a mapping of `sanitized sheet name → full bank name`; also write the full bank name into an optional `Bank Name` column so nothing is lost.

---

## 5. Scraping Strategy

Two discovery strategies. **Strategy A (sitemap-first) is recommended**; Strategy B mirrors your described click-flow and is the fallback/validator.

### 5.1 Strategy A — Sitemap-first (recommended)

The branch detail page is **self-describing**: it contains State, County, City, Bank Name, and all 7 fields. So we don't need to crawl the hierarchy to know where a branch belongs — we read it off the branch page itself and **bucket into folders/files/sheets from the scraped data.**

```
1. Fetch /sitemap.xml  (may be a sitemap index → fetch each child sitemap).
2. Collect all URLs; keep only branch pages (endswith "-branch.html").
3. For each branch URL:
     - fetch detail page (through cache),
     - parse the 7 fields + State + City + Bank Name,
     - route to bucket: USA Bank / <State> / <City>.xlsx / [<Bank>].
4. After all branches scraped, write workbooks (sorted), then consolidate.
```

Pros: fewer requests (skip city-page crawl), guaranteed coverage of everything the site indexes, simplest routing.
Cons: depends on sitemap completeness — validate the branch count against a few state pages.

### 5.2 Strategy B — Hierarchical drill-down (mirrors your click-flow, fallback)

```
Level 0: GET home (or a states index) → 52 state URLs.
Level 1: For each state page → parse "List Of All Cities and Towns" → city URLs.
Level 2: For each city page → parse bank groups (bank name + service type)
                             → collect each branch's detail-page URL.
Level 3: For each branch URL → fetch detail page → 7 fields.
Level 4: Bucket + write Excel (state already known, city known, bank known).
```

Pros: no reliance on sitemap; you get bank grouping + alphabetical order directly from the site; easy to run one state at a time. Cons: more requests (every city page too).

**Recommendation:** Use **A** for the full run; use **B** to spot-check a state or two and confirm A isn't missing branches. Both feed the same "bucket → write Excel" back end.

---

## 6. Data Model

One record per branch:

```python
@dataclass
class Branch:
    bank_name:     str   # sheet name    e.g. "TrustCo Bank"
    branch_name:   str   # col 1         e.g. "Winter Park"
    state_county:  str   # col 2         e.g. "Florida - Orange"  (as shown)
    zip_code:      str   # col 3         e.g. "32789"
    office_address:str   # col 4         e.g. "1211 Orange Ave, Winter Park, FL 32789"
    service_type:  str   # col 5         e.g. "Full-Service, Office"
    city_or_town:  str   # col 6         e.g. "Winter Park"
    phone_number:  str   # col 7         e.g. "407-755-6707"
    # --- routing keys (not necessarily printed) ---
    state:         str   # "Florida"    (for folder)
    source_url:    str   # provenance / dedup key
```

- **State & County** is stored exactly as displayed (`"Florida - Orange"`). If you later want them split, keep the raw string and derive `State`/`County` from it (split on ` - `).
- Optional extra columns you can enable per sheet: `Bank Name`, `Routing Number`, `Established`, `Hours`, `Branch URL`. Default output = the 7 required columns only.
- **Dedup key:** `source_url` (canonical branch URL). Guarantees a branch is written once even if reached via multiple paths.

---

## 7. Technical Design

### 7.1 Recommended stack (Python)

| Concern | Library |
|--------|---------|
| HTTP | `requests` (+ `requests.Session`, optionally `httpx` for async) |
| HTML parsing | `beautifulsoup4` + `lxml` |
| Excel writing | `openpyxl` |
| Retries/backoff | `tenacity` (or manual) |
| Progress | `tqdm` |
| State/checkpoint | `sqlite3` (stdlib) or JSON lines |
| Config | `pydantic` / `dataclasses` / a `config.yaml` |

Python is the right choice: static HTML + tabular Excel output = `requests + BeautifulSoup + openpyxl`. No Selenium/Playwright needed (no JS rendering).

### 7.2 Suggested project layout

```
DataScrapClaude/
├─ bank-branch-scraper-architecture.md   ← this document
├─ config.yaml                           ← delay, workers, paths, state filter
├─ requirements.txt
├─ scraper/
│  ├─ __init__.py
│  ├─ fetch.py        # HTTP session, headers, rate-limit, retry, cache
│  ├─ discover.py     # sitemap parse (Strategy A) + hierarchy crawl (Strategy B)
│  ├─ parse.py        # BeautifulSoup extractors → Branch objects
│  ├─ store.py        # SQLite checkpoint (visited URLs, scraped rows)
│  ├─ excel.py        # bucket → workbooks/sheets, sanitize, sort, write
│  ├─ consolidate.py  # build "Final Data Scraping/" + optional master workbook
│  └─ main.py         # CLI orchestration
├─ .cache/            # raw HTML cache (gitignored)
├─ USA Bank/          # working output tree
└─ Final Data Scraping/  # delivered artifact
```

### 7.3 Politeness & robustness (non-negotiable at this scale)

- **Rate limit:** default **1 request/second** per worker; make it configurable.
- **Concurrency:** start at **1–3 workers**. Back off automatically on HTTP 429/503.
- **Headers:** descriptive `User-Agent` (e.g., `BankBranchResearchBot/1.0 (+contact@example.com)`), `Accept-Encoding: gzip`.
- **Retries:** exponential backoff (e.g., 1s, 2s, 4s, 8s) on 5xx/timeouts; give up after N tries and log the URL to a `failed.csv`.
- **Timeouts:** connect+read timeout (e.g., 20s).
- **Caching:** save every fetched page under `.cache/<sha1(url)>.html`. Re-runs read cache → near-instant, zero extra load. Add a `--refresh` flag to bypass.
- **Logging:** structured logs (INFO progress, WARNING skips, ERROR failures) to console + `run.log`.

### 7.4 Resumability (essential for an ~80k-page run)

- A **SQLite** table `pages(url TEXT PRIMARY KEY, status TEXT, fetched_at)` and `branches(url PK, bank, state, city, json)`.
- On start: skip URLs already marked `done`. On crash/stop: re-run continues where it left off.
- Write Excel only in the final phase (or incrementally per completed city) so a mid-run crash never corrupts workbooks.
- `--state "Texas"` filter lets you run/resume one state at a time.

---

## 8. Excel Writing Rules

1. **Bucket** all `Branch` records in memory (or query from SQLite) grouped as `state → city → bank`.
2. For each **state**, create/ensure folder `USA Bank/<State>/`.
3. For each **city**, create workbook `<City>.xlsx`.
4. For each **bank** in that city (sorted A→Z), add a sheet named `<sanitized bank>`:
   - Row 1 = bold header: `Branch Name | State & County | Zip Code | Office Address | Service Type | City or Town | Phone Number`.
   - Following rows = that bank's branches, sorted by Branch Name A→Z.
   - Freeze the header row; auto-size columns; set the ZIP/phone columns to **Text** format so leading zeros and dashes survive (`openpyxl` `cell.number_format = '@'`).
5. Save. Never keep a giant workbook open across the whole run — write per city, then release.

---

## 9. Final Consolidation

Your requirement: *"finally the completed Excel data goes into a `Final Data Scraping` folder."*

Design:
- The scraper writes into a working `USA Bank/` tree.
- On successful completion, `consolidate.py` **copies** the entire validated `USA Bank/` tree into **`Final Data Scraping/USA Bank/`** (copy, not move, so the working tree remains for audits).
- **Master workbook (confirmed):** emit a single **master workbook** `Final Data Scraping/USA_Banks_All.xlsx` (plus a `master.csv`) with one flat row per branch and columns **in this exact order**: `State | City | URL | Phone | Branch Name | Bank Name | Zip Code`. This is far easier to search/filter/QA than opening thousands of files. (Note: 1M-row Excel limit — if total rows exceed ~1,000,000, fall back to CSV/Parquet for the master.)

---

## 10. Execution / Rollout Plan

1. **Phase 0 — Recon:** fetch `sitemap.xml`, count branch URLs, confirm scale.
2. **Phase 1 — Pilot (1 small state):** run end-to-end on e.g. Alaska or DC. Verify all 7 fields parse correctly, folder/sheet structure is right, sanitization works. **Do not run all 52 states until one is perfect.**
3. **Phase 2 — Validate:** cross-check pilot output against the live site for a few branches; confirm branch counts vs the state page's stated totals.
4. **Phase 3 — Full run:** all 52 states with checkpointing. Expect hours; it's resumable, so run in chunks (`--state` filter) if needed.
5. **Phase 4 — Consolidate & QA:** build `Final Data Scraping/`, master workbook, and a summary report (branches per state, failures, blanks).

---

## 11. Edge Cases & Gotchas

- **Missing fields:** some branches may lack a phone or county. Write empty string, never crash. Track blanks in the QA report.
- **Long / duplicate bank names:** handled by 31-char truncation + uniqueness suffix (§4.2).
- **Branch name already contains city:** URL token is dropped — rely on real links/sitemap, don't hand-build URLs.
- **ZIP & phone leading zeros:** force Text format in Excel or they'll be mangled (e.g., ZIP `07001` → `7001`).
- **Same city name in two states:** not a problem — city workbooks live under their state folder.
- **Pagination:** none observed on state/city pages (single-page lists), but verify per page and follow "next" if any appears.
- **Puerto Rico / DC:** included in the 52; their state folder names are `Puerto Rico` and `District of Columbia`.
- **Rate limiting / blocking (429/503):** auto-slow-down + retry; if persistently blocked, increase delay and reduce workers.
- **Site changes:** if HTML structure changes, only `parse.py` needs updating — keep selectors isolated there.

---

## 12. Questions — Resolved ✅ (see §1.1)

All resolved on 2026-08-27 — see the locked decisions in §1.1. The only still-optional item: a contact email/URL for the crawler's `User-Agent` (etiquette; reduces block risk). Until provided, a neutral descriptive UA is used. Original questions kept below for reference:

1. **Extra columns?** Do you want optional `Bank Name`, `Routing Number`, `Established`, or `Hours` columns, or strictly the 7 fields? *(Default: 7 fields only.)*
2. **Master workbook?** Should I also produce the single consolidated `USA_Banks_All.xlsx` in the final folder? *(Default: yes — very useful for QA.)*
3. **Split "State & County"?** Keep as one column `"Florida - Orange"` (as the site shows), or split into separate `State` and `County` columns? *(Default: keep as one, matching your field list.)*
4. **Scope for first build:** run all 52 states, or pilot one state first and then scale? *(Strong recommendation: pilot one, then scale.)*
5. **Language/stack:** Python (recommended) — confirm, or tell me if you need a different environment.
6. **Contact for User-Agent:** an email/URL to put in the crawler's User-Agent (good etiquette, reduces block risk).

---

## 13. Appendix — End-to-End Pseudocode (Strategy A)

```python
def run():
    cfg = load_config()
    session = build_session(user_agent=cfg.user_agent, delay=cfg.delay)
    db = Store("progress.sqlite")

    # 1. Discover branch URLs from sitemap (respect robots: skip disallowed paths)
    branch_urls = discover_from_sitemap("https://www.bankbranchlocator.com/sitemap.xml")
    branch_urls = [u for u in branch_urls if u.endswith("-branch.html")]

    # 2. Scrape each branch detail page (cached, retried, checkpointed)
    for url in tqdm(branch_urls):
        if db.is_done(url):
            continue
        html = fetch(session, url)              # cache + retry + rate-limit
        branch = parse_branch(html, url)        # → Branch dataclass (7 fields + state/city/bank)
        db.save_branch(branch)
        db.mark_done(url)

    # 3. Write Excel tree: USA Bank / State / City.xlsx / [Bank sheet]
    for state in sorted(db.states()):
        for city in sorted(db.cities(state)):
            wb = new_workbook()
            for bank in sorted(db.banks(state, city), key=str.lower):
                ws = wb.create_sheet(sanitize_sheet_name(bank))
                write_header(ws)                # the 7 columns
                for br in sorted(db.branches(state, city, bank), key=lambda b: b.branch_name.lower()):
                    write_row(ws, br)           # ZIP/phone as text
            wb.save(f"USA Bank/{state}/{sanitize_filename(city)}.xlsx")

    # 4. Consolidate into deliverable
    consolidate("USA Bank", "Final Data Scraping", master_workbook=cfg.master)
```

---

*End of architecture. Confirm the §12 questions and I'll implement the script module-by-module (starting with a single-state pilot).*
