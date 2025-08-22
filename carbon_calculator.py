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
            
            # Generate smooth monthly data
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
        """Generate smooth monthly data from annual data points."""
        try:
            # Extend date range for smoother interpolation
            min_year = annual_df['year'].min()
            max_year = annual_df['year'].max()
            
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
            
            # Prepare annual data for interpolation (using mid-year dates)
            annual_dates = [pd.Timestamp(year=int(row['year']), month=6, day=15) for _, row in annual_df.iterrows()]
            
            # Create interpolation functions
            monthly_data = []
            
            for i, date in enumerate(monthly_dates):
                year = date.year
                month = date.month
                
                # Find corresponding annual data
                annual_row = annual_df[annual_df['year'] == year]
                
                if not annual_row.empty:
                    # Use actual annual data
                    row_data = annual_row.iloc[0]
                    ownership_pct = row_data['ownership_percentage']
                    ev = row_data['enterprise_value']
                    data_quality = row_data['data_quality']
                    
                    # Calculate monthly emissions using smooth interpolation
                    monthly_emissions = self._interpolate_smooth_emissions(
                        date, annual_df, annual_dates
                    )
                    
                else:
                    # Interpolate/extrapolate for missing years
                    ownership_pct = self._interpolate_value(
                        date, annual_dates, annual_df['ownership_percentage'].to_numpy()
                    )
                    ev = self._interpolate_value(
                        date, annual_dates, annual_df['enterprise_value'].to_numpy()
                    )
                    monthly_emissions = self._interpolate_smooth_emissions(
                        date, annual_df, annual_dates
                    )
                    data_quality = 'estimated'
                
                # Ensure monthly_emissions is truly monthly (safety check for large values)
                # Values over 1000 tCO2e/month are likely annual values that need conversion
                if monthly_emissions > 1000:
                    monthly_emissions = monthly_emissions / 12
                
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
    
    def _interpolate_smooth_emissions(self, target_date: pd.Timestamp, 
                                    annual_df: pd.DataFrame, annual_dates: List[pd.Timestamp]) -> float:
        """Interpolate emissions with quality-aware smoothing to prevent unrealistic spikes."""
        try:
            if len(annual_dates) == 1:
                # Single data point - return monthly equivalent
                return annual_df.iloc[0]['annual_emissions_attributed'] / 12
            
            # Convert dates to numeric for interpolation
            target_numeric = target_date.timestamp()
            dates_numeric = [d.timestamp() for d in annual_dates]
            emissions_values = annual_df['annual_emissions_attributed'].to_numpy()
            data_qualities = annual_df['data_quality'].tolist()
            
            # Find the closest data points to avoid cross-quality interpolation spikes
            target_year = target_date.year
            closest_indices = []
            
            # Find data points within reasonable range (±3 years) with similar quality
            for i, date in enumerate(annual_dates):
                year_diff = abs(date.year - target_year)
                if year_diff <= 3:
                    closest_indices.append(i)
            
            # If we have good local data, use only those points for interpolation
            if len(closest_indices) >= 2:
                local_dates = [dates_numeric[i] for i in closest_indices]
                local_values = [emissions_values[i] for i in closest_indices]
                
                # Use linear interpolation with local data to prevent spikes
                interpolated_annual = np.interp(target_numeric, local_dates, local_values)
            elif len(dates_numeric) >= 4:
                # Use constrained cubic spline with strict limits
                f = interpolate.CubicSpline(dates_numeric, emissions_values, bc_type='clamped')
                interpolated_annual = f(target_numeric)
                
                # Apply very strict spike prevention
                min_value = min(emissions_values)
                max_value = max(emissions_values)
                median_value = np.median(emissions_values)
                
                # Cap at median ± 50% of range to prevent extreme spikes
                value_range = max_value - min_value
                safe_max = median_value + (0.3 * value_range)
                safe_min = max(0, median_value - (0.3 * value_range))
                
                interpolated_annual = np.clip(interpolated_annual, safe_min, safe_max)
            else:
                # Linear interpolation for fewer data points
                interpolated_annual = np.interp(target_numeric, dates_numeric, emissions_values)
            
            # Convert to monthly equivalent
            monthly_emissions = max(0.0, float(interpolated_annual) / 12.0)
            
            return monthly_emissions
            
        except Exception:
            # Fallback to simple average
            mean_emissions = annual_df['annual_emissions_attributed'].mean()
            return mean_emissions / 12 if mean_emissions > 0 else 0
    
    def _interpolate_value(self, target_date: pd.Timestamp, 
                          annual_dates: List[pd.Timestamp], values: np.ndarray) -> float:
        """Generic interpolation function for non-emissions values."""
        try:
            if len(annual_dates) == 1:
                return values[0]
            
            target_numeric = target_date.timestamp()
            dates_numeric = [d.timestamp() for d in annual_dates]
            
            # Linear interpolation
            interpolated_value = np.interp(target_numeric, dates_numeric, values)
            
            return max(0.0, float(interpolated_value))
            
        except Exception:
            return float(np.mean(values)) if len(values) > 0 else 0.0
    
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
