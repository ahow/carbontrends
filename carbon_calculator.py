import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from scipy import interpolate
import ui_messages as st  # Streamlit-compatible shim; see ui_messages.py

import methodology as M

# Carbon/sales data ends in 2023; "today" is 2026, so we nowcast through here.
CURRENT_YEAR = 2026


class CarbonCalculator:
    """Calculates carbon attribution for investments and handles temporal smoothing."""
    
    def __init__(self, data: Dict[str, pd.DataFrame]):
        self.data = data
        self.reference_df = data['reference']
        self.carbon_df = data['carbon']
        self.sales_df = data['sales']
        self.ev_df = data['ev']
        # Sector statistics (lazily built once, shared across companies).
        self._sector_growth: Optional[Dict[str, float]] = None
        self._sector_threshold: Optional[Dict[str, float]] = None
        self._isin_to_sector: Optional[Dict[str, str]] = None

    # ------------------------------------------------------------------
    # Sector-aware context (thresholds + trend) used by the methodology
    # ------------------------------------------------------------------
    def _build_sector_stats(self) -> None:
        """Compute per-subsector jump thresholds and trend growth once.

        Mirrors backtest_methodology.compute_sector_* so the production path
        uses the exact same sector definitions that were validated offline.
        """
        if self._sector_growth is not None:
            return
        try:
            ref = self.reference_df
            sec_col = 'Subsector' if 'Subsector' in ref.columns else 'Sector'
            self._isin_to_sector = dict(zip(ref['ISIN'], ref[sec_col]))

            carbon = self.carbon_df.set_index('ISIN')
            sales = self.sales_df.set_index('ISIN')
            year_cols = [c for c in carbon.columns if str(c).isdigit()
                         and c in sales.columns]
            sorted_cols = sorted(year_cols, key=lambda c: int(c))

            bucket: Dict[str, List[float]] = {}
            common = carbon.index.intersection(sales.index)
            for isin in common:
                sec = self._isin_to_sector.get(isin, 'UNKNOWN')
                c_row = carbon.loc[isin]
                s_row = sales.loc[isin]
                prev_year = None
                prev_int = None
                for col in sorted_cols:
                    cv = c_row[col]
                    sv = s_row[col]
                    if pd.isna(cv) or pd.isna(sv) or sv <= 0 or cv <= 0:
                        continue
                    yr = int(col)
                    inten = float(cv) / float(sv)
                    if (prev_year is not None and yr - prev_year == 1
                            and prev_int and prev_int > 0):
                        bucket.setdefault(sec, []).append(
                            float(np.log(inten / prev_int)))
                    prev_year, prev_int = yr, inten

            self._sector_growth = {
                sec: float(np.exp(np.median(v))) for sec, v in bucket.items() if v
            }
            self._sector_threshold = {
                sec: M.sector_jump_threshold(v) for sec, v in bucket.items() if v
            }
        except Exception as e:
            print(f"Sector stats build failed, using defaults: {e}")
            self._sector_growth = {}
            self._sector_threshold = {}
            self._isin_to_sector = {}

    def _sector_context(self, isin: str) -> Tuple[float, Optional[float]]:
        """Return (jump_threshold_log, sector_log_growth) for a company."""
        self._build_sector_stats()
        sector = (self._isin_to_sector or {}).get(isin, 'UNKNOWN')
        threshold = (self._sector_threshold or {}).get(sector, M.DEFAULT_JUMP_LOG)
        growth = (self._sector_growth or {}).get(sector)
        sector_log_growth = float(np.log(growth)) if growth and growth > 0 else None
        return threshold, sector_log_growth
        
    def get_companies_list(self) -> List[str]:
        """Get list of available companies for selection."""
        return sorted(self.reference_df['Company'].tolist())
    
    def get_company_info(self, company_name: str) -> Dict[str, str]:
        """Get company metadata from reference sheet."""
        try:
            company_row = self.reference_df[self.reference_df['Company'] == company_name].iloc[0]
            
            return {
                'isin': company_row.get('ISIN', 'N/A'),
                'sector': company_row.get('Sector', 'N/A'),
                'subsector': company_row.get('Subsector', 'N/A'),
                'industry': company_row.get('Industry', 'N/A'),
                'subindustry': company_row.get('Subindustry', 'N/A'),
                'country': company_row.get('Country', 'N/A')
            }
        except (IndexError, KeyError):
            return {
                'isin': 'N/A',
                'sector': 'N/A', 
                'subsector': 'N/A',
                'industry': 'N/A',
                'subindustry': 'N/A',
                'country': 'N/A'
            }
    
    def calculate_attribution(self, company_name: str, investment_amount: float,
                              cap_mode: str = "anchor", drift_offset: float = 0.0,
                              sales_mode: str = "latest") -> Optional[pd.DataFrame]:
        """
        Calculate carbon attribution for a company investment over time.
        
        Args:
            company_name: Name of the company
            investment_amount: Investment amount in USD
            
        Returns:
            DataFrame with monthly carbon attribution data
        """
        try:
            # Get company ISIN
            company_row = self.reference_df[self.reference_df['Company'] == company_name]
            if company_row.empty:
                st.error(f"Company {company_name} not found in reference data")
                return None
            
            isin = company_row.iloc[0]['ISIN']
            
            # Get company data from all sheets
            carbon_data = self._get_company_data(self.carbon_df, isin)
            sales_data = self._get_company_data(self.sales_df, isin)
            ev_data = self._get_company_data(self.ev_df, isin)
            
            # Determine available years
            all_years = set()
            if carbon_data:
                all_years.update(carbon_data.keys())
            if sales_data:
                all_years.update(sales_data.keys())
            if ev_data:
                all_years.update(ev_data.keys())
            
            if not all_years:
                st.warning(f"No data found for {company_name}")
                return None
            
            # Create annual data points with carbon intensity-based outlier removal
            annual_data = []
            
            # First pass: collect all available data with carbon intensity
            intensity_data = {}
            for year in sorted(all_years):
                year_int = int(year)
                carbon_annual = carbon_data.get(year)
                sales_annual = sales_data.get(year)
                ev_annual = ev_data.get(year)
                
                # Calculate carbon intensity where we have both carbon and sales data
                if carbon_annual is not None and sales_annual is not None and sales_annual > 0:
                    carbon_intensity = carbon_annual / sales_annual  # tCO2e per USD
                    intensity_data[year_int] = {
                        'carbon': carbon_annual,
                        'sales': sales_annual,
                        'ev': ev_annual,
                        'intensity': carbon_intensity,
                        'has_carbon': True,
                        'has_sales': True,
                        'has_ev': ev_annual is not None
                    }
                else:
                    # Store partial data for later estimation
                    intensity_data[year_int] = {
                        'carbon': carbon_annual,
                        'sales': sales_annual,
                        'ev': ev_annual,
                        'intensity': None,
                        'has_carbon': carbon_annual is not None,
                        'has_sales': sales_annual is not None and sales_annual > 0,
                        'has_ev': ev_annual is not None
                    }
            
            # Second pass: run the validated estimation pipeline (spike removal +
            # log-PCHIP interpolation + sector-shrinkage extrapolation).
            reported = {y: d['intensity'] for y, d in intensity_data.items()
                        if d['intensity'] is not None}
            if len(reported) < 1:
                st.warning(f"Insufficient carbon/sales data for {company_name}")
                return None

            jump_threshold, sector_log_growth = self._sector_context(isin)
            first_year = min(reported)
            last_reported = max(reported)
            # Cover every historical year plus forward nowcast to the current year.
            target_years = list(range(first_year, max(last_reported, CURRENT_YEAR) + 1))
            estimates = M.estimate_intensity_series(
                reported, target_years,
                jump_threshold_log=jump_threshold,
                sector_log_growth=sector_log_growth,
                cap_mode=cap_mode,
                drift_offset=drift_offset,
            )

            # Most recent ACTUAL sales, used to hold revenue flat for any year
            # with no reported sales figure.
            #
            # This previously iterated over `reported`, i.e. years with BOTH
            # carbon and sales. Carbon reporting lags revenue reporting by
            # about two years, so the fallback silently reverted to the last
            # joint year (2023 on the current dataset) and discarded the 2024
            # and 2025 sales actuals that are present in the workbook. Since
            # reconstructed emissions are intensity x sales, that understated
            # absolute emissions in the nowcast years by roughly 11% and, more
            # importantly, biased the reduction metric: intensity was allowed
            # to fall while revenue was frozen, overstating decarbonisation.
            #
            # Iterate over every year with a positive sales figure instead.
            # sales_mode="latest" (current) reads the most recent year with a
            # positive sales figure. sales_mode="joint" reproduces the legacy
            # behaviour of only considering years that also have carbon data,
            # which discarded the two most recent years of revenue actuals.
            last_sales = None
            _sales_years = sorted(reported) if sales_mode == "joint" else sorted(intensity_data)
            for y in _sales_years:
                sv = intensity_data[y].get('sales')
                if sv and sv > 0:
                    last_sales = sv

            # Third pass: build final annual points from the estimated intensities.
            for year_int in target_years:
                est = estimates.get(year_int)
                if est is None:
                    continue

                existing = intensity_data.get(year_int, {})
                sales_val = existing.get('sales')
                if sales_val is None or sales_val <= 0:
                    sales_val = last_sales  # forward / missing-sales year
                if sales_val is None or sales_val <= 0:
                    continue

                ev_val = existing.get('ev')
                if ev_val is None or ev_val <= 0:
                    ev_val = self._estimate_enterprise_value(
                        year_int, ev_data, sales_data, sales_val)
                if ev_val is None or ev_val <= 0:
                    continue

                final_carbon = est.value * sales_val
                data_quality = 'reported' if est.quality == 'reported' else 'estimated'

                annual_data.append({
                    'year': year_int,
                    'carbon_emissions': final_carbon,
                    'enterprise_value': ev_val,
                    'data_quality': data_quality,
                    'estimate_quality': est.quality,
                    'band_rel': M.band_for(est.quality, est.horizon),
                })
            
            if not annual_data:
                st.warning(f"Insufficient data to calculate attribution for {company_name}")
                return None
            
            # Convert to DataFrame
            annual_df = pd.DataFrame(annual_data)
            annual_df = annual_df.sort_values('year').reset_index(drop=True)
            
            # Calculate ownership and attribution at annual level
            annual_df['ownership_percentage'] = investment_amount / annual_df['enterprise_value']
            annual_df['annual_emissions_attributed'] = annual_df['ownership_percentage'] * annual_df['carbon_emissions']
            
            # Carbon intensity-based outlier removal has already been applied above
            # No additional outlier smoothing needed here
            
            # Generate smooth monthly data that maintains annual totals
            monthly_data = self._generate_monthly_smooth_data(annual_df)
            
            return monthly_data
            
        except Exception as e:
            st.error(f"Error calculating carbon attribution: {str(e)}")
            return None
    
    def _get_company_data(self, df: pd.DataFrame, isin: str) -> Dict[str, float]:
        """Extract company data from a sheet by ISIN."""
        try:
            company_row = df[df['ISIN'] == isin]
            if company_row.empty:
                return {}
            
            company_data = {}
            for col in df.columns:
                if col != 'ISIN':
                    try:
                        year = str(col)
                        value = company_row.iloc[0][col]
                        if pd.notna(value) and value != 0:
                            company_data[year] = float(value)
                    except (ValueError, TypeError, IndexError):
                        continue
            
            return company_data
            
        except Exception:
            return {}
    
    def _estimate_enterprise_value(self, target_year: int, ev_data: Dict[str, float], 
                                 sales_data: Dict[str, float], target_sales: Optional[float]) -> Optional[float]:
        """Estimate enterprise value for missing years."""
        try:
            # If we have EV data, interpolate/extrapolate
            if ev_data:
                years = sorted([int(y) for y in ev_data.keys()])
                values = [ev_data[str(y)] for y in years]
                
                if len(years) >= 2:
                    # Linear interpolation/extrapolation
                    ev_estimate = np.interp(target_year, years, values)
                    return max(float(ev_estimate), 1000000.0)  # Minimum 1M enterprise value
                elif len(years) == 1:
                    # Use the single available value
                    return values[0]
            
            # If we have sales data, estimate EV using industry multiples
            if target_sales and target_sales > 0:
                # Use a conservative EV/Sales ratio of 2.0
                ev_multiple = 2.0
                return target_sales * ev_multiple
            
            return None
            
        except Exception:
            return None
    
    def _build_curve_interpolant(self, x: List[float], y: List[float]):
        """Build a shape-preserving interpolant through annual points.

        Uses log-space PCHIP when all values are positive (monotone, no
        overshoot, never negative); falls back to linear-space PCHIP otherwise.
        """
        xa = np.asarray(x, dtype=float)
        ya = np.asarray(y, dtype=float)
        if len(xa) < 2:
            const = float(ya[0]) if len(ya) else 0.0
            return lambda t: const
        from scipy.interpolate import PchipInterpolator
        if np.all(ya > 0):
            log_interp = PchipInterpolator(xa, np.log(ya), extrapolate=True)
            return lambda t: float(np.exp(log_interp(t)))
        lin_interp = PchipInterpolator(xa, ya, extrapolate=True)
        return lambda t: float(lin_interp(t))

    def _generate_monthly_smooth_data(self, annual_df: pd.DataFrame) -> pd.DataFrame:
        """Generate smooth monthly data from annual data points with annual consistency."""
        try:
            # Extend date range for smoother interpolation
            min_year = int(annual_df['year'].min())
            max_year = int(annual_df['year'].max())
            
            # The monthly range is exactly the annual range. The previous code
            # padded it out to 2019-2025 regardless of the data, which meant the
            # curve was extrapolated outside the estimated annual series with no
            # annual total to constrain it -- unbounded, and presented with the
            # same weight as constrained months.
            
            # Create monthly date range
            monthly_dates = pd.date_range(
                start=f'{min_year}-01-01',
                end=f'{max_year}-12-01',
                freq='MS'
            )
            
            # Create smooth monthly curve
            monthly_curve = self._create_smooth_monthly_curve(annual_df, min_year, max_year)

            # Per-year relative band width (interpolated for filled gap years).
            years_list = sorted(annual_df['year'].tolist())
            band_values = (annual_df.sort_values('year')['band_rel'].to_numpy()
                           if 'band_rel' in annual_df.columns
                           else np.full(len(years_list), M.INTERPOLATED_BAND))

            monthly_data = []
            
            for date in monthly_dates:
                year = date.year
                month = date.month
                month_key = f"{year}-{month:02d}"
                
                # Find corresponding annual data
                annual_row = annual_df[annual_df['year'] == year]
                
                if not annual_row.empty:
                    # Use actual annual data for ownership and EV
                    row_data = annual_row.iloc[0]
                    ownership_pct = row_data['ownership_percentage']
                    ev = row_data['enterprise_value']
                    data_quality = row_data['data_quality']
                    band_rel = float(row_data.get('band_rel', M.INTERPOLATED_BAND))
                else:
                    # Interpolate/extrapolate for missing years
                    ownership_values = annual_df['ownership_percentage'].to_numpy()
                    ev_values = annual_df['enterprise_value'].to_numpy()
                    
                    ownership_pct = np.interp(year, years_list, ownership_values)
                    ev = np.interp(year, years_list, ev_values)
                    band_rel = float(np.interp(year, years_list, band_values))
                    data_quality = 'estimated'
                
                # Get smooth monthly emissions
                monthly_emissions = monthly_curve.get(month_key, 0)
                
                monthly_data.append({
                    'year': year,
                    'month': month,
                    'date': date,
                    'ownership_percentage': ownership_pct,
                    'enterprise_value': ev,
                    'monthly_emissions_attributed': monthly_emissions,
                    'monthly_emissions_lower': monthly_emissions * (1 - band_rel),
                    'monthly_emissions_upper': monthly_emissions * (1 + band_rel),
                    'data_quality': data_quality
                })
            
            return pd.DataFrame(monthly_data)
            
        except Exception as e:
            st.error(f"Error generating monthly data: {str(e)}")
            return pd.DataFrame()
    
    def _create_smooth_monthly_curve(self, annual_df: pd.DataFrame, min_year: int, max_year: int) -> Dict[str, float]:
        """Disaggregate annual emissions into a continuous monthly path.

        WORKFLOW. Annual values are estimated first, upstream in methodology.py,
        and are treated here as fixed. This function only distributes each
        annual total across its twelve months. It never changes an annual level.

        WHY NOT PROPORTIONAL RESCALING. The previous implementation fitted a
        spline through year midpoints, divided by twelve, then multiplied each
        calendar year's months by its own constant k_y = target_y / sum_y to
        force the annual total. Adjacent years get different constants, so the
        series steps at every December-to-January boundary. On 3M those boundary
        steps were 3.6x the median within-year change and reached 12.1%, and the
        six largest month-on-month moves in the entire series were all year
        boundaries. Annual totals were exact, but the path was discontinuous and
        the discontinuities were an artefact of the reconciliation rather than
        anything present in the data.

        METHOD. Mean-preserving disaggregation via the cumulative series, the
        standard approach in national-accounts temporal disaggregation. Build
        the cumulative emissions total at each 1 January, fit a monotone PCHIP
        through those cumulative points, and take each month as the increment of
        that curve across the month:

            value(y, m) = F(y + m/12) - F(y + (m-1)/12)

        Three properties hold simultaneously, none traded against another:

          * Annual totals are exact BY CONSTRUCTION. The twelve increments
            telescope to F(y+1) - F(y), the annual target. No reconciliation
            step exists, so nothing can reintroduce a jump.
          * The path is continuous. Monthly values are increments of a C1 curve
            over equal intervals, so no boundary is privileged over an interior
            month.
          * Values are non-negative, because PCHIP preserves monotonicity of the
            cumulative series and a cumulative of non-negative totals is
            non-decreasing.
        """
        try:
            all_data = annual_df.sort_values('year')
            years = [int(y) for y in all_data['year'].tolist()]
            values = [float(v) for v in all_data['annual_emissions_attributed'].tolist()]

            if not years:
                return {}
            if len(years) == 1:
                monthly_value = values[0] / 12.0
                return {f"{years[0]}-{m:02d}": monthly_value for m in range(1, 13)}

            # Annual estimation happens upstream. If the annual frame has gaps,
            # fill them in log space so the cumulative knots are contiguous,
            # rather than leaving a hole in the monthly path.
            full_years = list(range(years[0], years[-1] + 1))
            if len(full_years) != len(years):
                if all(v > 0 for v in values):
                    filled = np.exp(np.interp(full_years, years, np.log(values)))
                else:
                    filled = np.interp(full_years, years, values)
                values = [float(v) for v in filled]
                years = full_years

            # Cumulative emissions at each 1 January: knot k is the total
            # emitted strictly before years[k].
            knots = [float(y) for y in years] + [float(years[-1] + 1)]
            cumulative = [0.0]
            for v in values:
                cumulative.append(cumulative[-1] + max(v, 0.0))

            from scipy.interpolate import PchipInterpolator
            cumulative_curve = PchipInterpolator(np.asarray(knots, dtype=float),
                                                 np.asarray(cumulative, dtype=float),
                                                 extrapolate=False)

            monthly_curve: Dict[str, float] = {}
            for year in years:
                edges = cumulative_curve(np.array(
                    [year + m / 12.0 for m in range(13)], dtype=float))
                increments = np.clip(np.diff(edges), 0.0, None)
                for m in range(1, 13):
                    monthly_curve[f"{year}-{m:02d}"] = float(increments[m - 1])

            # Integrity check. Exact to floating-point noise because the totals
            # telescope; a failure means the curve was built from something
            # other than the annual frame.
            for year, target_annual in zip(years, values):
                got = sum(monthly_curve[f"{year}-{m:02d}"] for m in range(1, 13))
                if abs(got - target_annual) > max(1e-6, abs(target_annual) * 1e-9):
                    print(f"WARNING: Year {year} annual-total mismatch: "
                          f"target={target_annual:.6f}, got={got:.6f}")

            return monthly_curve

        except Exception as e:
            st.error(f"Error creating smooth monthly curve: {str(e)}")
            return {}
