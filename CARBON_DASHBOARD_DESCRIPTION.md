# Carbon Attribution Dashboard — Application Description

## 1. What the Application Is Designed For

The Carbon Attribution Dashboard is a financial analytics tool for investors who need to understand the carbon emissions they are responsible for through their investments. The central question it answers is:

> *"If I invest a given amount of money in a company, how many tonnes of CO₂ does that investment represent, and how has that figure changed over time?"*

It is built for:

- **ESG and financed-emissions reporting** — quantifying the emissions attributable to an investment for regulatory or voluntary disclosure.
- **Portfolio carbon budgeting** — understanding how much of a carbon budget different holdings consume.
- **Trend monitoring** — seeing whether a company's carbon intensity is improving or worsening over time relative to an investment.
- **Data transparency** — every figure is clearly labelled as either *reported* or *estimated*, so the user always knows how much to trust each data point.

---

## 2. What the Application Shows

The dashboard is organised into six tabs:

| Tab | Purpose |
|---|---|
| **About** | Overview, feature list, required data formats, and a getting-started guide. |
| **Data Upload** | Upload and persistently store carbon data and portfolio holdings files. |
| **Company Analysis** | Individual company carbon attribution for a chosen investment amount. |
| **Portfolio Analysis** | Portfolio-level carbon exposure tracking and aggregation across periods. |
| **Portfolio Library** | Create, update, and delete saved portfolios. |
| **System Status** | Health monitoring, error messages, and maintenance tools. |

### Company Analysis Output

When a company and an investment amount are selected, the dashboard displays:

- **Four summary cards** — monthly attribution (tonnes CO₂e/month), annual attribution (tonnes CO₂e/year), data quality (% reported vs estimated), and an overall confidence score.
- **A time-series chart** with two lines:
  - **Blue step function** — the flat annual reported (or estimated) attribution value for each full year.
  - **Green smooth line** — the month-by-month interpolated estimate, showing realistic within-year variation while always summing exactly to the annual total.
- **A monthly data table** — a detailed month-by-month breakdown with calculation transparency.

### Portfolio Analysis Output

- Portfolio weights per holding per period.
- Carbon intensity exposure changes between consecutive periods.
- Aggregated portfolio-level exposure over time.

---

## 3. How the Calculations Work

The smooth interpolated line for each company is produced through a multi-stage pipeline. Each stage feeds the next.

### Stage 1 — Raw Data Collection

For each company (matched by its ISIN identifier), three annual data series are read from the uploaded Excel file:

- **Carbon emissions** — total tonnes CO₂e per year.
- **Sales revenue** — total revenue in USD per year.
- **Enterprise value (EV)** — total company market value per year.

Any year with a zero or absent value is treated as missing and handled in later stages.

### Stage 2 — Carbon Intensity Calculation

Instead of working with absolute emissions, each year is converted to a **carbon intensity**:

> **Carbon Intensity = Carbon Emissions ÷ Sales Revenue**  *(tonnes CO₂e per USD)*

This ratio is more stable over time because it normalises for company size. Intensity is the quantity that gets interpolated and estimated; absolute emissions are recovered later by multiplying back by sales.

### Stage 3 — Outlier Detection and Removal

The intensity series is scanned year by year using a **year-over-year percentage change test**. A year is flagged as an outlier — and excluded from the trend — if its intensity:

- **More than doubles** (+100%) versus both neighbouring years, **or**
- **Falls by more than half** (−50%) versus both neighbouring years.

The test requires both neighbours to agree. If only one neighbour exists (first or last year), that single comparison is used. Flagged years are marked *estimated* and their values are replaced in Stage 4.

These thresholds deliberately preserve genuine efficiency improvements (e.g. a 20–30% year-on-year reduction) while catching data errors such as a tenfold mis-reported spike.

### Stage 4 — Estimating Missing and Outlier Years

For any year lacking reported data or flagged as an outlier, a replacement intensity is estimated using a **linear trend fitted to all clean data points**.

