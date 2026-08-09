// View 2 — Portfolio. The decomposition is the analytical point.
import { api } from './api.js';
import {
  PALETTE, num, int, signedNum, signedPct, compact, quarterLabel, yearOf, esc,
} from './fmt.js';
import { baseOptions, render, destroy } from './charts.js';
import { skeleton, empty, errorStrip, pending, tag } from './ui.js';

const LINE = 'portfolio-chart';
const WATER = 'waterfall-chart';
const EFFECTS = 'effects-chart';
let meta = null;
const state = { name: null, variant: null, reqId: 0 };

export function initPortfolio(appMeta) {
  meta = appMeta;
  state.variant = meta.default_variant;
  const vs = document.getElementById('portfolio-variant');
  vs.innerHTML = meta.variants.map((v) =>
    `<option value="${esc(v.id)}" ${v.id === meta.default_variant ? 'selected' : ''}>${esc(v.label)} — ${esc(v.short)}</option>`).join('');
  vs.addEventListener('change', () => { state.variant = vs.value; loadPortfolio(); });
  document.getElementById('portfolio-pick').addEventListener('change', (e) => {
    state.name = e.target.value; loadPortfolio();
  });
}

let listLoaded = false;

export async function loadPortfolioList() {
  if (listLoaded) return;
  const pick = document.getElementById('portfolio-pick');
  const hint = document.getElementById('portfolio-hint');
  try {
    const rows = await api.portfolios();
    if (!rows || !rows.length) {
      pick.innerHTML = '<option value="">No portfolio available</option>';
      hint.textContent = 'No portfolio holdings have been loaded on the server.';
      document.getElementById('portfolio-coverage').innerHTML =
        pending('Portfolio results are still being computed',
          'The portfolio library is empty, which usually means the holdings artefact has not been written yet.',
          'retry-portfolio');
      wireRetry('retry-portfolio', () => { listLoaded = false; loadPortfolioList(); });
      return;
    }
    listLoaded = true;
    pick.innerHTML = rows.map((r) =>
      `<option value="${esc(r.name)}">${esc(r.name)}</option>`).join('');
    const first = rows[0];
    hint.textContent = `${int(first.periods)} quarterly periods, ${int(first.holdings)} holdings, ${first.start} to ${first.end}.`;
    state.name = first.name;
    state.portfolios = rows;
    await loadPortfolio();
  } catch (err) {
    document.getElementById('portfolio-coverage').innerHTML = errorStrip(err, 'the portfolio library');
  }
}

export async function loadPortfolio() {
  if (!state.name) return;
  const reqId = ++state.reqId;
  const cards = document.getElementById('portfolio-cards');
  cards.innerHTML = skeleton(2, false);
  document.getElementById('portfolio-coverage').innerHTML = '';

  try {
    const d = await api.portfolio(state.name, state.variant);
    if (reqId !== state.reqId) return;
    drawCoverage(d);
    drawFinding(d);
    drawCards(d);
    drawLine(d);
    drawWaterfall(d);
    drawEffects(d);
    drawTable(d);
    drawVariantCompare(d);
  } catch (err) {
    if (reqId !== state.reqId) return;
    destroy(LINE); destroy(WATER); destroy(EFFECTS);
    document.getElementById('decomp-table').innerHTML = '';
    document.getElementById('variant-compare').innerHTML = '';
    document.getElementById('variant-compare-caption').textContent = '';
    document.getElementById('portfolio-finding').innerHTML = '';
    document.getElementById('portfolio-caption').textContent = '';
    document.getElementById('waterfall-caption').textContent = '';
    if (err.status === 503 || err.status === 404) {
      cards.innerHTML = '';
      document.getElementById('portfolio-coverage').innerHTML = pending(
        'Portfolio results are still being computed',
        err.status === 503
          ? 'The server reports the portfolio cache has not been built yet (HTTP 503).'
          : `No cached result yet for ${state.name} on the ${state.variant} variant (HTTP 404).`,
        'retry-portfolio');
      wireRetry('retry-portfolio', loadPortfolio);
    } else {
      cards.innerHTML = errorStrip(err, `portfolio ${state.name}`);
    }
  }
}

