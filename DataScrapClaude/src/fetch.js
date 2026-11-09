// HTTP fetch with disk cache, global rate limiting, timeout and retry/backoff.
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile, access } from 'node:fs/promises';
import path from 'node:path';

const CACHE_DIR = path.resolve('.cache');
const DEFAULT_UA =
  process.env.SCRAPER_UA ||
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Global request spacing: every fetch waits `delayMs` after the previous one
// started, regardless of concurrency, so effective rate ~= 1000/delayMs req/s.
let _chain = Promise.resolve();
function spaced(delayMs) {
  const p = _chain.then(() => sleep(delayMs));
  _chain = p.catch(() => {});
  return p;
}

function cachePath(url) {
  const h = createHash('sha1').update(url).digest('hex');
  return path.join(CACHE_DIR, h + '.html');
}
async function exists(p) {
  try { await access(p); return true; } catch { return false; }
}

export async function fetchHtml(url, opts = {}) {
  const {
    delay = 2500,
    timeoutMs = 25000,
    retries = 3,
    refresh = false,
    ua = DEFAULT_UA,
  } = opts;

  const cp = cachePath(url);
  if (!refresh && (await exists(cp))) {
    return { html: await readFile(cp, 'utf8'), cached: true };
  }

  let lastErr;
  for (let attempt = 0; attempt <= retries; attempt++) {
    await spaced(delay);
    try {
      const res = await fetch(url, {
        headers: {
          'User-Agent': ua,
          Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
          'Accept-Language': 'en-US,en;q=0.9',
        },
        signal: AbortSignal.timeout(timeoutMs),
        redirect: 'follow',
      });
      if (res.status === 429 || res.status >= 500) throw new Error('HTTP ' + res.status);
      if (!res.ok) {
        const e = new Error('HTTP ' + res.status);
        e.noRetry = true;
        throw e;
      }
      const html = await res.text();
      await mkdir(CACHE_DIR, { recursive: true });
      await writeFile(cp, html, 'utf8');
      return { html, cached: false };
    } catch (err) {
      lastErr = err;
      if (err && err.noRetry) break;
      await sleep(Math.min(12000, 800 * 2 ** attempt));
    }
  }
  throw new Error('Failed to fetch ' + url + ': ' + (lastErr && lastErr.message));
}
