# Carbon attribution dashboard — front end build and QA report

Built to `/home/user/workspace/carbontrends/web/SPEC.md`. Plain HTML + CSS + vanilla ES
modules, no build step, no framework. Chart.js v4.4.1 from jsDelivr CDN as the only
third-party dependency. Schroders palette and Calibri-first stack per SPEC and the
`schroders-brand` skill.

## Files

```
web/index.html
web/assets/styles.css
web/assets/app.js            boot, meta, hash routing, Method view prose
web/assets/api.js            typed fetch wrapper, ApiError with status + detail
web/assets/fmt.js            number/label formatting, palette, variant colours
web/assets/charts.js         Chart.js defaults, modelledRegion + zeroLine plugins
web/assets/ui.js             skeleton / empty / error / pending states, basis tags
web/assets/view-company.js
web/assets/view-portfolio.js
web/assets/view-evidence.js
web/qa/*.png                 screenshots (FINAL-*.png is the last sweep)
```

## Environment notes (deviations from the brief)

- **The API was not running** when I started, contrary to the brief. I started it:
  `python3 -m uvicorn api.main:app --host 127.0.0.1 --port 8000`. It is still running.
  Use `127.0.0.1:8000`; `localhost` did not resolve reliably in this sandbox.
- **`precomputed/` was empty**, so `/api/portfolio` and `/api/backtest` both returned 503.
  I built both artefacts myself: `precompute_portfolio.py` (21s) and
  `precompute_backtest.py` (88s, horizons 1/2/3, 7,895 companies).
  Both views were therefore tested in **both** states — pending and populated.
- `/api/portfolios` exposes one portfolio, `PortfolioHoldings` (21 quarterly periods,
  81 holdings, 2020-07-01 → 2025-07-01). Nothing is hardcoded; the selector is populated
  from the endpoint.

## Second pass — both artefacts live (built out and re-tested)

The parent confirmed `/api/backtest` and `/api/portfolio` now return 200. Both views were
rebuilt against real data and re-screenshotted (`qa/V2-*-1440.png`, `qa/V3-*-1024.png`).

### Portfolio — new work

The point of the view is now stated, not implied. Verified values, `variant=current`:
start 14,192,918 → end 4,804,545 tCO₂e, headline **−66.1%**; emissions −300,343 (3.2% of
the move), valuation −5,506,827 (58.7%), allocation −3,581,203 (38.1%), total −9,388,373.

1. **A "what the headline number is, and is not" block sits above every other number**,
   directly under the coverage warning: "Attributed emissions fell −66.1%, but only 3.2%
   of that move is companies emitting less… Neither of those is a company emitting less."
   Four figures beneath it: headline change, *of that, decarbonisation* (3.2%), enterprise
   values (58.7%), reweighting (38.1%).
2. **Sign-aware wording.** On `variant=legacy` the emissions effect is +3,191,784 — the
   companies emitted *more* — while the headline still reads −48.6%. The block switches
   to: "Attributed emissions fell −48.6%, but the emissions of the underlying companies
   **rose** … On this variant, **none** of the headline is companies emitting less", and
   the decarbonisation figure reads **none** rather than a negative percentage. Verified
   live (`qa/finding-legacy.png`, `qa/effects-legacy-v2.png`).
3. **Mixed-sign shares are explained.** Under legacy the shares are −46.3% / +79.7% /
   +66.6%; a footnote states they are contributions to the *net* move and shows the
   arithmetic, so the >100% figures cannot look like an error.
4. **Waterfall carries the message in-chart.** Each effect bar is labelled with its value
   *and* "x% of the move", and the emissions bar is annotated "the only decarbonisation" —
   or "emissions ROSE" in red when the effect is positive.
5. **New panel: "the three effects on their own scale."** On the waterfall's 14m tCO₂e
   axis a 300k effect is a hairline and is easy to miss. The three effects replotted on
   their own axis make the relative size visible without altering a single value.
6. **New exhibit: "same book, three variants."** All three variants fetched for the same
   portfolio and tabulated — headline change, emissions effect, share of the move,
   valuation, allocation. The caption is generated from the data and fires only when the
   signs disagree: "The emissions effect changes sign between variants while every
   headline still reads as a fall. The direction of the only decarbonisation term is
   therefore a modelling choice on this book, not an observation." Legacy −48.6% /
   +3,191,784; Current −66.1% / −300,343 (3.2%); Drift −69.0% / −824,959 (8.4%). The
   valuation effect barely moves (−5.49m / −5.51m / −5.51m) because it rests on actual
   prices — which is itself the point.

### Model evidence — new work