function wireRetry(id, fn) {
  const b = document.getElementById(id);
  if (b) b.addEventListener('click', fn);
}

/* --------------------------------------------------------------- coverage */
function drawCoverage(d) {
  const bad = d.series.filter((p) => p.uncovered > 0);
  const host = document.getElementById('portfolio-coverage');
  if (!bad.length) {
    host.innerHTML = `<div class="strip info">Every holding in every period has carbon data. No exclusions.</div>`;
    return;
  }
  const last = bad[bad.length - 1];
  host.innerHTML = `<div class="strip" role="status" data-testid="coverage-warning">
    <b>Incomplete coverage.</b> ${int(last.uncovered)} of ${int(last.holdings)} holdings have no carbon data in
    ${yearOf(last.date)} and are excluded from the attributed total.
    ${bad.length} of ${d.series.length} periods are affected; the attributed level is therefore understated
    by an unknown amount, and coverage changes between periods move the total on their own.
  </div>`;
}


/* ---------------------------------------------------------------- finding */
/* The headline percentage is the number a reader will quote. It is also the
   number most likely to be misread as decarbonisation. This block states, in
   words and in figures, how much of the move is actually companies emitting
   less — and it changes its wording when the emissions effect is positive,
   because in that case the headline fall is happening while emissions RISE. */
function drawFinding(d) {
  const c = d.cumulative;
  const h = d.headline;
  const host = document.getElementById('portfolio-finding');
  const shareOf = (part) => (c.total ? (part / c.total) * 100 : null);
  const emShare = shareOf(c.emissions);
  const emissionsRose = c.emissions > 0;
  const headlineFell = h.pct_change < 0;

  let sentence;
  if (emissionsRose && headlineFell) {
    sentence = `Attributed emissions fell <b>${signedPct(h.pct_change)}</b>, but the emissions of the `
      + `underlying companies <b>rose</b>. The emissions effect is <b>${signedNum(c.emissions, 0)} tCO₂e</b> — `
      + `it works against the headline. The entire reported fall comes from enterprise values rising `
      + `(${signedNum(c.valuation, 0)}) and from reweighting the book (${signedNum(c.allocation, 0)}). `
      + `On this variant, <b>none</b> of the headline is companies emitting less.`;
  } else if (emissionsRose) {
    sentence = `Attributed emissions rose <b>${signedPct(h.pct_change)}</b>, and the emissions effect `
      + `(<b>${signedNum(c.emissions, 0)} tCO₂e</b>, ${num(emShare, 1)}% of the move) is part of that rise.`;
  } else {
    sentence = `Attributed emissions fell <b>${signedPct(h.pct_change)}</b>, but only `
      + `<b>${num(emShare, 1)}% of that move</b> is companies emitting less. The emissions effect is `
      + `<b>${signedNum(c.emissions, 0)} tCO₂e</b>. The rest is enterprise values rising `
      + `(${num(shareOf(c.valuation), 1)}% of the move) and the book being reweighted `
      + `(${num(shareOf(c.allocation), 1)}%). Neither of those is a company emitting less.`;
  }

  // when the three effects do not all point the same way, shares of the net move
  // exceed 100% and must be explained rather than left to look like an error
  const mixed = new Set([c.emissions, c.valuation, c.allocation]
    .filter((v) => v).map((v) => Math.sign(v))).size > 1;
  const footnote = mixed
    ? `<p class="finding-note">Shares are contributions to the <i>net</i> move. Because the effects do not `
      + `all point the same way here, they sum to 100% only after the offsetting term is subtracted: `
      + `${num(shareOf(c.emissions), 1)}% + ${num(shareOf(c.valuation), 1)}% + `
      + `${num(shareOf(c.allocation), 1)}% = 100%.</p>`
    : '';

  host.innerHTML = `<div class="finding" data-testid="finding-block">
    <h3>What the headline number is, and is not</h3>
    <p>${sentence}</p>
    ${footnote}
    <div class="share">
      <div>
        <span>Headline change</span>
        <b class="${headlineFell ? 'neg' : 'pos'}" data-testid="finding-headline">${signedPct(h.pct_change)}</b>
        <em>${tag(d.series[d.series.length - 1].quality)} ${esc(h.start_date)} → ${esc(h.end_date)}</em>
      </div>
      <div>
        <span>Of that, decarbonisation</span>
        <b style="color:${emissionsRose ? PALETTE.negative : PALETTE.cerulean}" data-testid="finding-share">${
          emissionsRose ? 'none' : num(emShare, 1) + '%'}</b>
        <em>emissions effect ${signedNum(c.emissions, 0)} tCO₂e</em>
      </div>
      <div>
        <span>Enterprise values</span>
        <b style="color:${PALETTE.gold}">${num(shareOf(c.valuation), 1)}%</b>
        <em>${signedNum(c.valuation, 0)} tCO₂e</em>
      </div>
      <div>
        <span>Reweighting the book</span>
        <b style="color:${PALETTE.teal}">${num(shareOf(c.allocation), 1)}%</b>
        <em>${signedNum(c.allocation, 0)} tCO₂e</em>
      </div>
    </div>
  </div>`;
}

