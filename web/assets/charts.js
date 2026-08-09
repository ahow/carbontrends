// Chart.js v4 configuration. Think-cell house style, enforced centrally so no
// individual chart can drift off-brand.
import { PALETTE, compact } from './fmt.js';

const Chart = window.Chart;
const FONT = "Calibri, 'Segoe UI', system-ui, -apple-system, sans-serif";

Chart.defaults.font.family = FONT;
Chart.defaults.color = PALETTE.body;
Chart.defaults.animation = false;
Chart.defaults.maintainAspectRatio = false;

/* --------------------------------------------------------------------------
 * Modelled-region plugin: shades every x position from `startIndex` onward and
 * labels it. This is the primary defence against reading a modelled tail as
 * data, so it is drawn under the series but above the grid, on every chart.
 * ------------------------------------------------------------------------ */
export const modelledRegion = {
  id: 'modelledRegion',
  beforeDatasetsDraw(chart, _args, opts) {
    const cfg = opts || {};
    if (cfg.startIndex === null || cfg.startIndex === undefined) return;
    const { ctx, chartArea: area, scales } = chart;
    const x = scales.x;
    if (!x) return;
    const half = (x.width / Math.max(x.ticks.length, 1)) / 2;
    let left = x.getPixelForValue(cfg.startIndex);
    if (cfg.band !== false) left -= (x.getPixelForValue(1) - x.getPixelForValue(0)) / 2 || half;
    left = Math.max(left, area.left);
    if (left >= area.right) return;

    ctx.save();
    ctx.fillStyle = 'rgba(0,42,92,0.05)';
    ctx.fillRect(left, area.top, area.right - left, area.bottom - area.top);
    ctx.strokeStyle = 'rgba(0,42,92,0.45)';
    ctx.setLineDash([4, 3]);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(left, area.top);
    ctx.lineTo(left, area.bottom);
    ctx.stroke();
    ctx.setLineDash([]);

    if (cfg.label) {
      ctx.font = '700 11px ' + FONT;
      ctx.fillStyle = PALETTE.navy;
      ctx.textBaseline = 'top';
      const w = ctx.measureText(cfg.label).width;
      const pad = 5;
      let tx = left + 7;
      if (tx + w + pad > area.right) tx = Math.max(area.left + 4, area.right - w - pad);
      ctx.fillStyle = 'rgba(255,255,255,0.88)';
      ctx.fillRect(tx - 3, area.top + 3, w + 6, 16);
      ctx.fillStyle = PALETTE.navy;
      ctx.fillText(cfg.label, tx, area.top + 5);
    }
    ctx.restore();
  },
};

/** Emphasised zero line, Prussian Navy (used by the bias chart). */
export const zeroLine = {
  id: 'zeroLine',
  afterDatasetsDraw(chart, _a, opts) {
    if (!opts || opts.enabled === false) return;
    const y = chart.scales.y;
    if (!y) return;
    const py = y.getPixelForValue(0);
    const { ctx, chartArea: area } = chart;
    ctx.save();
    ctx.strokeStyle = PALETTE.navy;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(area.left, py);
    ctx.lineTo(area.right, py);
    ctx.stroke();
    ctx.restore();
  },
};

Chart.register(modelledRegion, zeroLine);

/** Shared scale/plugin scaffolding: y gridlines only, dashed, #E0E0E0. */
export function baseOptions({ yTitle, xTitle, tickFormatter = compact, beginAtZero = false } = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    layout: { padding: { top: 6, right: 10, bottom: 0, left: 0 } },
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#FFFFFF',
        borderColor: PALETTE.border,
        borderWidth: 1,
        titleColor: PALETTE.navy,
        bodyColor: PALETTE.body,
        titleFont: { size: 12, weight: '700' },
        bodyFont: { size: 12 },
        padding: 9,
        displayColors: true,
        boxWidth: 9,
        boxHeight: 9,
        cornerRadius: 0,
      },
    },
    scales: {
      x: {
        grid: { display: false, drawBorder: true },
        border: { color: PALETTE.border },
        title: xTitle ? { display: true, text: xTitle, color: PALETTE.muted, font: { size: 10 } } : { display: false },
        ticks: { color: PALETTE.faint, font: { size: 9 }, maxRotation: 0, autoSkip: false },
      },
      y: {
        beginAtZero,
        grid: { color: PALETTE.grid, borderDash: [4, 4], drawTicks: false, drawBorder: false },
        border: { display: false },
        title: yTitle ? { display: true, text: yTitle, color: PALETTE.muted, font: { size: 10 } } : { display: false },
        ticks: { color: PALETTE.faint, font: { size: 9 }, callback: (v) => tickFormatter(v) },
      },
    },
  };
}

const registry = new Map();

/** Create or replace a chart on a canvas id. */
export function render(canvasId, config) {
  const el = document.getElementById(canvasId);
  if (!el) return null;
  const existing = registry.get(canvasId);
  if (existing) existing.destroy();
  const chart = new Chart(el, config);
  registry.set(canvasId, chart);
  return chart;
}

export function destroy(canvasId) {
  const existing = registry.get(canvasId);
  if (existing) { existing.destroy(); registry.delete(canvasId); }
}