Artefact: 7,895 companies, generated 2026-08-09 14:16 UTC, horizons 1–3.

1. **A verdict block computed from the artefact**, not asserted: "Drift-corrected beats
   the do-nothing persistence benchmark at every horizon tested (1y, 2y, 3y). Current
   beats it at only 1 of 3. Legacy never beats it, so on this evidence it is not earning
   its complexity." Cross-checked by hand: 1y drift 13.97% vs persistence 14.03% (pass),
   current 14.26% (fail), legacy 16.16% (fail); 2y drift 20.80% / current 21.81% pass vs
   22.41%; 3y drift 24.75% pass, current 28.83% and legacy 29.90% fail vs 28.53%.
2. **Bias direction is spelled out** in the same block: "At the 3-year horizon Legacy and
   Current read high (+15.1%, +12.5%), which means they overstate emissions and therefore
   understate decarbonisation. Persistence reads high by +14.6% at the same horizon."
3. **Three per-variant stats** at the longest horizon: median absolute error against the
   persistence figure, how many horizons it beats, and its bias.
4. Bias chart bars are now individually named (rotated inside long bars, printed outside
   short ones) so colour can stay reserved for the *direction* of the bias.

## Views verified

| View | 1440px | 1024px | Data checked |
|---|---|---|---|
| Company | `qa/V2-company-1440.png` | `qa/V3-company-1024.png` | 228 monthly points 2008-01…2026-12, 3 variants, annual table, live search, investment rescale |
| Portfolio | `qa/V2-portfolio-1440.png` | `qa/V3-portfolio-1024.png` | 21 periods, 3-way decomposition, waterfall sums to total, all three variants, coverage warning |
| Model evidence | `qa/V2-evidence-1440.png` | `qa/V2-evidence-1024.png` | 3 horizons × 3 variants + persistence benchmark, verdict block, both bar charts |
| Method | `qa/V2-method-1440.png` | `qa/V3-method-1024.png` | static prose, disclosure, five limitations, variant caveats |

Screenshots: `qa/FINAL-<view>-<width>.png`, plus `qa/portfolio-pending-1440.png` and
`qa/evidence-pending-1440.png` for the artefact-pending states, and
`qa/company-chart-final.png` / `qa/bias-fix2-*.png` for chart detail.

No horizontal overflow at either width (`scrollWidth == clientWidth` = 1440 and 1024).
No page errors or console errors other than the deliberate 503 fixture.

## What the screenshots showed, and what I fixed

1. **Sidebar did not extend the full page height** on long pages. Fixed with a sticky
   `.sidebar-inner` wrapper.
2. **Portfolio modelled band was misleading.** Period `quality` is not monotonic — it
   takes `reported`, `mixed`, `estimated`, and `mixed` periods occur *inside* the reported
   window (some holdings lack recent disclosure). Keying the shaded band on the first
   non-reported period therefore shaded reported history. Now the band is keyed on
   `year > 2023`, and the line carries three dash states per segment (solid = reported,
   dotted = part modelled, dashed = fully modelled) with a matching three-way tag
   (Reported / Part modelled / Modelled) on every number and table row.
3. **Company empty state** rendered an empty 400px canvas with a stray axis line. The
   chart is now hidden until a company is selected and replaced by an explicit
   "Nothing plotted yet" panel that states the solid/dashed convention up front.
4. **Overplotted variant lines.** Over the reported span the three variants are visually
   one line. Rather than leave the reader guessing whether that is agreement or a bug,
   the chart sub-line now measures it: "Over the reported span the variants differ by at
   most 1.2%, so they plot on top of one another; they diverge only where the data ends."
   The threshold is 2%; above it the sentence is suppressed.
5. **Bias chart bars were unidentifiable.** Colour there encodes *direction* of bias
   (Deep Orange = reads high, Navy = reads low), so it cannot also encode variant. Each
   bar now carries its variant name — rotated inside long bars, printed outside short
   ones, with extra x-axis tick padding so it cannot collide with the horizon labels.
6. **Evidence table overflowed at 1024px** (last column clipped). Added a narrow-width
   table type ramp; the table now fits without a horizontal scroller.
7. **Variant cards wrapped 2+1 at 1024px.** With a 240px sidebar the content column is
   752px, one pixel short of three 238px cards plus gaps. The narrow-width card minimum
   is now 216px; computed grid at 1024px is `236px 236px 236px`, verified in the browser.
8. **Signed zeros.** `+0` / `−0` appeared throughout the portfolio decomposition table
   (quarters inside a reported year have no emissions effect by construction). Formatter
   now returns an unsigned `0`.

## Reported vs modelled separation (the primary requirement)

