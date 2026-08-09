// View 3 — Model evidence. Backtest artefact; may legitimately be missing.
import { api } from './api.js';
import { PALETTE, VARIANT_COLOUR, num, pct, signedPct, int, esc, timestamp } from './fmt.js';
import { baseOptions, render, destroy } from './charts.js';
import { skeleton, errorStrip, pending } from './ui.js';

const ERR = 'error-chart';
const BIAS = 'bias-chart';
let meta = null;
let loaded = false;

export function initEvidence(appMeta) { meta = appMeta; }

export async function loadEvidence(force = false) {
  if (loaded && !force) return;
  const status = document.getElementById('evidence-status');
  const body = document.getElementById('evidence-body');
  status.innerHTML = skeleton(3, true);
  body.hidden = true;

  try {
    const d = await api.backtest();
    loaded = true;
    status.innerHTML = `<div class="strip info" data-testid="evidence-provenance">
      <b>Artefact provenance.</b> Generated ${esc(timestamp(d.generated_at))} over ${int(d.n_companies)} companies.
      If that timestamp is old relative to the data refresh, treat these numbers as stale.
    </div>`;
    body.hidden = false;
    drawFinding(d);
    drawTable(d);
    drawErrorChart(d);
    drawBiasChart(d);
    document.getElementById('evidence-note').textContent =
      [d.notes && d.notes.horizon, d.notes && d.notes.bias].filter(Boolean).join(' ')
      || 'Errors are out-of-sample forecast errors expressed as a share of the realised value.';
  } catch (err) {
    destroy(ERR); destroy(BIAS);
    body.hidden = true;
    if (err.status === 503) {
      status.innerHTML = pending(
        'Backtest results are still being computed',
        'The server reports the backtest artefact has not been written yet (HTTP 503). The full harness takes roughly 25 minutes.',
        'retry-evidence');
      const b = document.getElementById('retry-evidence');
      if (b) b.addEventListener('click', () => loadEvidence(true));
    } else {
      status.innerHTML = errorStrip(err, 'the backtest artefact');
    }
  }
}

const horizonsOf = (d) => Object.keys(d.horizons).sort((a, b) => Number(a) - Number(b));


/* ---------------------------------------------------------------- finding */
/* Two questions decide whether any of this modelling is worth running: does a
   variant beat the do-nothing benchmark, and which way does it err. Both are
   computed from the artefact rather than asserted. */
