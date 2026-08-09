// View 1 — Company. Model A/B comparison is the centrepiece.
import { api, ApiError } from './api.js';
import {
  PALETTE, VARIANT_COLOUR, num, int, pct, signedPct, compact, monthLabel, esc, parseAmount,
} from './fmt.js';
import { baseOptions, render, destroy } from './charts.js';
import { skeleton, empty, errorStrip, tag } from './ui.js';

const CANVAS = 'company-chart';
const state = {
  company: null,
  companyMeta: null,
  investment: 1000000,
  variants: ['legacy', 'current', 'drift'],
  data: null,
  reqId: 0,
  showAnnual: true,
};

let meta = null;
let searchTimer = null;

/* ------------------------------------------------------------------ setup */
export function initCompany(appMeta) {
  meta = appMeta;
  state.variants = meta.variants.map((v) => v.id);

  const checks = document.getElementById('variant-checks');
  checks.innerHTML = meta.variants.map((v) => `
    <label class="vcheck" for="chk-${esc(v.id)}">
      <input type="checkbox" id="chk-${esc(v.id)}" value="${esc(v.id)}" checked
             data-testid="check-variant-${esc(v.id)}">
      <span class="swatch" style="background:${VARIANT_COLOUR[v.id] || PALETTE.navy}"></span>
      <span><span class="vlabel">${esc(v.label)}</span>
      <span class="vshort">${esc(v.short)}</span></span>
    </label>`).join('');

  checks.addEventListener('change', () => {
    const picked = [...checks.querySelectorAll('input:checked')].map((i) => i.value);
    state.variants = picked.length ? picked : [meta.default_variant];
    if (!picked.length) {
      checks.querySelector(`input[value="${meta.default_variant}"]`).checked = true;
    }
    loadCompany();
  });

  const annualToggle = document.getElementById('toggle-annual');
  if (annualToggle) {
    annualToggle.addEventListener('change', () => {
      state.showAnnual = annualToggle.checked;
      // Redraw only; no refetch needed since the annual series is already loaded.
      if (state.data) drawChart(state.data);
    });
  }

  const search = document.getElementById('company-search');
  const results = document.getElementById('company-results');
  search.addEventListener('input', () => {
    clearTimeout(searchTimer);
    const q = search.value.trim();
    if (q.length < 2) { hideResults(); return; }
    searchTimer = setTimeout(() => runSearch(q), 250);
  });
  search.addEventListener('keydown', (e) => { if (e.key === 'Escape') hideResults(); });
  document.addEventListener('click', (e) => {
    if (!results.contains(e.target) && e.target !== search) hideResults();
  });

  const amount = document.getElementById('investment');
  amount.addEventListener('change', () => {
    const v = parseAmount(amount.value);
    if (v === null) { amount.value = int(state.investment); return; }
    state.investment = v;
    amount.value = int(v);
    loadCompany();
  });

  renderVariantNotes();
  showPlaceholders();
}

function hideResults() {
  const results = document.getElementById('company-results');
  results.hidden = true;
  results.innerHTML = '';
  document.getElementById('company-search').setAttribute('aria-expanded', 'false');
}

async function runSearch(q) {
  const results = document.getElementById('company-results');
  results.hidden = false;
  document.getElementById('company-search').setAttribute('aria-expanded', 'true');
  results.innerHTML = '<li class="r-empty">Searching…</li>';
  try {
    const rows = await api.companies(q, 25);
    if (!rows.length) {
      results.innerHTML = '<li class="r-empty">No company in the reference universe matches that.</li>';
      return;
    }
    results.innerHTML = rows.map((r) => `
      <li role="option"><button type="button" data-name="${esc(r.name)}"
        data-sector="${esc(r.sector)}" data-country="${esc(r.country)}" data-isin="${esc(r.isin)}"
        data-testid="result-${esc(r.isin)}">
        <span class="r-name">${esc(r.name)}</span>
        <span class="r-meta">${esc(r.sector || 'Sector n/a')} · ${esc(r.country || 'Country n/a')} · ${esc(r.isin)}</span>
      </button></li>`).join('');
    results.querySelectorAll('button').forEach((b) => {
      b.addEventListener('click', () => {
        state.company = b.dataset.name;
        state.companyMeta = { ...b.dataset };
        document.getElementById('company-search').value = b.dataset.name;
        hideResults();
        loadCompany();
      });
    });
  } catch (err) {
    results.innerHTML = `<li class="r-empty">Search failed: ${esc(err.detail || err.message)}</li>`;
  }
}

