// Application shell: metadata, routing, and the four views.
import { api } from './api.js';
import { int, esc } from './fmt.js';
import { errorStrip } from './ui.js';
import { initCompany, loadCompany, companyState } from './view-company.js';
import { initPortfolio, loadPortfolioList } from './view-portfolio.js';
import { initEvidence, loadEvidence } from './view-evidence.js';

const VIEWS = {
  company: {
    title: 'Company',
    sub: 'Attributed emissions for one company, with the model variants compared side by side.',
  },
  portfolio: {
    title: 'Portfolio',
    sub: 'Attributed emissions for a book of holdings, decomposed into emissions, valuation and allocation effects.',
  },
  evidence: {
    title: 'Model evidence',
    sub: 'Out-of-sample backtest error and bias by horizon, against a do-nothing benchmark.',
  },
  method: {
    title: 'Method and limitations',
    sub: 'What is measured, what is modelled, and what the numbers cannot tell you.',
  },
};

let meta = null;

async function boot() {
  try {
    meta = await api.meta();
  } catch (err) {
    document.getElementById('main').insertAdjacentHTML('afterbegin', errorStrip(err, 'dataset metadata'));
    return;
  }

  document.getElementById('sidebar-disclosure').textContent = meta.disclosure;
  document.getElementById('topbar-meta').innerHTML = `
    <span>Universe<b data-testid="meta-companies">${int(meta.companies)}</b></span>
    <span>Reported carbon<b data-testid="meta-carbon-years">${meta.carbon_years.first}\u2013${meta.carbon_years.last}</b></span>
    <span>Modelled<b data-testid="meta-modelled-years">${meta.nowcast_from} onward</b></span>
    <span>Revenue &amp; EV<b>${meta.sales_years.first}\u2013${meta.sales_years.last}</b></span>`;

  initCompany(meta);
  initPortfolio(meta);
  initEvidence(meta);
  renderMethod(meta);

  window.addEventListener('hashchange', route);
  route();
}

function route() {
  const name = (location.hash.replace('#/', '') || 'company').split('?')[0];
  const view = VIEWS[name] ? name : 'company';

  Object.keys(VIEWS).forEach((k) => {
    document.getElementById(`view-${k}`).hidden = (k !== view);
  });
  document.querySelectorAll('#nav a').forEach((a) => {
    if (a.dataset.view === view) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  });
  document.getElementById('view-title').textContent = VIEWS[view].title;
  document.getElementById('view-sub').textContent = VIEWS[view].sub;
  document.title = `${VIEWS[view].title} — Carbon Attribution`;

  if (view === 'portfolio') loadPortfolioList();
  if (view === 'evidence') loadEvidence();
  if (view === 'company' && companyState.company && !companyState.data) loadCompany();
}

/* ----------------------------------------------------------------- method */
function renderMethod(m) {
  document.getElementById('method-disclosure').innerHTML = `
    <h2>Data basis</h2>
    <p data-testid="disclosure-text">${esc(m.disclosure)}</p>`;

  document.getElementById('method-body').innerHTML = `
    <h2>What is reported and what is modelled</h2>
    <p>Company carbon disclosures in this dataset run from ${m.carbon_years.first} to
      <b>${m.carbon_years.last}</b>. Revenue and enterprise value run to ${m.sales_years.last}.
      Every year from <b>${m.nowcast_from}</b> onward is model output. Throughout the dashboard a solid line and a
      “Reported” tag mean disclosed carbon data; a dashed line, a shaded region and a “Modelled” tag mean the number
      was produced by the estimator. No headline figure is shown without stating which basis it rests on and over what
      horizon.</p>

    <h2>Five limitations that matter</h2>
    <h3>1. The monthly series is interpolated</h3>
    <p>Carbon disclosures are annual. The monthly path is an interpolation between annual points and carries
      <b>no information beyond those points</b>. Month-to-month movement is an artefact of the interpolation, not a
      measurement. Read levels and multi-year direction; do not read monthly turning points.</p>

    <h3>2. The bands are approximately 50% intervals</h3>
    <p>The shaded band on the company chart is roughly a 50% interval. Approximately half of realised outcomes would be
      expected to fall <b>outside</b> it. It is not a worst case and should not be read as one. The realised error
      distribution is on the Model evidence view; the p90 column there is the honest tail.</p>

    <h3>3. Attribution uses an enterprise-value denominator</h3>
    <p>Attributed emissions are <code>invested amount × company emissions ÷ enterprise value</code>. The denominator is
      a market quantity, so attributed emissions fall when enterprise values rise even if the companies emit exactly the
      same amount. This is why the portfolio view decomposes the change: only the emissions effect is decarbonisation.
      A market rally alone can produce an apparently falling carbon footprint.</p>

    <h3>4. Every year after ${m.carbon_years.last} is a forecast, and forecasts are biased</h3>
    <p>The variants differ in how they extrapolate. Their measured out-of-sample errors and their <b>signed</b> bias by
      horizon are on the Model evidence view, alongside a persistence benchmark — carrying the last reported intensity
      forward unchanged. A variant that does not beat persistence is not earning its complexity. A positive bias means
      the model reads high, which understates decarbonisation.</p>

    <h3>5. Coverage is incomplete and changes over time</h3>
    <p>Holdings with no carbon data are excluded from the attributed total rather than estimated at zero. The portfolio
      view states how many holdings are excluded in each period. Because coverage changes between periods, part of any
      change in the total can come from the composition of the covered set rather than from emissions.</p>

    <h2>Model variants</h2>
    ${m.variants.map((v) => `
      <h3>${esc(v.label)} — ${esc(v.short)}</h3>
      <p>${esc(v.description)}</p>
      <p><b>Caveat.</b> ${esc(v.caveat)}</p>`).join('')}

    <h2>How to read a figure on this dashboard</h2>
    <ul>
      <li>Check the basis tag: <b>Reported</b> or <b>Modelled</b>.</li>
      <li>Check the horizon printed beneath every headline number — a reduction is meaningless without its start and end year.</li>
      <li>For portfolio changes, look at the emissions effect before the total.</li>
      <li>For anything past ${m.carbon_years.last}, read the bias row for the matching horizon on the Model evidence view before quoting the number.</li>
    </ul>
    <p class="caption">Marketing material for professional clients only. Figures are model output on a research dataset,
      not a regulatory disclosure.</p>`;
}

boot();