function drawFinding(d) {
  const hs = horizonsOf(d);
  const ids = meta.variants.map((v) => v.id);
  const labelOf = (id) => (meta.variants.find((v) => v.id === id) || { label: id }).label;
  const benchAt = (h) => (d.benchmarks && d.benchmarks[h] && d.benchmarks[h].persistence) || null;

  // how many horizons each variant beats persistence on
  const beats = {};
  ids.forEach((v) => {
    beats[v] = hs.filter((h) => {
      const s = d.horizons[h] && d.horizons[h][v];
      const b = benchAt(h);
      return s && b && s.median_abs < b.median_abs;
    });
  });
  const clean = ids.filter((v) => beats[v].length === hs.length);
  const partial = ids.filter((v) => beats[v].length > 0 && beats[v].length < hs.length);
  const never = ids.filter((v) => beats[v].length === 0);

  const phrase = (list) => {
    const names = list.map((v) => `<b>${esc(labelOf(v))}</b>`);
    if (names.length <= 1) return names.join('');
    return names.slice(0, -1).join(', ') + ' and ' + names[names.length - 1];
  };
  let verdict;
  if (clean.length) {
    verdict = `${phrase(clean)} beat${clean.length === 1 ? 's' : ''} the do-nothing persistence benchmark at `
      + `every horizon tested (${hs.map((h) => h + 'y').join(', ')}).`;
    if (partial.length) {
      verdict += ` ${phrase(partial)} beat${partial.length === 1 ? 's' : ''} it at only `
        + partial.map((v) => `${beats[v].length} of ${hs.length}`).join(' and ') + '.';
    }
    if (never.length) {
      verdict += ` ${phrase(never)} never beat${never.length === 1 ? 's' : ''} it, so on this evidence `
        + `${never.length === 1 ? 'it is' : 'they are'} not earning ${never.length === 1 ? 'its' : 'their'} complexity.`;
    }
  } else {
    verdict = `<b>No variant beats the do-nothing persistence benchmark at every horizon.</b> `
      + `On this evidence, carrying the last reported intensity forward unchanged is competitive with the model.`;
  }

  // bias direction, longest horizon
  const hLast = hs[hs.length - 1];
  const highs = ids.filter((v) => d.horizons[hLast][v] && d.horizons[hLast][v].median_signed > 0);
  const biasSentence = highs.length
    ? `At the ${hLast}-year horizon ${phrase(highs)} ${highs.length === 1 ? 'reads' : 'read'} <b>high</b> `
      + `(${highs.map((v) => signedPct(d.horizons[hLast][v].median_signed * 100)).join(', ')}), which means `
      + `${highs.length === 1 ? 'it overstates' : 'they overstate'} emissions and therefore `
      + `<b>understate${highs.length === 1 ? 's' : ''} decarbonisation</b>. `
    : `At the ${hLast}-year horizon no variant reads high. `;
  const bLast = benchAt(hLast);
  const benchBias = bLast
    ? `Persistence reads high by ${signedPct(bLast.median_signed * 100)} at the same horizon — carrying the last `
      + `reported intensity forward misses the downward trend in the data.`
    : '';

  document.getElementById('evidence-finding').innerHTML = `<div class="finding" data-testid="evidence-finding-block">
    <h3>Does the modelling earn its keep, and which way does it err</h3>
    <p>${verdict}</p>
    <p style="margin-top:8px">${biasSentence}${benchBias}</p>
    <div class="share">
      ${ids.map((v) => {
        const s = d.horizons[hLast][v];
        if (!s) return '';
        const b = benchAt(hLast);
        const wins = beats[v].length;
        return `<div data-testid="evidence-stat-${esc(v)}">
          <span>${esc(labelOf(v))}</span>
          <b style="color:${VARIANT_COLOUR[v]}">${pct(s.median_abs * 100)}</b>
          <em>median abs. error at ${hLast}y${b ? ` · persistence ${pct(b.median_abs * 100)}` : ''}<br>
            beats persistence at ${wins} of ${hs.length} horizons · bias ${signedPct(s.median_signed * 100)}</em>
        </div>`;
      }).join('')}
    </div>
  </div>`;
}

/* ------------------------------------------------------------------ table */
function drawTable(d) {
  const hs = horizonsOf(d);
  const variantIds = meta.variants.map((v) => v.id);
  const labelOf = (id) => (meta.variants.find((v) => v.id === id) || { label: id }).label;

  const head = `<thead><tr>
    <th scope="col">Model</th><th scope="col">Horizon</th><th scope="col">n</th>
    <th scope="col">Median abs. error</th><th scope="col">p90 abs. error</th>
    <th scope="col">Share of errors &gt; 50%</th><th scope="col">Median signed bias</th>
  </tr></thead>`;

  const rows = [];
  hs.forEach((h) => {
    const cell = d.horizons[h] || {};
    const bench = (d.benchmarks && d.benchmarks[h] && d.benchmarks[h].persistence) || null;
    const candidates = variantIds.map((v) => cell[v]).filter(Boolean).map((s) => s.median_abs);
    if (bench) candidates.push(bench.median_abs);
    const best = candidates.length ? Math.min(...candidates) : null;

    variantIds.forEach((v) => {
      const s = cell[v];
      if (!s) return;
      rows.push(`<tr data-testid="backtest-row-${esc(v)}-${esc(h)}">
        <th scope="row"><span class="swatch" style="display:inline-block;width:10px;height:10px;background:${VARIANT_COLOUR[v]};margin-right:6px"></span>${esc(labelOf(v))}</th>
        <td class="num">${h}y</td><td class="num">${int(s.n)}</td>
        <td class="num ${s.median_abs === best ? 'best' : ''}">${pct(s.median_abs * 100)}</td>
        <td class="num">${pct(s.p90_abs * 100)}</td>
        <td class="num">${pct(s.share_over_50 * 100)}</td>
        <td class="num" style="color:${s.median_signed > 0 ? PALETTE.negative : PALETTE.navy}">${signedPct(s.median_signed * 100)}</td>
      </tr>`);
    });
    if (bench) {
      rows.push(`<tr class="row-benchmark" data-testid="backtest-row-persistence-${esc(h)}">
        <th scope="row">Persistence benchmark (do nothing)</th>
        <td class="num">${h}y</td><td class="num">${int(bench.n)}</td>
        <td class="num ${bench.median_abs === best ? 'best' : ''}">${pct(bench.median_abs * 100)}</td>
        <td class="num">${pct(bench.p90_abs * 100)}</td>
        <td class="num">${pct(bench.share_over_50 * 100)}</td>
        <td class="num">${signedPct(bench.median_signed * 100)}</td>
      </tr>`);
    }
  });

  document.getElementById('evidence-table').innerHTML =
    `<caption>Out-of-sample errors as a percentage of the realised value. Lowest median absolute error in each horizon is highlighted. A variant that does not beat persistence is not earning its complexity.</caption>`
    + head + `<tbody>${rows.join('')}</tbody>`;
}