Implemented at five levels, so no single failure hides it:

- **Data-basis disclosure** is fixed in the sidebar and repeated as a strip at the top of
  every view: "Carbon data ends 2023. Revenue and enterprise value run to 2025. Every
  year after 2023 is modelled, not reported."
- **Line style**: solid = reported, dashed = modelled, dotted = part modelled. Not colour,
  so it survives greyscale printing and colour-blind readers.
- **Shaded region** from 2024 onward with an in-chart label
  "Modelled — no reported carbon data after 2023" and a dashed boundary at the cut.
- **Every headline number carries a basis tag** (Reported / Part modelled / Modelled) and
  its horizon in years. The company view shows the reported-only reduction and the
  including-modelled reduction with equal visual weight, side by side — the modelled
  figure is never the only number on screen.
- **Every table row is tagged** by basis; the annual table caption states that
  "Modelled" rows contain no reported carbon data.

## Honesty features worth noting

- Confidence bands are labelled as **approximately 50% intervals** with the explicit
  warning that roughly half of realised outcomes fall outside them, so they are not a
  worst case; the p90 column on the evidence view is presented as the honest tail.
- The evidence table includes the **persistence benchmark** (carry the last reported
  intensity forward) as a distinct italic row, with the caption "a variant that does not
  beat persistence is not earning its complexity". On the current artefact, at a 1-year
  horizon persistence (14.0% median absolute error) is level with drift-corrected (14.0%)
  and beats legacy (16.2%) — the dashboard shows this rather than hiding it.
- The portfolio view states plainly that only the **emissions effect** is decarbonisation.
  On the current data the total change is −66.1% but the emissions effect is only
  −300,343 tCO₂e (3.2% of the change); valuation contributes 58.7% and allocation 38.1%.
- **Coverage warning**: "2 of 55 holdings have no carbon data in 2025 and are excluded
  from the attributed total. 21 of 21 periods are affected."
- The monthly path is repeatedly described as **interpolated between annual points**,
  carrying no information beyond them.
- Provenance strip on the evidence view prints the artefact `generated_at` and
  `n_companies`, and warns that an old timestamp means stale numbers.

## Not implemented / caveats

- **Both 503 states and the populated states were verified.** The pending state was seen
  live for `/api/backtest` before the artefact existed (`qa/evidence-pending-1440.png`) and
  for `/api/portfolio` via a Playwright route returning a real 503 (`qa/portfolio-pending-1440.png`);
  "Re-check now" then populated the view. Original note retained below.
- **503 handling was verified by fixture, not by a live race.** The pending state was
  observed live for `/api/backtest` before I built the artefact
  (`qa/evidence-pending-1440.png`), and for `/api/portfolio` via a Playwright route
  returning a real 503 body (`qa/portfolio-pending-1440.png`). The "Re-check now" button
  was then clicked with the fixture removed and the view populated correctly.
- **No mobile breakpoint QA.** Only 1440px and 1024px were requested and tested. CSS
  breakpoints exist at 1120px and 900px but the sub-900px layout was not screenshotted.
- **Topbar "Modelled: 2024 onward"** rather than a year range. `/api/meta` gives
  `nowcast_from` but no explicit modelled end year; deriving one from `sales_years` would
  be a guess, so the label states the boundary instead.
- **Legacy and Current can coincide in the modelled tail too** for companies where the
  regime median and the last observed value are close (e.g. Sally Beauty). Legacy is drawn
  first, so Current sits on top. Deselecting a variant separates them; there is no
  automatic offset, which would falsify the values.
- **No CSV/PNG export** — not in the spec, and not built.
- **The variant comparison fires three extra API calls** per portfolio load (one per
  variant). At current response times this is unnoticeable, but on a slower backend it
  would want caching; there is no client-side cache.
- **The share-of-move figures are only meaningful when the total move is non-zero.** The
  code returns `n/a` rather than dividing by zero, but that path was not exercised because
  no portfolio in the dataset has a zero net move.
- Charts are keyboard-inaccessible beyond the tooltip (a Chart.js canvas limitation). All
  chart content is duplicated in an adjacent HTML table on every view except the
  portfolio quarterly line, whose values appear in the per-period table.

Sources: all figures in this report come from the local API at `http://127.0.0.1:8000`
(`/api/meta`, `/api/company/...`, `/api/portfolio/...`, `/api/backtest`) and from the
artefacts at `carbontrends/precomputed/backtest.json` and
`carbontrends/precomputed/portfolio_cache.json`, generated 2026-08-09 14:16 UTC over
7,895 companies. Brand specification from the user-scoped `schroders-brand` skill.
