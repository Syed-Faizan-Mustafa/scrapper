// CLI orchestrator: crawl State -> City -> Branch, write per-city workbooks,
// then a master compilation. Resumable, rate-limited, block-aware.
//
// Usage:
//   node src/main.js --state Alaska              # pilot one state (gentle defaults)
//   node src/main.js --state Alaska --limit 8    # quick smoke test
//   node src/main.js --state Alaska --write-only # rebuild Excel from cached data, no network
//   node src/main.js --all                       # every state (long run)
// Options: --delay <ms> (default 2500) --concurrency <n> (default 1)
//          --cooldown <ms> (default 300000) --maxfails <n> (default 6)
//          --refresh --out <dir>
import pLimit from 'p-limit';
import path from 'node:path';
import { cp } from 'node:fs/promises';
import { fetchHtml } from './fetch.js';
import { parseStateCities, parseCityBranchLinks, parseBranch } from './parse.js';
import { writeCityWorkbook, writeMaster } from './excel.js';
import { Store } from './store.js';
import { resolveState, STATES } from './states.js';

const BASE = 'https://www.bankbranchlocator.com/';
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function parseArgs(argv) {
  const a = {
    delay: 2500, concurrency: 1, limit: 0, cooldown: 300000, maxfails: 6,
    refresh: false, writeOnly: false, out: process.cwd(), state: null, all: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (k === '--state') a.state = argv[++i];
    else if (k === '--all') a.all = true;
    else if (k === '--delay') a.delay = Number(argv[++i]);
    else if (k === '--concurrency') a.concurrency = Number(argv[++i]);
    else if (k === '--limit') a.limit = Number(argv[++i]);
    else if (k === '--cooldown') a.cooldown = Number(argv[++i]);
    else if (k === '--maxfails') a.maxfails = Number(argv[++i]);
    else if (k === '--refresh') a.refresh = true;
    else if (k === '--write-only' || k === '--no-scrape') a.writeOnly = true;
    else if (k === '--out') a.out = argv[++i];
  }
  return a;
}

async function scrapeState(st, args, store) {
  const fetchOpts = { delay: args.delay, refresh: args.refresh };
  const stateUrl = `${BASE}${st.slug}-banks.html`;
  log(`STATE ${st.name}  ->  ${stateUrl}`);

  const { html: stateHtml } = await fetchHtml(stateUrl, fetchOpts);
  const cities = parseStateCities(stateHtml, BASE, st.abbr);
  log(`  cities found: ${cities.length}`);
  if (cities.length === 0) log('  !! no cities parsed — check selector/state slug');

  const limit = pLimit(args.concurrency);

  // --- Circuit breaker: pause when the site starts refusing connections. ---
  let consecutiveFails = 0;
  let pauseUntil = 0;
  const gate = async () => {
    const wait = pauseUntil - Date.now();
    if (wait > 0) await sleep(wait);
  };
  const onFail = () => {
    if (++consecutiveFails >= args.maxfails) {
      pauseUntil = Date.now() + args.cooldown;
      log(`  ** ${consecutiveFails} consecutive failures — cooling down ${Math.round(args.cooldown / 1000)}s (likely rate-limited) **`);
      consecutiveFails = 0;
    }
  };

  // Gather branch URLs from every city page.
  const branchSet = new Set();
  let cityDone = 0;
  await Promise.all(cities.map((cityUrl) => limit(async () => {
    await gate();
    try {
      const { html } = await fetchHtml(cityUrl, fetchOpts);
      for (const l of parseCityBranchLinks(html, BASE)) branchSet.add(l);
      consecutiveFails = 0;
    } catch (e) {
      log(`  !! city failed ${cityUrl}: ${e.message}`);
      await store.fail(cityUrl, e);
      onFail();
    }
    if (++cityDone % 10 === 0 || cityDone === cities.length) {
      log(`  city pages ${cityDone}/${cities.length}, branch links: ${branchSet.size}`);
    }
  })));

  let branchUrls = [...branchSet];
  if (args.limit) branchUrls = branchUrls.slice(0, args.limit);
  log(`  branch pages to scrape: ${branchUrls.length}`);

  let done = 0, added = 0, skipped = 0, offState = 0, failed = 0;
  await Promise.all(branchUrls.map((url) => limit(async () => {
    if (store.has(url)) { skipped++; done++; return; }
    await gate();
    try {
      const { html } = await fetchHtml(url, fetchOpts);
      const b = parseBranch(html, url);
      if (b.state && b.state.toLowerCase() !== st.name.toLowerCase()) offState++;
      await store.add(b);
      added++;
      consecutiveFails = 0;
    } catch (e) {
      failed++;
      log(`  !! branch failed ${url}: ${e.message}`);
      await store.fail(url, e);
      onFail();
    }
    if (++done % 25 === 0 || done === branchUrls.length) {
      log(`  branches ${done}/${branchUrls.length} (new ${added}, cached ${skipped}, failed ${failed})`);
    }
  })));
  log(`  scraped ${st.name}: new=${added} cached=${skipped} failed=${failed} off-state=${offState}`);
}

async function writeStateWorkbooks(stateName, store, outBase, abbr) {
  const branches = store.forState(stateName, abbr);
  const byCity = new Map();
  for (const b of branches) {
    const city = b.city_or_town || 'Unknown';
    if (!byCity.has(city)) byCity.set(city, new Map());
    const banks = byCity.get(city);
    const bank = b.bank_name || 'Unknown Bank';
    if (!banks.has(bank)) banks.set(bank, []);
    banks.get(bank).push(b);
  }
  let files = 0;
  for (const [city, banks] of [...byCity.entries()].sort((a, b) => a[0].localeCompare(b[0]))) {
    await writeCityWorkbook(stateName, city, banks, outBase);
    files++;
  }
  log(`  wrote ${files} city workbooks (${byCity.size} cities, ${branches.length} branches) for ${stateName}`);
  return { cities: byCity.size, files, branches: branches.length };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const store = new Store();
  await store.load();
  log(`store loaded: ${store.all().length} branches already cached`);

  let targets;
  if (args.all) targets = STATES;
  else if (args.state) {
    const s = resolveState(args.state);
    if (!s) { console.error('Unknown state:', args.state); process.exit(1); }
    targets = [s];
  } else {
    console.error('Specify --state "Alaska" (pilot) or --all  (add --write-only to rebuild Excel offline)');
    process.exit(1);
  }

  log(`targets: ${targets.map((t) => t.name).join(', ')} | mode=${args.writeOnly ? 'WRITE-ONLY' : 'scrape'} delay=${args.delay}ms concurrency=${args.concurrency}${args.limit ? ` limit=${args.limit}` : ''}`);

  for (const st of targets) {
    if (!args.writeOnly) await scrapeState(st, args, store);
    await writeStateWorkbooks(st.name, store, args.out, st.abbr);
  }

  const m = await writeMaster(store.all(), args.out);
  log(`MASTER: ${m.count} rows -> Final Data Scraping/USA_Banks_All.xlsx + master.csv`);

  try {
    await cp(path.join(args.out, 'USA Bank'), path.join(args.out, 'Final Data Scraping', 'USA Bank'), { recursive: true });
    log('copied USA Bank tree -> Final Data Scraping/USA Bank');
  } catch (e) {
    log('!! tree copy skipped:', e.message);
  }
  log('DONE');
}

main().catch((e) => { console.error(e); process.exit(1); });