/* ------------------------------------------------------- median abs error */
function drawErrorChart(d) {
  const hs = horizonsOf(d);
  const variantIds = meta.variants.map((v) => v.id);
  const labelOf = (id) => (meta.variants.find((v) => v.id === id) || { label: id }).label;

  const datasets = variantIds.map((v) => ({
    label: labelOf(v),
    data: hs.map((h) => (d.horizons[h][v] ? d.horizons[h][v].median_abs * 100 : null)),
    backgroundColor: VARIANT_COLOUR[v],
    borderColor: '#FFFFFF', borderWidth: 1, borderSkipped: false,
    categoryPercentage: 0.72, barPercentage: 0.9,
  }));
  datasets.push({
    label: 'Persistence benchmark',
    data: hs.map((h) => {
      const b = d.benchmarks && d.benchmarks[h] && d.benchmarks[h].persistence;
      return b ? b.median_abs * 100 : null;
    }),
    backgroundColor: 'transparent',
    borderColor: PALETTE.navy, borderWidth: 1.5,
    borderSkipped: false, categoryPercentage: 0.72, barPercentage: 0.9,
  });

  const opts = baseOptions({
    yTitle: 'Median absolute error, % of realised value',
    xTitle: 'Forecast horizon',
    tickFormatter: (v) => `${num(v, 0)}%`,
    beginAtZero: true,
  });
  opts.plugins.tooltip.callbacks = { label: (i) => `${i.dataset.label}: ${pct(i.parsed.y)}` };
  opts.plugins.modelledRegion = { startIndex: null };
  opts.scales.x.ticks.color = PALETTE.body;
  opts.scales.x.ticks.font = { size: 11 };

  render(ERR, {
    type: 'bar',
    data: { labels: hs.map((h) => `${h} year${h === '1' ? '' : 's'} ahead`), datasets },
    options: opts,
  });

  document.getElementById('evidence-legend').innerHTML = meta.variants.map((v) =>
    `<span class="li"><span class="bx" style="background:${VARIANT_COLOUR[v.id]}"></span>${esc(v.label)}</span>`).join('')
    + `<span class="li"><span class="bx" style="background:#fff;border:1.5px solid ${PALETTE.navy}"></span>Persistence benchmark</span>`;
}