/* ------------------------------------------------------------------ cards */
function drawCards(d) {
  const h = d.headline;
  const first = d.series[0], last = d.series[d.series.length - 1];
  const endBasis = last.quality;
  document.getElementById('portfolio-cards').innerHTML = `
    <article class="card" data-testid="card-portfolio-level">
      <h3 class="card-variant">Attributed emissions</h3>
      <div class="metric">
        <span class="metric-label">Start of period</span>
        <span class="metric-value" data-testid="metric-portfolio-start">${num(h.start, 0)}</span>
        <span class="metric-basis">${tag(first.quality)} ${esc(h.start_date)} · tCO₂e</span>
      </div>
      <div class="metric">
        <span class="metric-label">End of period</span>
        <span class="metric-value" data-testid="metric-portfolio-end">${num(h.end, 0)}</span>
        <span class="metric-basis">${tag(endBasis)} ${esc(h.end_date)} · tCO₂e</span>
      </div>
    </article>
    <article class="card" data-testid="card-portfolio-change">
      <h3 class="card-variant">Change over the period</h3>
      <div class="metric">
        <span class="metric-label">Total change in attributed emissions</span>
        <span class="metric-value ${h.pct_change < 0 ? 'neg' : 'pos'}" data-testid="metric-portfolio-change">${signedPct(h.pct_change)}</span>
        <span class="metric-basis">${tag(endBasis)} ${esc(h.start_date)} → ${esc(h.end_date)}
          · all three effects combined</span>
      </div>
      <div class="metric">
        <span class="metric-label">Of which the emissions effect — the only decarbonisation term</span>
        <span class="metric-value ${d.cumulative.emissions < 0 ? 'neg' : 'pos'}" data-testid="metric-portfolio-emissions-effect">${signedNum(d.cumulative.emissions, 0)}</span>
        <span class="metric-basis">tCO₂e, ${h.start_date ? esc(h.start_date) : ''} → ${esc(h.end_date)}
          · ${pctOfTotal(d.cumulative.emissions, d.cumulative.total)} of the total change</span>
      </div>
    </article>
    <article class="card" data-testid="card-portfolio-other">
      <h3 class="card-variant">Non-emissions effects</h3>
      <div class="metric">
        <span class="metric-label">Valuation effect — enterprise values moving</span>
        <span class="metric-value" style="color:${PALETTE.gold}" data-testid="metric-portfolio-valuation-effect">${signedNum(d.cumulative.valuation, 0)}</span>
        <span class="metric-basis">tCO₂e · ${pctOfTotal(d.cumulative.valuation, d.cumulative.total)} of the total change</span>
      </div>
      <div class="metric">
        <span class="metric-label">Allocation effect — reweighting the book</span>
        <span class="metric-value" style="color:${PALETTE.teal}" data-testid="metric-portfolio-allocation-effect">${signedNum(d.cumulative.allocation, 0)}</span>
        <span class="metric-basis">tCO₂e · ${pctOfTotal(d.cumulative.allocation, d.cumulative.total)} of the total change</span>
      </div>
    </article>`;
}