**Fitting the trend:** A least-squares linear regression across all non-outlier years produces a slope (tonnes CO₂e/USD per year) and intercept, capturing the company's long-run direction — a negative slope means improving efficiency, positive means worsening.

**Producing the estimate:** `estimated intensity = slope × year + intercept`.

**Adaptive capping:** The raw estimate is constrained to stay near the company's observed range. The bounds depend on whether the missing year sits inside or outside the reported data:

| Situation | Year position | Allowed range |
|---|---|---|
| **Interpolation** | Between two reported years | 50% – 200% of median intensity |
| **Extrapolation** | Before first / after last reported year | 67% – 150% of median intensity |

Extrapolation gets tighter bounds because there is no surrounding data to anchor it. A final floor ensures the estimate is never zero or negative (minimum of 50% of the median).

### Stage 5 — Reconstructing Annual Attribution

With a complete, clean intensity series:

> **Final Carbon Emissions = Intensity × Sales Revenue**
> **Ownership % = Investment Amount ÷ Enterprise Value**
> **Annual Attributed Emissions = Ownership % × Final Carbon Emissions**

Missing enterprise values are estimated by linear interpolation between known years, or — if no EV data exists at all — approximated using a conservative EV-to-sales multiple of 2.0×.

### Stage 6 — Cubic Spline Smoothing (the interpolated line)

To turn one flat figure per year into a realistic monthly curve, the system uses **cubic spline interpolation**:

- **Control point placement:** The spline passes through the **midpoint of each year (July 1st**, represented as `year + 0.5`), reflecting the middle of each reporting period for natural year-to-year transitions.
- **Spline type:** A **natural cubic spline** (zero second derivative at the endpoints) prevents unrealistic curling beyond the available data. With fewer than three data points it falls back to linear interpolation.
- **Generating monthly values:** Each month is converted to a fractional year position (e.g. January = `year + 0.042`, June = `year + 0.458`, December = `year + 0.958`), the spline is evaluated at each, and the result is divided by 12 to give a monthly rate.
- **Constraint satisfaction (exact annual totals):** The raw spline values for a year will not generally sum to the annual target, so each month is rescaled:

  > **Scale factor = Annual Target ÷ Sum of raw monthly values for that year**

  Multiplying every month by this factor guarantees the 12 monthly values sum **exactly** to the annual total while preserving the smooth shape. Every year is validated, with a warning logged if any mismatch exceeds 0.001 tonnes.
- **Years without annual data:** Where a year inside the chart window has no annual target, the raw spline output is used directly (no scaling), since there is no constraint to enforce.

### Stage 7 — Final Monthly Output

Each month receives its smoothed attributed-emissions value plus the ownership percentage for that year. Each point is tagged **reported** (all underlying annual figures came directly from source data) or **estimated** (any of carbon, sales, or EV was missing or replaced). These tags drive the Data Quality and Confidence cards above the chart.

---

## 4. Data Flow Summary

1. **Upload** an Excel carbon-data file with four sheets: Reference, Carbon, Sales, EV.
2. **Quality checks** run automatically — outlier detection and missing-data estimation.
3. **Monthly smoothing** generates the cubic-spline curve constrained to annual totals.
4. **Attribution** converts company emissions into the investor's personal share.
5. **Visualisation** shows the blue annual steps and green smooth monthly line.
6. **Persistence** saves data to disk so re-uploading is unnecessary across sessions.

---

## 5. Technical Architecture

- **DataProcessor** — Excel ingestion and validation of the four required sheets.
- **CarbonCalculator** — outlier detection, intensity estimation, cubic-spline smoothing, attribution.
- **PortfolioAnalyzer** — portfolio weighting and carbon exposure changes over time.
- **ChartBuilder** — Plotly time-series charts (smooth green line + blue annual steps).
- **DataPersistence** — saving/loading carbon data and the portfolio library across sessions.

**Core libraries:** Streamlit (web framework), Pandas (data handling), NumPy (numerics), SciPy (cubic spline interpolation), Plotly (charts), OpenPyXL (Excel reading).