function showPlaceholders() {
  document.getElementById('company-cards').innerHTML =
    empty('No company selected',
      'Search by name or ISIN above to compare the model variants for one company.')
    + '<div class="empty" id="quick-picks" data-testid="quick-picks"><b>Examples from the universe</b>Loading…</div>';
  const wrap = document.querySelector('#company-chart-panel .chart-wrap');
  wrap.hidden = true;
  if (!document.getElementById('chart-empty')) {
    wrap.insertAdjacentHTML('afterend',
      '<div class="empty" id="chart-empty"><b>Nothing plotted yet</b>'
      + 'The chart appears once a company is selected. Reported years will be drawn solid, modelled years dashed.</div>');
  }
  document.getElementById('company-annual-table').innerHTML =
    '<caption>Select a company to populate annual totals.</caption>';
  document.getElementById('company-caption').textContent = '';
  document.getElementById('company-chart-sub').textContent =
    'No company selected. Nothing is plotted.';
  loadQuickPicks();
}

async function loadQuickPicks() {
  const host = document.getElementById('quick-picks');
  if (!host) return;
  try {
    const rows = await api.companies('', 5);
    host.innerHTML = '<b>Examples from the universe</b>'
      + rows.map((r) => `<button type="button" class="quick" data-name="${esc(r.name)}"
          data-sector="${esc(r.sector)}" data-country="${esc(r.country)}" data-isin="${esc(r.isin)}"
          data-testid="quick-${esc(r.isin)}">${esc(r.name)}</button>`).join('');
    host.querySelectorAll('button').forEach((b) => b.addEventListener('click', () => {
      state.company = b.dataset.name;
      state.companyMeta = { ...b.dataset };
      document.getElementById('company-search').value = b.dataset.name;
      loadCompany();
    }));
  } catch {
    host.innerHTML = '<b>Examples from the universe</b>Could not reach the reference universe.';
  }
}

/* ------------------------------------------------------------------- load */
export async function loadCompany() {
  if (!state.company) { showPlaceholders(); return; }
  const cards = document.getElementById('company-cards');
  const reqId = ++state.reqId;
  cards.innerHTML = skeleton(2, false);
  const wrap = document.querySelector('#company-chart-panel .chart-wrap');
  wrap.hidden = false;
  const chartEmpty = document.getElementById('chart-empty');
  if (chartEmpty) chartEmpty.remove();

  const sel = document.getElementById('selected-company');
  const m = state.companyMeta || {};
  sel.hidden = false;
  sel.innerHTML = `<b>${esc(state.company)}</b> — ${esc(m.sector || 'sector n/a')} · ${esc(m.country || 'country n/a')}
    ${m.isin ? '· ISIN ' + esc(m.isin) : ''} · attribution on ${int(state.investment)} invested`;

  try {
    const data = await api.company(state.company, state.variants, state.investment);
    if (reqId !== state.reqId) return;
    state.data = data;
    drawCards(data);
    drawChart(data);
    drawAnnualTable(data);
  } catch (err) {
    if (reqId !== state.reqId) return;
    cards.innerHTML = errorStrip(err, `attribution for ${state.company}`);
    destroy(CANVAS);
    document.getElementById('company-annual-table').innerHTML = '';
    document.getElementById('company-caption').textContent = '';
  }
}