function pctOfTotal(part, total) {
  if (!total) return 'n/a';
  return num((part / total) * 100, 1) + '%';
}

/* ------------------------------------------------------------------- line */
function drawLine(d) {
  const labels = d.series.map((p) => p.date);
  const quality = d.series.map((p) => p.quality);
  // The shaded region marks the fully modelled years only: everything after the
  // last reported carbon year. Part-modelled periods are marked on the line itself.
  let startIndex = labels.findIndex((iso) => yearOf(iso) > meta.carbon_years.last);
  if (startIndex < 0) startIndex = null;

  const rank = (q) => (q === 'reported' ? 0 : (q === 'mixed' ? 1 : 2));
  const dashFor = (r) => (r === 0 ? undefined : (r === 1 ? [2, 3] : [6, 4]));
  const values = d.series.map((p) => p.value);

  const opts = baseOptions({ yTitle: 'tCO₂e attributed', tickFormatter: compact });
  opts.scales.x.ticks.callback = (v, i) => (labels[i] ? quarterLabel(labels[i]) : '');
  opts.scales.x.ticks.maxRotation = 60;
  opts.scales.x.ticks.minRotation = 60;
  opts.scales.x.ticks.autoSkip = true;
  opts.plugins.modelledRegion = {
    startIndex,
    label: `Modelled — no reported carbon data after ${meta.carbon_years.last}`,
  };
  const basisWord = (q) => (q === 'reported' ? 'reported carbon data'
    : (q === 'mixed' ? 'PART MODELLED' : 'MODELLED'));
  opts.plugins.tooltip.callbacks = {
    title: (items) => `${quarterLabel(labels[items[0].dataIndex])} · ${basisWord(quality[items[0].dataIndex])}`,
    label: (item) => {
      const p = d.series[item.dataIndex];
      return `${num(item.parsed.y, 0)} tCO₂e · ${int(p.covered)}/${int(p.holdings)} holdings covered`;
    },
  };

  render(LINE, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Attributed emissions',
        data: values,
        borderColor: PALETTE.cerulean,
        backgroundColor: PALETTE.cerulean,
        borderWidth: 2,
        tension: 0,
        pointRadius: 2.6,
        pointBackgroundColor: quality.map((q) => (q === 'reported' ? PALETTE.cerulean : '#FFFFFF')),
        pointBorderColor: PALETTE.cerulean,
        pointBorderWidth: 1.5,
        segment: {
          borderDash: (ctx) => dashFor(Math.max(rank(quality[ctx.p0DataIndex]), rank(quality[ctx.p1DataIndex]))),
        },
      }],
    },
    options: opts,
  });

  document.getElementById('portfolio-legend').innerHTML = `
    <span class="li"><span class="ln" style="border-top-color:${PALETTE.cerulean}"></span>Reported carbon data</span>
    <span class="li"><span class="ln dotted" style="border-top-color:${PALETTE.cerulean}"></span>Part modelled</span>
    <span class="li"><span class="ln dashed" style="border-top-color:${PALETTE.cerulean}"></span>Fully modelled</span>`;
  document.getElementById('portfolio-chart-sub').textContent =
    `${esc(d.name)} · ${d.meta.label} variant · ${d.series.length} quarterly periods.`;
  document.getElementById('portfolio-caption').innerHTML =
    `The shaded region covers ${meta.nowcast_from} onward, where <b>no</b> holding has reported carbon data. `
    + `A dotted segment marks a period in which <b>some</b> holdings already rely on modelled emissions even though the `
    + `year is within the reported window; hollow markers flag any period that is not wholly reported. `
    + `<b>Annual inputs, quarterly holdings.</b> Company emissions and enterprise values are annual figures, `
    + `so they are constant within a calendar year. Quarter-on-quarter moves inside the same year therefore `
    + `reflect changes in the book only, and the emissions and valuation effects are zero by construction for `
    + `those periods — not because nothing happened. Compare year-on-year, or read the cumulative figures. `
    + `Caveat for this variant: ${esc(d.meta.caveat)}`;
}

