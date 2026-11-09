// Append-only checkpoint store so runs are resumable and re-runs skip scraped URLs.
import { appendFile, readFile, mkdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';

const DATA_DIR = path.resolve('data');
const NDJSON = path.join(DATA_DIR, 'branches.ndjson');
const FAILED = path.join(DATA_DIR, 'failed.ndjson');

export class Store {
  constructor() { this.map = new Map(); }

  async load() {
    if (!existsSync(NDJSON)) return;
    const txt = await readFile(NDJSON, 'utf8');
    for (const line of txt.split('\n')) {
      const t = line.trim();
      if (!t) continue;
      try { const b = JSON.parse(t); if (b && b.url) this.map.set(b.url, b); } catch {}
    }
  }

  has(url) { return this.map.has(url); }

  async add(b) {
    this.map.set(b.url, b);
    await mkdir(DATA_DIR, { recursive: true });
    await appendFile(NDJSON, JSON.stringify(b) + '\n', 'utf8');
  }

  async fail(url, err) {
    await mkdir(DATA_DIR, { recursive: true });
    await appendFile(FAILED, JSON.stringify({ url, err: String(err && err.message || err) }) + '\n', 'utf8');
  }

  all() { return [...this.map.values()]; }
  forState(name, abbr) {
    const s = String(name).toLowerCase();
    const a = abbr ? String(abbr).toLowerCase() : null;
    return this.all().filter((b) => {
      const bs = (b.state || '').toLowerCase();
      return bs === s || (a && bs === a);
    });
  }
}