/* ------------------------------------------------------------------ cards */
function drawCards(data) {
  const cards = document.getElementById('company-cards');
  const firstYear = (v) => {
    const ann = data.series[v] && data.series[v].annual;
    return ann && ann.length ? ann[0].year : null;
  };
  cards.innerHTML = state.variants.filter((v) => data.headline[v]).map((v) => {
    const h = data.headline[v];
    const vm = data.series[v].meta;
    const start = firstYear(v);
    return `<article class="card" data-testid="card-${esc(v)}">
      <h3 class="card-variant">
        <span class="swatch" style="background:${VARIANT_COLOUR[v]}"></span>${esc(vm.label)}
      </h3>
      <div class="metric">
        <span class="metric-label">Reduction, reported data only</span>
        <span class="metric-value ${cls(h.reported_only)}" data-testid="metric-reported-${esc(v)}">${signedPct(h.reported_only)}</span>
        <span class="metric-basis">${tag('reported')} ${start ?? '—'} → ${h.reported_last_year ?? '—'}
          · ${spanYears(start, h.reported_last_year)}</span>
      </div>
      <div class="metric">
        <span class="metric-label">Reduction including modelled years</span>
        <span class="metric-value ${cls(h.full)}" data-testid="metric-full-${esc(v)}">${signedPct(h.full)}</span>
        <span class="metric-basis">${tag('modelled')} ${start ?? '—'} → ${h.final_year ?? '—'}
          · ${h.final_year && h.reported_last_year ? (h.final_year - h.reported_last_year) : '—'} modelled years</span>
      </div>
    </article>`;
  }).join('');
}

const cls = (v) => (v === null || v === undefined ? 'na' : (v < 0 ? 'neg' : 'pos'));
const spanYears = (a, b) => (a && b ? `${b - a} years` : 'span n/a');