/* -------------------------------------------------------------- waterfall */
function drawWaterfall(d) {
  const c = d.cumulative;
  const s = d.headline.start;
  const a1 = s + c.emissions;
  const a2 = a1 + c.valuation;
  const a3 = a2 + c.allocation;

  const labels = ['Start', 'Emissions effect', 'Valuation effect', 'Allocation effect', 'End'];
  const bars = [[0, s], [s, a1], [a1, a2], [a2, a3], [0, d.headline.end]];
  const colours = [PALETTE.navy, PALETTE.cerulean, PALETTE.gold, PALETTE.teal, PALETTE.navy];
  const deltas = [null, c.emissions, c.valuation, c.allocation, null];

  const opts = baseOptions({ yTitle: 'tCO₂e attributed', tickFormatter: compact, beginAtZero: true });
  opts.scales.x.ticks.font = { size: 11 };
  opts.scales.x.ticks.color = PALETTE.body;
  opts.plugins.tooltip.callbacks = {
    title: (items) => labels[items[0].dataIndex],
    label: (item) => {
      const i = item.dataIndex;
      if (deltas[i] === null) return `${num(bars[i][1], 0)} tCO₂e`;
      return `${signedNum(deltas[i], 0)} tCO₂e`;
    },
  };
  opts.plugins.modelledRegion = { startIndex: null };

  // Direct value labels above/below each bar, plus hairline connectors.
  const valueLabels = {
    id: 'waterfallLabels',
    afterDatasetsDraw(chart) {
      const { ctx } = chart;
      const m = chart.getDatasetMeta(0);
      ctx.save();
      ctx.strokeStyle = PALETTE.border;
      ctx.lineWidth = 1;
      for (let i = 0; i < m.data.length - 1; i += 1) {
        const a = m.data[i], b = m.data[i + 1];
        const yScale = chart.scales.y;
        const yPix = yScale.getPixelForValue(i === m.data.length - 2 ? bars[i][1] : bars[i][1]);
        ctx.beginPath();
        ctx.moveTo(a.x + (a.width / 2), yPix);
        ctx.lineTo(b.x - (b.width / 2), yPix);
        ctx.stroke();
      }
      ctx.textAlign = 'center';
      m.data.forEach((el, i) => {
        const top = Math.min(el.y, el.base);
        const bottom = Math.max(el.y, el.base);
        const isDelta = deltas[i] !== null;
        ctx.fillStyle = isDelta ? PALETTE.body : PALETTE.navy;
        ctx.textBaseline = 'bottom';
        ctx.font = '700 11px Calibri, "Segoe UI", system-ui, sans-serif';
        ctx.fillText(isDelta ? signedNum(deltas[i], 0) : num(bars[i][1], 0), el.x, top - 4);
        if (!isDelta) return;
        // share of the total move, printed on the bar itself: the bar for a small
        // effect is easy to overlook, the number is not
        const share = c.total ? (deltas[i] / c.total) * 100 : null;
        if (share === null) return;
        ctx.font = '700 10px Calibri, "Segoe UI", system-ui, sans-serif';
        ctx.fillStyle = PALETTE.muted;
        ctx.fillText(`${num(share, 1)}% of the move`, el.x, top - 18);
        if (i === 1) {
          // the emissions effect is the only decarbonisation term; say so in place
          ctx.font = 'italic 10px Calibri, "Segoe UI", system-ui, sans-serif';
          ctx.fillStyle = deltas[i] > 0 ? PALETTE.negative : PALETTE.cerulean;
          ctx.textBaseline = 'top';
          ctx.fillText(deltas[i] > 0 ? 'emissions ROSE' : 'the only decarbonisation',
            el.x, bottom + 6);
        }
      });
      ctx.restore();
    },
  };

  render(WATER, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Decomposition', data: bars,
        backgroundColor: colours, borderColor: '#FFFFFF', borderWidth: 1,
        borderSkipped: false, barPercentage: 0.68, categoryPercentage: 0.8,
      }],
    },
    options: opts,
    plugins: [valueLabels],
  });

  document.getElementById('waterfall-sub').textContent =
    `${esc(d.name)} · ${d.headline.start_date} to ${d.headline.end_date} · exact three-way decomposition, tCO₂e.`;
  const emShare = c.total ? (c.emissions / c.total) * 100 : null;
  document.getElementById('waterfall-caption').innerHTML =
    `<b>Only the emissions effect is decarbonisation${c.emissions > 0
      ? ', and on this variant it is negative decarbonisation — emissions rose'
      : `, and it is ${num(emShare, 1)}% of the move`}.</b> `
    + `The valuation effect is the portfolio's enterprise values `
    + `moving: because attribution divides company emissions by enterprise value, a market rally on its own reduces `
    + `attributed emissions with no change in what the companies emit. The allocation effect is the result of `
    + `reweighting the book toward or away from carbon-intensive names. The three terms sum exactly to the total change `
    + `(${signedNum(d.cumulative.total, 0)} tCO₂e). Periods from ${meta.nowcast_from} onward use modelled emissions.`;
}


