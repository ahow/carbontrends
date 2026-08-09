// Number / text formatting. One place, so every view formats identically.
export const MINUS = '\u2212';           // real minus sign, not a hyphen
export const PALETTE = {
  navy: '#002A5C',
  cerulean: '#00A3D7',
  gold: '#B09A6A',
  orange: '#FF6B57',
  teal: '#008080',
  body: '#333333',
  muted: '#666666',
  faint: '#999999',
  grid: '#E0E0E0',
  border: '#D4D1CA',
  positive: '#00805E',
  caution: '#E8A317',
  negative: '#C0392B',
};

// current = Deep Cerulean, legacy = #999999, drift = Matt Gold  (spec)
export const VARIANT_COLOUR = {
  current: PALETTE.cerulean,
  legacy: PALETTE.faint,
  drift: PALETTE.gold,
};

const groups = (s) => s.replace(/\B(?=(\d{3})+(?!\d))/g, ',');

function fixed(v, dp) {
  const s = Math.abs(v).toFixed(dp);
  const [i, d] = s.split('.');
  return groups(i) + (d ? '.' + d : '');
}

/** Thousands-separated, fixed decimals, real minus sign. */
export function num(v, dp = 1) {
  if (v === null || v === undefined || Number.isNaN(v)) return 'n/a';
  return (v < 0 ? MINUS : '') + fixed(v, dp);
}

/** Always-signed number. */
export function signedNum(v, dp = 1) {
  if (v === null || v === undefined || Number.isNaN(v)) return 'n/a';
  if (Math.abs(v) < 0.5 * Math.pow(10, -dp)) return fixed(0, dp);
  return (v < 0 ? MINUS : '+') + fixed(Math.abs(v), dp);
}

/** Always-signed percentage, 1 decimal. */
export function signedPct(v, dp = 1) {
  if (v === null || v === undefined || Number.isNaN(v)) return 'n/a';
  if (Math.abs(v) < 0.5 * Math.pow(10, -dp)) return fixed(0, dp) + '%';
  return (v < 0 ? MINUS : '+') + fixed(Math.abs(v), dp) + '%';
}

/** Unsigned percentage, for error magnitudes. */
export function pct(v, dp = 1) {
  if (v === null || v === undefined || Number.isNaN(v)) return 'n/a';
  return fixed(v, dp) + '%';
}

/** Integer with separators. */
export function int(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return 'n/a';
  return (v < 0 ? MINUS : '') + groups(String(Math.round(Math.abs(v))));
}

/** Compact axis ticks: 12.3k / 4.5m. */
export function compact(v) {
  const a = Math.abs(v);
  const sign = v < 0 ? MINUS : '';
  if (a >= 1e9) return sign + fixed(a / 1e9, 1) + 'bn';
  if (a >= 1e6) return sign + fixed(a / 1e6, 1) + 'm';
  if (a >= 1e4) return sign + fixed(a / 1e3, 0) + 'k';
  if (a >= 1e3) return sign + fixed(a / 1e3, 1) + 'k';
  return sign + fixed(a, a < 10 ? 1 : 0);
}

/** 2024-03-01 -> Mar 2024 */
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
export function monthLabel(iso) {
  const [y, m] = String(iso).split('-');
  return `${MON[Number(m) - 1]} ${y}`;
}
export function quarterLabel(iso) {
  const [y, m] = String(iso).split('-');
  return `Q${Math.floor((Number(m) - 1) / 3) + 1} ${y}`;
}
export function yearOf(iso) { return Number(String(iso).slice(0, 4)); }

export function parseAmount(text) {
  const n = Number(String(text).replace(/[^0-9.]/g, ''));
  return Number.isFinite(n) && n > 0 ? n : null;
}

export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

export function timestamp(iso) {
  if (!iso) return 'unknown';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toISOString().slice(0, 16).replace('T', ' ') + ' UTC';
}
