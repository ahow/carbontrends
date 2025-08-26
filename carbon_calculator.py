import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from scipy import interpolate
import streamlit as st

class CarbonCalculator:
    """Calculates carbon attribution for investments and handles temporal smoothing."""
    
    def __init__(self, data: Dict[str, pd.DataFrame]):
        self.data = data
        self.reference_df = data['reference']
        self.carbon_df = data['carbon']
        self.sales_df = data['sales']
        self.ev_df = data['ev']
        
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
            
            # Second pass: identify and remove carbon intensity outliers
            valid_intensities = []
            valid_years = []
            for year_int, data in intensity_data.items():
                if data['intensity'] is not None:
                    valid_intensities.append(data['intensity'])
                    valid_years.append(year_int)
            
            if len(valid_intensities) >= 3:
                # Remove outliers using carbon intensity
                intensities_array = np.array(valid_intensities)
                median_intensity = np.median(intensities_array)
                mad_intensity = np.median(np.abs(intensities_array - median_intensity))
                
                # Flag carbon intensity outliers (>3 MADs from median)
                intensity_threshold = 3 * mad_intensity if mad_intensity > 0 else median_intensity * 0.1
                outlier_mask = np.abs(intensities_array - median_intensity) > intensity_threshold
                
                # Also flag multiplicative outliers (>5x median intensity)
                multiplicative_outlier_mask = intensities_array > (median_intensity * 5)
                outlier_mask = outlier_mask | multiplicative_outlier_mask
                
                # Remove outlier years from consideration
                for i, year_int in enumerate(valid_years):
                    if outlier_mask[i]:
                        intensity_data[year_int]['intensity'] = None  # Mark as invalid
                        intensity_data[year_int]['is_outlier'] = True
                        original_intensity = valid_intensities[i]
                        print(f"Carbon intensity outlier removed for {company_name} year {year_int}: {original_intensity:.6f} tCO2e/USD")
            
            # Third pass: estimate missing carbon intensities using temporal interpolation
            self._estimate_missing_intensities(intensity_data, company_name)
            
            # Fourth pass: create final annual data using corrected intensities
            for year_int in sorted(intensity_data.keys()):
                data = intensity_data[year_int]
                
                # Estimate missing EV if needed
                if not data['has_ev']:
                    data['ev'] = self._estimate_enterprise_value(year_int, ev_data, sales_data, data['sales'])
                
                # Skip if we don't have essential data
                if data['ev'] is None or data['ev'] <= 0:
                    continue
                if data['sales'] is None or data['sales'] <= 0:
                    continue
                if data['intensity'] is None:
                    continue
                
                # Calculate final carbon emissions from intensity and sales
                final_carbon = data['intensity'] * data['sales']
                
                # Determine data quality
                data_quality = 'reported'
                if not data['has_carbon'] or not data['has_ev'] or data.get('is_outlier', False):
                    data_quality = 'estimated'
                
                annual_data.append({
                    'year': year_int,
                    'carbon_emissions': final_carbon,
                    'enterprise_value': data['ev'],
                    'data_quality': data_quality
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
    
    def _estimate_carbon_emissions(self, target_year: int, carbon_data: Dict[str, float],
                                 sales_data: Dict[str, float], target_sales: Optional[float]) -> Optional[float]:
        """Estimate carbon emissions for missing years using improved trend-based logic."""
        try:
            # If we have carbon data, interpolate/extrapolate
            if carbon_data:
                years = sorted([int(y) for y in carbon_data.keys()])
                values = [carbon_data[str(y)] for y in years]
                
                if len(years) >= 2:
                    # Linear interpolation/extrapolation
                    carbon_estimate = np.interp(target_year, years, values)
                    return max(float(carbon_estimate), 0.0)
                elif len(years) == 1:
                    # Improved estimation for single data point
                    single_year = years[0]
                    single_carbon = values[0]
                    
                    # For historical years (before first data point), use conservative approach
                    if target_year < single_year:
                        # Assume historical emissions were higher due to less efficient technology
                        # Use moderate increase: 2-3% per year going backward
                        years_back = single_year - target_year
                        historical_multiplier = 1 + (0.025 * years_back)  # 2.5% increase per year back
                        historical_estimate = single_carbon * historical_multiplier
                        
                        # But cap it to avoid unrealistic values (max 2x the known value)
                        return min(historical_estimate, single_carbon * 2.0)
                    
                    # For future years (after first data point), assume improvement
                    elif target_year > single_year:
                        # Assume emissions decrease due to efficiency improvements
                        years_forward = target_year - single_year
                        future_multiplier = max(0.5, 1 - (0.02 * years_forward))  # 2% decrease per year, min 50%
                        return single_carbon * future_multiplier
                    
                    # For the same year, return the value
                    else:
                        return single_carbon
            
            # If no carbon data but have sales data, use industry average intensity
            if target_sales and target_sales > 0:
                # Conservative carbon intensity: 0.5 tCO2e per $1M sales
                default_intensity = 0.5 / 1000000
                return target_sales * default_intensity
            
            return None
            
        except Exception:
            return None
    
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
                else:
                    # Interpolate/extrapolate for missing years
                    years_list = sorted(annual_df['year'].tolist())
                    ownership_values = annual_df['ownership_percentage'].to_numpy()
                    ev_values = annual_df['enterprise_value'].to_numpy()
                    
                    ownership_pct = np.interp(year, years_list, ownership_values)
                    ev = np.interp(year, years_list, ev_values)
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
                    'data_quality': data_quality
                })
            
            return pd.DataFrame(monthly_data)
            
        except Exception as e:
            st.error(f"Error generating monthly data: {str(e)}")
            return pd.DataFrame()
    
    def _create_smooth_monthly_curve(self, annual_df: pd.DataFrame, min_year: int, max_year: int) -> Dict[str, float]:
        """Create a smooth monthly emissions curve that preserves annual totals exactly."""
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
            
            # Step 1: Generate constrained smooth monthly estimates
            # Use a two-phase approach: create base trend, then adjust to meet constraints
            
            # Phase 1: Create smooth baseline using annual midpoints
            annual_years = sorted(annual_targets.keys())
            annual_values = [annual_targets[year] for year in annual_years]
            
            # Create smooth function through annual midpoints (July 1st)
            annual_timestamps = []
            for year in annual_years:
                try:
                    midpoint = pd.Timestamp(year=year, month=7, day=1)
                    if pd.notna(midpoint) and midpoint != pd.NaT:
                        annual_timestamps.append(midpoint.timestamp())
                    else:
                        # Fallback to simple timestamp calculation
                        import datetime
                        dt = datetime.datetime(year, 7, 1)
                        annual_timestamps.append(dt.timestamp())
                except Exception:
                    # Fallback to simple timestamp calculation
                    import datetime
                    dt = datetime.datetime(year, 7, 1)
                    annual_timestamps.append(dt.timestamp())
            
            # Create interpolation function
            if len(annual_values) >= 3:
                f_smooth = interpolate.PchipInterpolator(annual_timestamps, annual_values)
            else:
                f_smooth = interpolate.interp1d(annual_timestamps, annual_values, 
                                              kind='linear', bounds_error=False, 
                                              fill_value=annual_values[0])
            
            # Phase 2: For each year with an annual target, distribute it across 12 months
            # while maintaining smooth transitions between years
            for year in range(min_year, max_year + 1):
                year_keys = [f"{year}-{month:02d}" for month in range(1, 13)]
                
                if year in annual_targets:
                    # This year has a known annual total - distribute it smoothly
                    target_annual = annual_targets[year]
                    
                    # Create realistic monthly variation around annual average
                    annual_avg = target_annual / 12  # Average monthly rate
                    
                    # Generate smooth variation weights based on interpolated curve
                    monthly_variations = []
                    for month in range(1, 13):
                        try:
                            month_date = pd.Timestamp(year=year, month=month, day=15)  # Mid-month
                            if pd.notna(month_date) and month_date != pd.NaT:
                                month_timestamp = month_date.timestamp()
                            else:
                                import datetime
                                dt = datetime.datetime(year, month, 15)
                                month_timestamp = dt.timestamp()
                        except Exception:
                            import datetime
                            dt = datetime.datetime(year, month, 15)
                            month_timestamp = dt.timestamp()
                        
                        # Get smooth interpolated value
                        smooth_value = float(f_smooth(month_timestamp))
                        
                        # Create variation factor relative to annual average (but constrained)
                        # Convert smooth annual value to monthly equivalent
                        smooth_monthly = smooth_value / 12
                        
                        # Calculate variation from annual average (limit to ±30% variation)
                        if annual_avg > 0:
                            variation_factor = smooth_monthly / annual_avg
                            variation_factor = np.clip(variation_factor, 0.7, 1.3)  # ±30% max variation
                        else:
                            variation_factor = 1.0
                        
                        monthly_variations.append(variation_factor)
                    
                    # Normalize to ensure sum equals target annual
                    total_variation = sum(monthly_variations)
                    if total_variation > 0:
                        normalized_variations = [v / total_variation for v in monthly_variations]
                    else:
                        normalized_variations = [1/12] * 12  # Equal distribution fallback
                    
                    # Distribute annual total with realistic monthly variations
                    for i, month in enumerate(range(1, 13)):
                        key = f"{year}-{month:02d}"
                        monthly_curve[key] = target_annual * normalized_variations[i]
                        
                else:
                    # Year without target - use interpolated smooth values
                    for month in range(1, 13):
                        try:
                            month_date = pd.Timestamp(year=year, month=month, day=15)
                            if pd.notna(month_date) and month_date != pd.NaT:
                                month_timestamp = month_date.timestamp()
                            else:
                                import datetime
                                dt = datetime.datetime(year, month, 15)
                                month_timestamp = dt.timestamp()
                        except Exception:
                            import datetime
                            dt = datetime.datetime(year, month, 15)
                            month_timestamp = dt.timestamp()
                        
                        smooth_annual = float(f_smooth(month_timestamp))
                        key = f"{year}-{month:02d}"
                        monthly_curve[key] = max(0, smooth_annual / 12)
            
            # Phase 3: Validation - verify annual totals match exactly
            for year, target_annual in annual_targets.items():
                year_keys = [f"{year}-{month:02d}" for month in range(1, 13)]
                calculated_sum = sum(monthly_curve.get(key, 0) for key in year_keys)
                difference = abs(calculated_sum - target_annual)
                
                # Should be mathematically exact, but allow for tiny floating point errors
                if difference > 0.001:  # 0.001 threshold for floating point precision
                    print(f"WARNING: Year {year} sum mismatch: target={target_annual:.6f}, calculated={calculated_sum:.6f}, diff={difference:.6f}")
                else:
                    print(f"Year {year}: target={target_annual:.2f}, calculated={calculated_sum:.2f}, ✓ exact match")
            
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
    
    def _smooth_year_transition(self, monthly_curve: Dict[str, float], year1: int, year2: int) -> None:
        """Apply gentle smoothing at transitions between reported and estimated years."""
        try:
            # Get end of year1 and start of year2 values
            year1_dec = monthly_curve.get(f"{year1}-12", 0)
            year2_jan = monthly_curve.get(f"{year2}-01", 0)
            
            # If there's a significant jump, apply gentle smoothing
            if abs(year2_jan - year1_dec) > 0.1 * max(year1_dec, year2_jan):
                # Calculate a smooth transition value
                transition_value = (year1_dec + year2_jan) / 2
                
                # Apply gentle transition over the boundary months
                # Adjust December of year1 and January of year2 slightly toward transition
                smoothing_factor = 0.3  # Adjust by 30% toward smooth transition
                
                if f"{year1}-12" in monthly_curve:
                    monthly_curve[f"{year1}-12"] = (
                        year1_dec * (1 - smoothing_factor) + 
                        transition_value * smoothing_factor
                    )
                
                if f"{year2}-01" in monthly_curve:
                    monthly_curve[f"{year2}-01"] = (
                        year2_jan * (1 - smoothing_factor) + 
                        transition_value * smoothing_factor
                    )
                    
        except Exception as e:
            # If smoothing fails, leave values as they are
            pass
    
    def _estimate_missing_intensities(self, intensity_data: Dict, company_name: str) -> None:
        """Estimate missing carbon intensities using temporal interpolation."""
        try:
            # Get valid intensities for interpolation
            valid_years = []
            valid_intensities = []
            
            for year_int in sorted(intensity_data.keys()):
                data = intensity_data[year_int]
                if data['intensity'] is not None and not data.get('is_outlier', False):
                    valid_years.append(year_int)
                    valid_intensities.append(data['intensity'])
            
            if len(valid_intensities) < 2:
                # Not enough data for interpolation, use median or default
                if len(valid_intensities) == 1:
                    default_intensity = valid_intensities[0]
                else:
                    # Use industry default: 0.1 tCO2e per $1000 sales
                    default_intensity = 0.0001
                
                for year_int, data in intensity_data.items():
                    if data['intensity'] is None and data['sales'] is not None:
                        intensity_data[year_int]['intensity'] = default_intensity
                        print(f"Used default carbon intensity for {company_name} year {year_int}: {default_intensity:.6f} tCO2e/USD")
                return
            
            # Interpolate/extrapolate missing intensities with realistic trends
            valid_years_array = np.array(valid_years)
            valid_intensities_array = np.array(valid_intensities)
            
            # If we have enough data points, fit a trend line
            if len(valid_intensities) >= 3:
                # Fit linear trend to capture improvement/worsening over time
                trend_coeffs = np.polyfit(valid_years_array, valid_intensities_array, 1)
                slope, intercept = trend_coeffs
                
                print(f"Carbon intensity trend for {company_name}: slope={slope:.8f} tCO2e/USD/year, intercept={intercept:.6f}")
                
                for year_int, data in intensity_data.items():
                    if data['intensity'] is None and data['sales'] is not None:
                        # Use trend line for extrapolation, interpolation for interior points
                        if year_int < min(valid_years_array) or year_int > max(valid_years_array):
                            # Extrapolation: use trend line but cap reasonable bounds
                            estimated_intensity = slope * year_int + intercept
                            # Cap to reasonable range (0.5x to 2x median of valid data)
                            median_intensity = np.median(valid_intensities_array)
                            estimated_intensity = np.clip(estimated_intensity, 
                                                        median_intensity * 0.5, 
                                                        median_intensity * 2.0)
                        else:
                            # Interpolation: use linear interpolation for interior points
                            estimated_intensity = np.interp(year_int, valid_years_array, valid_intensities_array)
                        
                        intensity_data[year_int]['intensity'] = estimated_intensity
                        print(f"Estimated carbon intensity for {company_name} year {year_int}: {estimated_intensity:.6f} tCO2e/USD")
            else:
                # Fallback to simple linear interpolation
                for year_int, data in intensity_data.items():
                    if data['intensity'] is None and data['sales'] is not None:
                        estimated_intensity = np.interp(year_int, valid_years_array, valid_intensities_array)
                        intensity_data[year_int]['intensity'] = estimated_intensity
                        print(f"Estimated carbon intensity for {company_name} year {year_int}: {estimated_intensity:.6f} tCO2e/USD")
                    
        except Exception as e:
            print(f"Error estimating intensities for {company_name}: {e}")
            # Fallback: use a conservative default intensity
            default_intensity = 0.0001  # 0.1 tCO2e per $1000 sales
            for year_int, data in intensity_data.items():
                if data['intensity'] is None and data['sales'] is not None:
                    intensity_data[year_int]['intensity'] = default_intensity
