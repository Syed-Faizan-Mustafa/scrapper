// Excel writers: per-city workbooks (one sheet per bank) and the master compilation.
import ExcelJS from 'exceljs';
import path from 'node:path';
import { mkdir, writeFile } from 'node:fs/promises';

const PER_SHEET_HEADERS = [
  'Branch Name', 'State & County', 'Zip Code', 'Office Address',
  'Service Type', 'City or Town', 'Phone Number', 'URL',
];
const PER_SHEET_WIDTHS = [24, 22, 10, 42, 20, 16, 16, 52];

const MASTER_HEADERS = ['State', 'City', 'URL', 'Phone', 'Branch Name', 'Bank Name', 'Zip Code'];
const MASTER_WIDTHS = [16, 18, 52, 16, 26, 26, 10];

const byName = (a, b) => String(a).localeCompare(String(b), 'en', { sensitivity: 'base' });

// Windows-safe file name.
export function sanitizeFilename(name) {
  let s = (name || 'Unknown').replace(/[\\/:*?"<>|]/g, ' ').replace(/\s+/g, ' ').trim();
  s = s.replace(/[. ]+$/, '').trim();
  if (!s) s = 'Unknown';
  if (/^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$/i.test(s)) s += '_';
  return s;
}

// Excel sheet name: <=31 chars, no : \ / ? * [ ], unique within a workbook.
export function sanitizeSheetName(name, used) {
  let s = (name || 'Sheet').replace(/[:\\/?*[\]]/g, ' ').replace(/\s+/g, ' ').trim();
  if (!s) s = 'Sheet';
  s = s.slice(0, 31);
  if (used) {
    const base = s;
    let i = 2;
    while (used.has(s.toLowerCase())) {
      const sfx = ` (${i++})`;
      s = base.slice(0, 31 - sfx.length) + sfx;
    }
    used.add(s.toLowerCase());
  }
  return s;
}

function styleHeader(ws, widths) {
  ws.getRow(1).font = { bold: true };
  ws.views = [{ state: 'frozen', ySplit: 1 }];
  ws.columns.forEach((c, i) => { c.width = widths[i] || 18; });
}

// banks: Map<bankName, branch[]>. Writes USA Bank/<State>/<City>.xlsx
export async function writeCityWorkbook(state, city, banks, outBase) {
  const wb = new ExcelJS.Workbook();
  const used = new Set();
  for (const bank of [...banks.keys()].sort(byName)) {
    const rows = banks.get(bank).slice().sort((a, b) => byName(a.branch_name, b.branch_name));
    const ws = wb.addWorksheet(sanitizeSheetName(bank, used));
    ws.columns = PER_SHEET_HEADERS.map((h) => ({ header: h, key: h }));
    ws.getColumn(3).numFmt = '@'; // Zip Code as text (keep leading zeros)
    ws.getColumn(7).numFmt = '@'; // Phone as text
    for (const r of rows) {
      ws.addRow({
        'Branch Name': r.branch_name,
        'State & County': r.state_county,
        'Zip Code': r.zip_code,
        'Office Address': r.office_address,
        'Service Type': r.service_type,
        'City or Town': r.city_or_town,
        'Phone Number': r.phone_number,
        URL: r.url,
      });
    }
    styleHeader(ws, PER_SHEET_WIDTHS);
  }
  const dir = path.join(outBase, 'USA Bank', sanitizeFilename(state));
  await mkdir(dir, { recursive: true });
  const file = path.join(dir, sanitizeFilename(city) + '.xlsx');
  await wb.xlsx.writeFile(file);
  return file;
}

function csvEscape(v) {
  const s = v == null ? '' : String(v);
  return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}

// Flat master compilation: State | City | URL | Phone | Branch Name | Bank Name | Zip Code
export async function writeMaster(branches, outBase) {
  const dir = path.join(outBase, 'Final Data Scraping');
  await mkdir(dir, { recursive: true });
  const sorted = branches.slice().sort(
    (a, b) =>
      byName(a.state, b.state) ||
      byName(a.city_or_town, b.city_or_town) ||
      byName(a.bank_name, b.bank_name) ||
      byName(a.branch_name, b.branch_name)
  );

  const wb = new ExcelJS.Workbook();
  const ws = wb.addWorksheet('All Branches');
  ws.columns = MASTER_HEADERS.map((h) => ({ header: h, key: h }));
  ws.getColumn(4).numFmt = '@'; // Phone
  ws.getColumn(7).numFmt = '@'; // Zip Code
  for (const r of sorted) {
    ws.addRow({
      State: r.state,
      City: r.city_or_town,
      URL: r.url,
      Phone: r.phone_number,
      'Branch Name': r.branch_name,
      'Bank Name': r.bank_name,
      'Zip Code': r.zip_code,
    });
  }
  styleHeader(ws, MASTER_WIDTHS);
  const xlsxPath = path.join(dir, 'USA_Banks_All.xlsx');
  await wb.xlsx.writeFile(xlsxPath);

  const lines = [MASTER_HEADERS.join(',')];
  for (const r of sorted) {
    lines.push(
      [r.state, r.city_or_town, r.url, r.phone_number, r.branch_name, r.bank_name, r.zip_code]
        .map(csvEscape).join(',')
    );
  }
  const csvPath = path.join(dir, 'master.csv');
  await writeFile(csvPath, lines.join('\r\n'), 'utf8');

  return { xlsxPath, csvPath, count: sorted.length };
}
