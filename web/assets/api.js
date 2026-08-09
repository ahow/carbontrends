// Thin fetch layer. Errors are surfaced, never swallowed.
export class ApiError extends Error {
  constructor(status, detail, url) {
    super(detail || `Request failed (${status})`);
    this.status = status;
    this.detail = detail;
    this.url = url;
  }
}

async function get(path) {
  let res;
  try {
    res = await fetch(path, { headers: { Accept: 'application/json' } });
  } catch (e) {
    throw new ApiError(0, `Network error contacting the API (${e.message})`, path);
  }
  let payload = null;
  const text = await res.text();
  if (text) {
    try { payload = JSON.parse(text); } catch { payload = null; }
  }
  if (!res.ok) {
    const detail = payload && payload.detail ? payload.detail : `HTTP ${res.status}`;
    throw new ApiError(res.status, detail, path);
  }
  return payload;
}

export const api = {
  meta: () => get('/api/meta'),
  companies: (q, limit = 25) => get(`/api/companies?q=${encodeURIComponent(q)}&limit=${limit}`),
  company: (name, variants, investment) =>
    get(`/api/company/${encodeURIComponent(name)}?variants=${variants.join(',')}&investment=${investment}`),
  portfolios: () => get('/api/portfolios'),
  portfolio: (name, variant) =>
    get(`/api/portfolio/${encodeURIComponent(name)}?variant=${encodeURIComponent(variant)}`),
  backtest: () => get('/api/backtest'),
};
