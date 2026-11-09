// HTML parsers for the three page types. Selectors verified against live samples.
import { load } from 'cheerio';

// State page -> list of city page URLs (absolute), deduped.
// City links look like: <a class="litem" href=".../banks-in-<city>-<abbr>.html">City</a>
export function parseStateCities(html, baseUrl, abbr) {
  const $ = load(html);
  const out = new Set();
  const suffix = `-${String(abbr).toLowerCase()}.html`;
  $('a').each((_, a) => {
    const href = $(a).attr('href');
    if (!href) return;
    if (!/(^|\/)banks-in-/i.test(href)) return;
    if (!href.toLowerCase().endsWith(suffix)) return;
    try { out.add(new URL(href, baseUrl).href); } catch {}
  });
  return [...out];
}

// City page -> list of branch-detail URLs (absolute), deduped.
// Scoped to the #showlist container to avoid unrelated footer/sidebar links.
export function parseCityBranchLinks(html, baseUrl) {
  const $ = load(html);
  const out = new Set();
  const collect = (root) =>
    root.find('a').each((_, a) => {
      const href = $(a).attr('href');
      if (href && /-branch\.html$/i.test(href)) {
        try { out.add(new URL(href, baseUrl).href); } catch {}
      }
    });
  const scope = $('#showlist');
  if (scope.length) collect(scope);
  if (out.size === 0) collect($.root()); // fallback: whole document
  return [...out];
}

// Branch detail page -> normalized record with all 8 output fields + routing keys.
export function parseBranch(html, url) {
  const $ = load(html);

  // Label/value pairs inside <ul class="details">
  const map = {};
  $('ul.details li').each((_, li) => {
    const label = $(li).find('.dtab').first().text().replace(/\s*:\s*$/, '').trim();
    if (!label) return;
    let val;
    if (/phone/i.test(label)) {
      val =
        $(li).find('.phone-number').first().text().trim() ||
        $(li).find('a.ext').first().text().trim() ||
        $(li).find('.dvalue').first().text().trim();
    } else {
      val = $(li).find('.dvalue').first().text().trim();
    }
    map[label] = val;
  });

  // Office Address sits outside the <ul> in <div class="address"><span class="dvaluex">
  let address = $('.address .dvaluex').first().text().trim();
  if (!address) {
    $('.dtab').each((_, el) => {
      if (!address && /office address/i.test($(el).text())) {
        address = $(el).nextAll('.dvaluex, .dvalue').first().text().trim();
      }
    });
  }

  // Bank name: <h1><span class="extra">Bank Name </span>Branch</h1>; fallback to breadcrumb.
  let bank = $('.leftdiv h1 .extra').first().text().trim();
  if (!bank) {
    $('a.brlink[itemprop="item"]').each((_, a) => {
      const href = $(a).attr('href') || '';
      if (!bank && /^https?:\/\/[^/]+\/[a-z0-9-]+\/$/i.test(href)) {
        bank = $(a).find('[itemprop="name"]').first().text().trim();
      }
    });
  }
  if (!bank) bank = 'Unknown Bank';

  const stateCounty = map['State & County'] || '';
  const state = (stateCounty.split(' - ')[0] || '').trim();

  return {
    bank_name: bank,
    branch_name: map['Branch Name'] || '',
    state_county: stateCounty,
    zip_code: map['Zip Code'] || '',
    office_address: address || '',
    service_type: map['Service Type'] || '',
    city_or_town: map['City or Town'] || '',
    phone_number: map['Phone Number'] || '',
    state,
    url,
  };
}