/* ------------------------------------------------------------------ chart */
function drawChart(data) {
  const present = state.variants.filter((v) => data.series[v]);
  if (!present.length) { destroy(CANVAS); return; }

  const base = data.series[present[0]].monthly;
  const labels = base.map((p) => p.date);
  const quality = base.map((p) => p.quality);
  let startIndex = quality.findIndex((q) => q !== 'reported');
  if (startIndex < 0) startIndex = null;

  const focus = present.includes(meta.default_variant) ? meta.default_variant : present[0];
  const datasets = [];

  // Confidence band for the focus variant only (drawn first, under the lines).
  const fm = data.series[focus].monthly;
  const hasBand = fm.some((p) => p.lower !== null && p.upper !== null);
  if (hasBand) {
    datasets.push({
      label: `__band_upper`,
      data: fm.map((p) => p.upper),
      borderWidth: 0, pointRadius: 0, fill: '+1',
      backgroundColor: hexA(VARIANT_COLOUR[focus], 0.12),
      order: 30, spanGaps: true,
    });
    datasets.push({
      label: `__band_lower`,
      data: fm.map((p) => p.lower),
      borderWidth: 0, pointRadius: 0, fill: false, order: 31, spanGaps: true,
    });
  }

  present.forEach((v, i) => {
    const colour = VARIANT_COLOUR[v] || PALETTE.navy;
    const label = data.series[v].meta.label;
    const pts = data.series[v].monthly;
    const reported = pts.map((p) => (p.quality === 'reported' ? p.value : null));
    // repeat the join point so the dashed line starts where the solid one ends
    const modelled = pts.map((p, idx) => {
      if (p.quality !== 'reported') return p.value;
      return (startIndex !== null && idx === startIndex - 1) ? p.value : null;
    });
    datasets.push({
      label: `${label} — reported`,
      data: reported, borderColor: colour, backgroundColor: colour,
      borderWidth: 2, pointRadius: 0, pointHoverRadius: 3, tension: 0,
      spanGaps: false, order: 10 - i,
    });
    datasets.push({
      label: `${label} — modelled`,
      data: modelled, borderColor: colour, backgroundColor: colour,
      borderWidth: 2, borderDash: [6, 4], pointRadius: 0, pointHoverRadius: 3, tension: 0,
      spanGaps: false, order: 10 - i,
    });
  });

  // Annual level overlay. The annual estimate is the primary model output;
  // the monthly path is a disaggregation of it. Plotting the annual level as a
  // step at annual/12 -- the average monthly rate for that year -- puts it on
  // the same axis as the monthly curve, so the monthly line must average to the
  // step across each calendar year. Solid where the year is reported carbon
  // data, dotted where it is modelled.
  if (state.showAnnual) {
    present.forEach((v, i) => {
      const colour = VARIANT_COLOUR[v] || PALETTE.navy;
      const label = data.series[v].meta.label;
      const byYear = new Map(data.series[v].annual.map((a) => [a.year, a]));
      const level = (q) => base.map((p) => {
        const a = byYear.get(p.year);
        if (!a) return null;
        return (a.quality === 'reported') === (q === 'reported') ? a.value / 12 : null;
      });
      datasets.push({
        label: `${label} — annual level (reported)`,
        data: level('reported'), borderColor: colour, backgroundColor: colour,
        borderWidth: 1.25, pointRadius: 0, stepped: 'middle', tension: 0,
        spanGaps: false, order: 20 - i,
      });
      datasets.push({
        label: `${label} — annual level (modelled)`,
        data: level('modelled'), borderColor: colour, backgroundColor: colour,
        borderWidth: 1.25, borderDash: [2, 3], pointRadius: 0, stepped: 'middle',
        tension: 0, spanGaps: false, order: 20 - i,
      });
    });
  }

  const opts = baseOptions({
    yTitle: `tCO₂e attributed per month, on ${int(state.investment)} invested`,
    tickFormatter: compact,
  });
  opts.scales.x.ticks.callback = (value, index) => {
    const iso = labels[index];
    if (!iso) return '';
    return iso.slice(5, 7) === '01' && Number(iso.slice(0, 4)) % 2 === 0 ? iso.slice(0, 4) : '';
  };
  opts.plugins.modelledRegion = {
    startIndex,
    label: `Modelled — no reported carbon data after ${meta.carbon_years.last}`,
  };
  opts.plugins.tooltip.filter = (item) => !item.dataset.label.startsWith('__');
  opts.plugins.tooltip.callbacks = {
    title: (items) => `${monthLabel(labels[items[0].dataIndex])} · ${
      quality[items[0].dataIndex] === 'reported' ? 'reported carbon data' : 'MODELLED'}`,
    label: (item) => `${item.dataset.label.split(' — ')[0]}: ${num(item.parsed.y)} tCO₂e`,
  };

  render(CANVAS, { type: 'line', data: { labels, datasets }, options: opts });

  // custom legend — line style carries the reported/modelled distinction
  document.getElementById('company-legend').innerHTML = present.map((v) => `
    <span class="li"><span class="ln" style="border-top-color:${VARIANT_COLOUR[v]}"></span>${esc(data.series[v].meta.label)}</span>`).join('')
    + `<span class="li"><span class="ln dashed" style="border-top-color:${PALETTE.navy}"></span>Modelled years</span>`
    + (state.showAnnual ? `<span class="li"><span class="ln" style="border-top-color:${PALETTE.navy};border-top-width:1px"></span>Annual level (÷12)</span>` : '')
    + (hasBand ? `<span class="li"><span class="bx" style="background:${hexA(VARIANT_COLOUR[focus], 0.24)}"></span>Interval, ${esc(data.series[focus].meta.label)}</span>` : '');

  const nowcastYears = `${meta.nowcast_from}\u2013${data.headline[focus] ? data.headline[focus].final_year : ''}`;
  // how far apart are the variants over the reported span? if they are all but
  // identical there, say so, otherwise the overplotted lines look like one line
  // and the reader cannot tell whether that is agreement or a rendering artefact
  let maxRel = 0;
  if (present.length > 1) {
    const ref = data.series[present[0]].monthly;
    present.slice(1).forEach((v) => {
      const b = data.series[v].monthly;
      ref.forEach((p, i) => {
        if (p.quality !== 'reported' || !b[i] || !p.value) return;
        maxRel = Math.max(maxRel, Math.abs((b[i].value - p.value) / p.value));
      });
    });
  }
  const agree = present.length > 1 && maxRel < 0.02;
  document.getElementById('company-chart-sub').textContent =
    `Solid line = reported carbon data to ${meta.carbon_years.last}. Dashed line and shaded region = ${nowcastYears}, model output.`
    + (agree
      ? ` Over the reported span the variants differ by at most ${pct(maxRel * 100)}, so they plot on top of one another; they diverge only where the data ends.`
      : '');
  // Reconciliation: the monthly path is a disaggregation of the annual
  // estimate, so each calendar year's twelve months must sum to the annual
  // total. Check it in the browser rather than asserting it.
  let worstRel = 0;
  present.forEach((v) => {
    const sums = new Map();
    data.series[v].monthly.forEach((p) => {
      sums.set(p.year, (sums.get(p.year) || 0) + p.value);
    });
    data.series[v].annual.forEach((a) => {
      const got = sums.get(a.year);
      if (got === undefined || !a.value) return;
      worstRel = Math.max(worstRel, Math.abs(got - a.value) / Math.abs(a.value));
    });
  });
  const reconcile = worstRel < 1e-6
    ? `<b>Annual reconciliation:</b> each calendar year's twelve monthly values sum to that year's annual estimate exactly (largest discrepancy ${(worstRel * 100).toExponential(1)}%). `
    : `<b class="warn">Annual reconciliation FAILED:</b> largest discrepancy ${pct(worstRel * 100)} between the sum of monthly values and the annual estimate. `;

  document.getElementById('company-caption').innerHTML =
    `<b>Annual first, then monthly.</b> The annual level is the model's actual output. The monthly path is a `
    + `mean-preserving disaggregation of it: cumulative emissions are interpolated with a monotone curve and each `
    + `month is that curve's increment, so annual totals hold by construction and the path has no step at year `
    + `boundaries. The stepped line is the annual level shown as an average monthly rate (annual ÷ 12) — solid where `
    + `the year is reported carbon data, dotted where it is modelled. `
    + reconcile
    + `The monthly shape carries no information beyond the annual points; month-to-month movement is a smoothing `
    + `convention, not data. `
    + `Shaded band is the model's interval for <b>${esc(data.series[focus].meta.label)}</b> and is approximately a 50% `
    + `interval — roughly half of outcomes would be expected to fall outside it, so it is not a worst case. `
    + `Values are tCO₂e attributed to ${int(state.investment)} invested, using an enterprise-value denominator, so a `
    + `change in enterprise value moves the series without any change in company emissions.`;
}

