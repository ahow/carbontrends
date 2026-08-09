# Dashboard front-end spec

Build a **static** front end in `/home/user/workspace/carbontrends/web/`.
No build step, no npm, no bundler. Plain `index.html` + `assets/app.js` +
`assets/styles.css` (+ any extra JS modules under `assets/`). It is served by
FastAPI from `api/main.py`, which mounts `web/assets` at `/assets` and returns
`web/index.html` at `/`.

Charts: **Chart.js v4 from CDN** (`https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js`).
Do not use Plotly. Do not use React or any framework. Vanilla ES modules only.

---

## Brand — Schroders. These are mandatory, not suggestions.

```
Prussian Navy   #002A5C   headings, primary text, chart series 2
Deep Cerulean   #00A3D7   accents, links, chart series 1
Matt Gold       #B09A6A   chart series 3
Deep Orange     #FF6B57   alerts / negative emphasis
Teal            #008080   chart series 5
Body text       #333333
Muted text      #666666
Faint text      #999999
Gridlines       #E0E0E0
Borders         #D4D1CA
Background      #FFFFFF
Positive        #00805E   Caution #E8A317   Negative #C0392B   N/A #999999
```

Typography: Calibri, then system sans fallback
(`font-family: Calibri, 'Segoe UI', system-ui, -apple-system, sans-serif`).

Chart style (think-cell inspired, strictly enforced):
- White background, no chart area fill, no chart border
- Gridlines: y-axis only, `#E0E0E0`, dashed, no x gridlines
- Lines 2px solid. Markers optional, small circles
- **Two to three colours maximum per chart.** Colour carries meaning only
- Direct labelling preferred over legends where it fits
- Axis labels 10px `#666666`, ticks 9px `#999999`, titles 14px Prussian Navy bold

Tables: Prussian Navy header with white bold text, alternating `#F2F2F2`/white
rows, thin horizontal rules only, no vertical lines, numbers right-aligned.

Layout: left sidebar navigation (Prussian Navy), white content area, generous
whitespace, max content width ~1400px. Desktop-first but must not break at
1024px. This is an institutional analytical tool — sober and precise, not
playful. No emoji. No gradients. No drop shadows beyond a hairline.

---

## API contract

All endpoints are same-origin under `/api`. Use `fetch`.

### `GET /api/meta`
```json
{ "variants": [ { "id":"legacy","label":"Legacy","short":"...","description":"...","caveat":"..." }, ... ],
  "default_variant": "current",
  "companies": 7982,
  "carbon_years": {"first":2008,"last":2023},
  "sales_years": {"first":2007,"last":2025},
  "nowcast_from": 2024,
  "disclosure": "Carbon data ends 2023. ..." }
```

### `GET /api/companies?q=<text>&limit=50`
`[{ "isin","name","sector","country" }]`

### `GET /api/company/<name>?variants=legacy,current,drift&investment=1000000`
```json
{ "company":"...", "investment":1000000,
  "series": { "current": {
      "monthly":[{"date":"2024-01-01","year":2024,"value":123.4,"lower":..,"upper":..,"quality":"estimated"}],
      "annual":[{"year":2024,"value":1481.2,"quality":"estimated","ev":1.2e10}],
      "meta": { variant object } } },
  "headline": { "current": { "full": -34.2, "reported_only": -28.9,
                             "reported_last_year": 2023, "final_year": 2026 } } }
```
`quality` is `"reported"` or `"estimated"`.

### `GET /api/portfolios`
`[{ "name","periods","holdings","start","end" }]`

### `GET /api/portfolio/<name>?variant=current`
```json
{ "name","variant","meta":{...},
  "series":[{"date":"2020-07-01","value":1234.5,"holdings":78,"covered":74,"uncovered":4,"quality":"reported"}],
  "decomposition":[{"from":"2020-07-01","to":"2020-10-01","emissions":-12.3,"valuation":+4.5,"allocation":-1.1,"total":-8.9}],
  "cumulative":{"emissions":-120.0,"valuation":+45.0,"allocation":-11.0,"total":-86.0},
  "headline":{"start":..,"end":..,"pct_change":-31.2,"start_date":"..","end_date":".."} }
```

