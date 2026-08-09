// Shared state markup: skeletons, empty states, errors, pending artefacts.
import { esc } from './fmt.js';

export function skeleton(rows = 3, block = true) {
  const lines = ['w40', 'w90', 'w70'].slice(0, rows)
    .map((w) => `<div class="sk-line ${w} sk-pulse"></div>`).join('');
  return `<div class="skeleton" aria-busy="true" aria-live="polite">
    ${lines}${block ? '<div class="sk-block sk-pulse"></div>' : ''}
    <span class="sr-only">Loading</span>
  </div>`;
}

export function empty(title, detail) {
  return `<div class="empty"><b>${esc(title)}</b>${esc(detail || '')}</div>`;
}

export function errorStrip(err, what) {
  const status = err && err.status ? ` (HTTP ${err.status})` : '';
  return `<div class="strip error" role="alert" data-testid="error-state">
    <b>Could not load ${esc(what)}${status}.</b> ${esc(err && err.detail ? err.detail : String(err))}
  </div>`;
}

/** 503 artefact-not-yet-built state, with a retry control. */
export function pending(title, detail, retryId) {
  return `<div class="pending" role="status" data-testid="pending-state">
    <h3>${esc(title)}</h3>
    <p>${esc(detail)}</p>
    <p>The server has not finished writing this artefact. Nothing is being hidden — there is simply
       no result to show yet. Re-check in a few minutes.</p>
    <button class="retry" type="button" id="${esc(retryId)}" data-testid="button-retry">Re-check now</button>
  </div>`;
}

/** Basis tag. kind: 'reported' | 'mixed' | anything else = modelled. */
export function tag(kind) {
  if (kind === 'reported') {
    return '<span class="tag tag-reported" title="Every underlying value is disclosed carbon data">Reported</span>';
  }
  if (kind === 'mixed') {
    return '<span class="tag tag-mixed" title="Some holdings in this period have modelled carbon data">Part modelled</span>';
  }
  return '<span class="tag tag-modelled" title="No reported carbon data — model output">Modelled</span>';
}
