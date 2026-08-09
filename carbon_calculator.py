import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from scipy import interpolate
import streamlit as st

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
    
    def calculate_attribution(self, company_name: str, investment_amount: float) -> Optional[pd.DataFrame]:
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
            last_sales = None
            for y in sorted(intensity_data):
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
            
            # Add buffer years if needed
            if max_year < 2025:
                max_year = 2025
            if min_year > 2019:
                min_year = 2019
            
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
        """Create smooth monthly emissions curve using cubic spline interpolation while preserving annual totals exactly."""
        try:
            # Create monthly date range
            monthly_dates = pd.date_range(
                start=f'{min_year}-01-01',
                end=f'{max_year}-12-01',
                freq='MS'
            )
            
            all_data = annual_df.copy()
            monthly_curve = {}
            
            if len(all_data) == 1:
                # Single data point - flat monthly distribution
                single_value = all_data.iloc[0]['annual_emissions_attributed']
                monthly_value = single_value / 12
                for date in monthly_dates:
                    key = f"{date.year}-{date.month:02d}"
                    monthly_curve[key] = monthly_value
                return monthly_curve
            
            # Create mapping of year -> annual target
            annual_targets = {}
            for _, row in all_data.iterrows():
                year = int(row['year'])
                annual_targets[year] = row['annual_emissions_attributed']
            
            # SHAPE-PRESERVING LOG-SPACE PCHIP INTERPOLATION
            # Step 1: Build a monotone interpolant through annual data points.
            # PCHIP avoids the overshoot/negative dips a cubic spline can produce;
            # working in log-space keeps emissions strictly positive.
            annual_years = sorted(annual_targets.keys())
            annual_values = [annual_targets[year] for year in annual_years]
            
            # Create spline function through year midpoints (July 1st)
            year_midpoints = [year + 0.5 for year in annual_years]
            
            spline_func = self._build_curve_interpolant(year_midpoints, annual_values)
            
            # Step 2: Generate initial smooth monthly estimates using spline
            initial_monthly = {}
            for date in monthly_dates:
                year = date.year
                month = date.month
                # Convert to fractional year (month 1 = 0.042, month 6 = 0.458, month 12 = 0.958)
                fractional_year = year + (month - 0.5) / 12
                
                # Get smooth annual estimate from spline
                smooth_annual = float(spline_func(fractional_year))
                
                # Convert to monthly rate (annual ÷ 12)
                key = f"{year}-{month:02d}"
                initial_monthly[key] = max(0, smooth_annual / 12)
            
            # Step 3: CONSTRAINT SATISFACTION - Adjust to meet exact annual totals
            # This is the key step that the working methodology uses
            for year in annual_targets:
                year_keys = [f"{year}-{month:02d}" for month in range(1, 13)]
                
                # Get current monthly estimates for this year
                current_monthly = [initial_monthly.get(key, 0) for key in year_keys]
                current_sum = sum(current_monthly)
                target_annual = annual_targets[year]
                
                if current_sum > 0:
                    # Scale factor to meet exact constraint
                    scale_factor = target_annual / current_sum
                    
                    # Apply proportional scaling to maintain shape while meeting constraint
                    for i, key in enumerate(year_keys):
                        monthly_curve[key] = current_monthly[i] * scale_factor
                else:
                    # Fallback to equal distribution
                    monthly_value = target_annual / 12
                    for key in year_keys:
                        monthly_curve[key] = monthly_value
            
            # Step 4: Fill in missing years with spline estimates (no constraints)
            for date in monthly_dates:
                year = date.year
                month = date.month
                key = f"{year}-{month:02d}"
                
                if key not in monthly_curve:  # Year without annual target
                    fractional_year = year + (month - 0.5) / 12
                    smooth_annual = float(spline_func(fractional_year))
                    monthly_curve[key] = max(0, smooth_annual / 12)
            
            # Step 5: Integrity check - annual totals must be preserved exactly.
            for year, target_annual in annual_targets.items():
                year_keys = [f"{year}-{month:02d}" for month in range(1, 13)]
                calculated_sum = sum(monthly_curve.get(key, 0) for key in year_keys)
                if abs(calculated_sum - target_annual) > 0.001:
                    print(f"WARNING: Year {year} annual-total mismatch: "
                          f"target={target_annual:.6f}, got={calculated_sum:.6f}")
            
            return monthly_curve
            
        except Exception as e:
            st.error(f"Error creating smooth monthly curve: {str(e)}")
            # Fallback to simple annual distribution
            monthly_curve = {}
            for date in pd.date_range(start=f'{min_year}-01-01', end=f'{max_year}-12-01', freq='MS'):
                year = date.year
                annual_value = np.interp(year, annual_df['year'].tolist(), 
                                       annual_df['annual_emissions_attributed'].tolist())
                key = f"{year}-{date.month:02d}"
                monthly_curve[key] = annual_value / 12
            return monthly_curve