/* ---------------------------------------------------------------- effects */
/* On the waterfall the emissions effect is drawn against a 14m tCO2e axis, so a
   300k effect is a hairline and can be missed entirely. Replotting the three
   effects on their own axis makes the relative size visible without changing
   any value. */
function drawEffects(d) {
  const c = d.cumulative;
  const labels = ['Emissions effect', 'Valuation effect', 'Allocation effect'];
  const vals = [c.emissions, c.valuation, c.allocation];
  const colours = [c.emissions > 0 ? PALETTE.negative : PALETTE.cerulean, PALETTE.gold, PALETTE.teal];

  const opts = baseOptions({ yTitle: 'tCO₂e attributed', tickFormatter: compact });
  opts.scales.x.ticks.font = { size: 11 };
  opts.scales.x.ticks.color = PALETTE.body;
  opts.scales.x.ticks.padding = 8;
  opts.plugins.modelledRegion = { startIndex: null };
  opts.plugins.zeroLine = { enabled: true };
  opts.plugins.tooltip.callbacks = {
    label: (i) => `${signedNum(i.parsed.y, 0)} tCO₂e · ${
      c.total ? num((i.parsed.y / c.total) * 100, 1) + '% of the total move' : 'n/a'}`,
  };
  opts.layout = { padding: { top: 8, bottom: 6 } };
  // headroom so the value and share labels are never clipped against the zero line
  const maxAbs = Math.max(...vals.map((v) => Math.abs(v))) || 1;
  opts.scales.y.suggestedMax = Math.max(0, ...vals) + (maxAbs * 0.22);
  opts.scales.y.suggestedMin = Math.min(0, ...vals) - (maxAbs * 0.06);

  const labelsPlugin = {
    id: 'effectsLabels',
    afterDatasetsDraw(chart) {
      const { ctx } = chart;
      ctx.save();
      ctx.textAlign = 'center';
      chart.getDatasetMeta(0).data.forEach((el, i) => {
        const v = vals[i];
        const above = v < 0;   // negative bars hang below zero, label above the zero line
        ctx.fillStyle = PALETTE.body;
        ctx.font = '700 12px Calibri, "Segoe UI", system-ui, sans-serif';
        ctx.textBaseline = above ? 'bottom' : 'bottom';
        const yTop = Math.min(el.y, el.base);
        ctx.fillText(signedNum(v, 0), el.x, yTop - 5);
        ctx.font = '700 10px Calibri, "Segoe UI", system-ui, sans-serif';
        ctx.fillStyle = PALETTE.muted;
        ctx.fillText(c.total ? `${num((v / c.total) * 100, 1)}% of the move` : '', el.x, yTop - 19);
      });
      ctx.restore();
    },
  };

  render(EFFECTS, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Effect', data: vals, backgroundColor: colours,
        borderColor: '#FFFFFF', borderWidth: 1, barPercentage: 0.5, categoryPercentage: 0.72,
      }],
    },
    options: opts,
    plugins: [labelsPlugin],
  });

  document.getElementById('effects-sub').textContent =
    `${d.name} · ${d.meta.label} variant · same three numbers as the waterfall, plotted against the size of the effects rather than the level.`;
  const emShare = c.total ? (c.emissions / c.total) * 100 : null;
  document.getElementById('effects-caption').innerHTML = c.emissions > 0
    ? `The emissions effect points the other way from the headline on this variant: the companies emitted `
      + `<b>more</b>, by ${signedNum(c.emissions, 0)} tCO₂e, and the fall in the attributed total is entirely `
      + `the valuation and allocation terms.`
    : `The emissions effect is the smallest of the three at ${num(emShare, 1)}% of the move. `
      + `A reader looking only at the headline would attribute the whole fall to decarbonisation; `
      + `${num(100 - emShare, 1)}% of it is enterprise values and portfolio weights.`;
}