### `GET /api/backtest`
```json
{ "generated_at":"...","n_companies":7134,
  "horizons": { "1": { "legacy": {"n":..,"median_abs":0.162,"p90_abs":0.715,
                                  "share_over_50":0.21,"median_signed":0.058,
                                  "q80":..,"q90":..,"q95":..},
                       "current": {...}, "drift": {...} } },
  "benchmarks": { "1": { "persistence": {...} } },
  "notes": {"horizon":"...","bias":"..."} }
```
Note: all error/bias values are **fractions**, not percentages. Multiply by 100.

---

## Views — four, in a left sidebar

### 1. Company
- Search box hitting `/api/companies?q=`. Debounce 250ms. Show sector + country.
- Investment amount input, default 1,000,000, formatted with thousands separators.
- **Model A/B comparison is the centrepiece.** Checkboxes for the three
  variants; all selected variants draw on one chart, one colour each
  (current = Deep Cerulean, legacy = `#999999`, drift = Matt Gold).
- Main chart: monthly attributed emissions, x = date, y = tCO2e per the chosen
  investment.
  - **Reported vs estimated must be unmistakable.** Draw the reported span as a
    solid line and everything from `meta.nowcast_from` onward as a dashed line
    of the same colour, plus a shaded vertical band over the nowcast region
    (`rgba(0,42,92,0.05)`) with a label reading e.g. "Modelled — no reported
    carbon data after 2023". A user must never mistake the 2026 tail for data.
  - Confidence band: shade between `lower` and `upper` for the selected
    variant at 12% opacity. Label it honestly as roughly a 50% interval — the
    caption must say so.
- Headline cards, side by side, for each selected variant:
  - "Reduction, reported data only (first reported year → last reported year)"
  - "Reduction including modelled years (→ final year)"
  These two numbers must be equally prominent. Do not lead with the modelled one.
- Variant descriptions and `caveat` rendered beneath the chart in small muted
  text, so the caveat travels with the number.

### 2. Portfolio
- Portfolio picker from `/api/portfolios`, variant selector.
- Line chart of attributed emissions over the quarterly series.
- **Decomposition is the analytical point of this view.** A waterfall (build it
  with a Chart.js floating bar chart — `data: [[start, end], ...]`) showing
  Start → emissions effect → valuation effect → allocation effect → End, using
  `cumulative`. Colour: emissions effect Deep Cerulean, valuation effect Matt
  Gold, allocation effect Teal, start/end bars Prussian Navy.
- Caption stating plainly: only the emissions effect is decarbonisation; the
  valuation effect is the portfolio's enterprise values moving, which a market
  rally alone can produce.
- Per-period decomposition table beneath.
- Coverage warning strip when any period has `uncovered > 0`, e.g.
  "4 of 78 holdings have no carbon data in 2024 and are excluded."

### 3. Model evidence
- Table of median absolute error, p90 and median signed bias by horizon and
  variant from `/api/backtest`, with the persistence benchmark as a distinct
  row so it is obvious whether the model beats doing nothing.
- Grouped bar chart of median error by horizon, one series per variant plus
  persistence.
- Separate bar chart of **median signed bias** by horizon. Zero line emphasised
  in Prussian Navy. Positive bars in Deep Orange labelled "reads high —
  understates decarbonisation".
- Show `generated_at` and `n_companies` so a stale artefact is visible.

### 4. Method
- Render the disclosure from `/api/meta` prominently at the top.
- Short honest plain-English notes covering: the monthly series is interpolated
  and carries no information beyond the annual points; the confidence bands are
  approximately 50% intervals; attribution uses an enterprise-value denominator
  so valuation changes affect the result; and every year after the last carbon
  year is modelled.

---

## Non-negotiables

1. Never present a modelled figure with the same visual weight as a reported one.
2. Every headline number must carry its horizon and its data basis.
3. Loading skeletons for every async panel; a clear empty state; a visible error
   state if a fetch fails (do not fail silently).
4. Number formatting: thousands separators, 1 decimal for tCO2e, 1 decimal for
   percentages, always signed for changes (`+`/`−`, using a real minus sign).
5. Accessible: semantic HTML, labelled form controls, WCAG AA contrast,
   keyboard-navigable.
6. Add `data-testid` attributes to interactive and data-bearing elements.