/* ------------------------------------------------------------ signed bias */
function drawBiasChart(d) {
  const hs = horizonsOf(d);
  const variantIds = meta.variants.map((v) => v.id);
  const labelOf = (id) => (meta.variants.find((v) => v.id === id) || { label: id }).label;

  const datasets = variantIds.map((v) => {
    const vals = hs.map((h) => (d.horizons[h][v] ? d.horizons[h][v].median_signed * 100 : null));
    return {
      label: labelOf(v),
      data: vals,
      backgroundColor: vals.map((x) => (x !== null && x > 0 ? PALETTE.orange : PALETTE.navy)),
      borderColor: '#FFFFFF', borderWidth: 1, borderSkipped: false,
      categoryPercentage: 0.72, barPercentage: 0.9,
    };
  });

  const opts = baseOptions({
    yTitle: 'Median signed bias, % of realised value',
    xTitle: 'Forecast horizon',
    tickFormatter: (v) => `${signedPct(v, 0)}`,
  });
  opts.plugins.tooltip.callbacks = {
    label: (i) => `${i.dataset.label}: ${signedPct(i.parsed.y)} — ${
      i.parsed.y > 0 ? 'reads high, understates decarbonisation' : 'reads low, overstates decarbonisation'}`,
  };
  opts.plugins.modelledRegion = { startIndex: null };
  opts.plugins.zeroLine = { enabled: true };
  opts.scales.x.ticks.color = PALETTE.body;
  opts.scales.x.ticks.font = { size: 11 };
  // room beneath the axis line so per-bar variant names cannot collide with
  // the horizon labels
  opts.scales.x.ticks.padding = 26;

  const barLabels = {
    id: 'biasLabels',
    afterDatasetsDraw(chart) {
      const { ctx } = chart;
      ctx.save();
      ctx.font = '700 10px Calibri, "Segoe UI", system-ui, sans-serif';
      ctx.textAlign = 'center';
      chart.data.datasets.forEach((ds, di) => {
        const m = chart.getDatasetMeta(di);
        m.data.forEach((el, i) => {
          const v = ds.data[i];
          if (v === null || v === undefined) return;
          ctx.fillStyle = v > 0 ? PALETTE.negative : PALETTE.navy;
          ctx.textBaseline = v > 0 ? 'bottom' : 'top';
          ctx.font = '700 10px Calibri, "Segoe UI", system-ui, sans-serif';
          ctx.fillText(signedPct(v), el.x, v > 0 ? el.y - 3 : el.y + 3);
          // which variant this bar is: written inside the bar, so colour can stay
          // reserved for the direction of the bias
          ctx.font = '700 9px Calibri, "Segoe UI", system-ui, sans-serif';
          const barLen = Math.abs(el.base - el.y);
          if (barLen > ctx.measureText(ds.label).width + 12) {
            ctx.save();
            ctx.translate(el.x, el.base + (v > 0 ? -5 : 5));
            ctx.rotate(-Math.PI / 2);
            ctx.fillStyle = '#FFFFFF';
            ctx.textAlign = v > 0 ? 'left' : 'right';
            ctx.textBaseline = 'middle';
            ctx.fillText(ds.label, 0, 0);
            ctx.restore();
          } else {
            // bar too short to hold the label: put it outside, beyond the value
            ctx.fillStyle = '#666666';
            ctx.textAlign = 'center';
            ctx.textBaseline = v > 0 ? 'bottom' : 'top';
            // beyond the value label, clear of the bar; the x axis carries extra
            // tick padding so this cannot collide with the horizon labels
            ctx.fillText(ds.label, el.x, v > 0 ? el.y - 17 : el.y + 17);
          }
          ctx.textAlign = 'center';
        });
      });
      ctx.restore();
    },
  };

  render(BIAS, {
    type: 'bar',
    data: { labels: hs.map((h) => `${h} year${h === '1' ? '' : 's'} ahead`), datasets },
    options: opts,
    plugins: [barLabels],
  });

  const host = document.getElementById('bias-chart').closest('.panel').querySelector('.panel-head');
  if (!host.querySelector('.chart-legend')) {
    const legend = document.createElement('div');
    legend.className = 'chart-legend';
    legend.innerHTML =
      `<span class="li"><span class="bx" style="background:${PALETTE.orange}"></span>Reads high — understates decarbonisation</span>`
      + `<span class="li"><span class="bx" style="background:${PALETTE.navy}"></span>Reads low — overstates decarbonisation</span>`;
    host.appendChild(legend);
  }
}