/* ------------------------------------------------------------------ table */
function drawTable(d) {
  const head = `<thead><tr>
      <th scope="col">Period</th><th scope="col">Basis</th>
      <th scope="col">Emissions effect</th><th scope="col">Valuation effect</th>
      <th scope="col">Allocation effect</th><th scope="col">Total change</th>
    </tr></thead>`;
  const qualityAt = {};
  d.series.forEach((p) => { qualityAt[p.date] = p.quality; });

  const rows = d.decomposition.map((r) => {
    const q = qualityAt[r.to] || 'estimated';
    return `<tr class="${q === 'reported' ? '' : 'row-modelled'}" data-testid="decomp-row-${esc(r.to)}">
      <th scope="row">${quarterLabel(r.from)} → ${quarterLabel(r.to)}</th>
      <td>${tag(q)}</td>
      <td class="num">${signedNum(r.emissions, 0)}</td>
      <td class="num">${signedNum(r.valuation, 0)}</td>
      <td class="num">${signedNum(r.allocation, 0)}</td>
      <td class="num">${signedNum(r.total, 0)}</td>
    </tr>`;
  }).join('');

  const c = d.cumulative;
  const foot = `<tfoot><tr>
      <td>Cumulative</td><td></td>
      <td class="num">${signedNum(c.emissions, 0)}</td>
      <td class="num">${signedNum(c.valuation, 0)}</td>
      <td class="num">${signedNum(c.allocation, 0)}</td>
      <td class="num">${signedNum(c.total, 0)}</td>
    </tr></tfoot>`;

  document.getElementById('decomp-table').innerHTML =
    `<caption>Quarter-on-quarter decomposition, tCO₂e. “Modelled” = the period contains no reported carbon data; “Part modelled” = some holdings are estimated. Emissions and valuation effects are zero for periods within a single calendar year because both inputs are annual; only the year-crossing rows carry them.</caption>`
    + head + `<tbody>${rows}</tbody>` + foot;
}