function hexA(hex, a) {
  const h = hex.replace('#', '');
  const r = parseInt(h.slice(0, 2), 16), g = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${a})`;
}

/* ------------------------------------------------------------------ table */
function drawAnnualTable(data) {
  const present = state.variants.filter((v) => data.series[v]);
  const years = [...new Set(present.flatMap((v) => data.series[v].annual.map((a) => a.year)))].sort();
  const lookup = {};
  present.forEach((v) => {
    lookup[v] = {};
    data.series[v].annual.forEach((a) => { lookup[v][a.year] = a; });
  });
  const qualityOf = (y) => {
    const a = lookup[present[0]][y];
    return a ? a.quality : 'estimated';
  };

  const head = `<thead><tr><th scope="col">Year</th><th scope="col">Basis</th>`
    + present.map((v) => `<th scope="col">${esc(data.series[v].meta.label)} (tCO₂e)</th>`).join('')
    + `<th scope="col">Enterprise value</th></tr></thead>`;

  const rows = years.map((y) => {
    const q = qualityOf(y);
    const ev = lookup[present[0]][y] ? lookup[present[0]][y].ev : null;
    return `<tr class="${q === 'reported' ? '' : 'row-modelled'}" data-testid="annual-row-${y}">
      <th scope="row">${y}</th>
      <td>${tag(q === 'reported' ? 'reported' : 'modelled')}</td>
      ${present.map((v) => `<td class="num">${lookup[v][y] ? num(lookup[v][y].value) : 'n/a'}</td>`).join('')}
      <td class="num">${ev === null || ev === undefined ? 'n/a' : num(ev, 0)}</td>
    </tr>`;
  }).join('');

  document.getElementById('company-annual-table').innerHTML =
    `<caption>Annual attributed emissions by variant. Rows tagged “Modelled” contain no reported carbon data.</caption>`
    + head + `<tbody>${rows}</tbody>`;
}

/* --------------------------------------------------------- variant notes */
function renderVariantNotes() {
  document.getElementById('variant-notes').innerHTML = meta.variants.map((v) => `
    <div class="note" style="border-left-color:${VARIANT_COLOUR[v.id] || PALETTE.border}">
      <h4><span class="swatch" style="background:${VARIANT_COLOUR[v.id] || PALETTE.navy}"></span>${esc(v.label)}</h4>
      <p>${esc(v.description)}</p>
      <p class="caveat"><b>Caveat.</b> ${esc(v.caveat)}</p>
      <p>Parameters: <code>cap ${esc(v.params.cap_mode)}</code>,
         <code>drift ${esc(String(v.params.drift_offset))}</code>,
         <code>sales ${esc(v.params.sales_mode)}</code></p>
    </div>`).join('');
}

export { state as companyState };