/* -------------------------------------------------- variant comparison table */
/* The same book, priced the same way, under all three model variants. This is the
   sharpest available test of how much of the headline is a modelling choice: on
   this dataset the emissions effect changes sign between variants while every
   headline still reads as a large fall. */
let compareToken = 0;
async function drawVariantCompare(shown) {
  const host = document.getElementById('variant-compare');
  const cap = document.getElementById('variant-compare-caption');
  const token = ++compareToken;
  host.innerHTML = '<caption>Loading the other variants for the same book…</caption>';
  cap.textContent = '';

  const ids = meta.variants.map((v) => v.id);
  let rows;
  try {
    rows = await Promise.all(ids.map(async (id) => {
      if (id === shown.variant) return { id, d: shown };
      try { return { id, d: await api.portfolio(shown.name, id) }; }
      catch (err) { return { id, err }; }
    }));
  } catch (err) {
    host.innerHTML = '';
    cap.textContent = 'The other variants could not be loaded for this comparison.';
    return;
  }
  if (token !== compareToken) return;

  const labelOf = (id) => (meta.variants.find((v) => v.id === id) || {}).label || id;
  const body = rows.map(({ id, d, err }) => {
    if (err) {
      return `<tr><th scope="row">${esc(labelOf(id))}</th>
        <td colspan="5" style="text-align:left;color:var(--muted)">Not available (HTTP ${err.status || '—'})</td></tr>`;
    }
    const c = d.cumulative;
    const share = c.total ? (c.emissions / c.total) * 100 : null;
    const rose = c.emissions > 0;
    return `<tr class="${id === shown.variant ? 'row-focus' : ''}" data-testid="compare-row-${esc(id)}">
      <th scope="row">${esc(labelOf(id))}${id === shown.variant ? ' <span class="muted-note">(shown above)</span>' : ''}</th>
      <td class="num ${d.headline.pct_change < 0 ? 'neg' : 'pos'}">${signedPct(d.headline.pct_change)}</td>
      <td class="num" style="color:${rose ? PALETTE.negative : PALETTE.cerulean};font-weight:700">${signedNum(c.emissions, 0)}</td>
      <td class="num" style="color:${rose ? PALETTE.negative : PALETTE.body}">${rose ? 'emissions rose' : num(share, 1) + '%'}</td>
      <td class="num">${signedNum(c.valuation, 0)}</td>
      <td class="num">${signedNum(c.allocation, 0)}</td>
    </tr>`;
  }).join('');

  host.innerHTML = `<caption>Same holdings, same enterprise values, same reported carbon data to
      ${meta.carbon_years.last}. Only the treatment of the modelled years differs.</caption>
    <thead><tr>
      <th scope="col">Variant</th>
      <th scope="col">Headline change</th>
      <th scope="col">Emissions effect (tCO₂e)</th>
      <th scope="col">Share of the move</th>
      <th scope="col">Valuation effect</th>
      <th scope="col">Allocation effect</th>
    </tr></thead><tbody>${body}</tbody>`;

  const ok = rows.filter((r) => r.d);
  const signs = new Set(ok.map((r) => Math.sign(r.d.cumulative.emissions)));
  const allFall = ok.every((r) => r.d.headline.pct_change < 0);
  cap.innerHTML = signs.size > 1 && allFall
    ? `<b>The emissions effect changes sign between variants while every headline still reads as a fall.</b> `
      + `The direction of the only decarbonisation term is therefore a modelling choice on this book, not `
      + `an observation. Do not quote the headline percentage without the variant and the emissions effect `
      + `beside it. The valuation and allocation effects are almost unchanged across variants, because they `
      + `rest on actual prices and actual weights.`
    : `The variants differ only in how the years after ${meta.carbon_years.last} are extrapolated; the `
      + `valuation and allocation effects rest on actual prices and weights and barely move between them.`;
}
