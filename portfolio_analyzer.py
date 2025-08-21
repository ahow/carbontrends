"""
Portfolio Carbon Exposure Analysis Module

This module analyzes portfolio holdings over time and calculates
carbon intensity exposure changes for the entire portfolio.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import streamlit as st


class PortfolioAnalyzer:
    """Analyzes portfolio carbon exposure over time."""
    
    def __init__(self, carbon_calculator):
        """Initialize with a carbon calculator instance."""
        self.carbon_calculator = carbon_calculator
        self.portfolio_data = None
        self.portfolio_analysis = None
    
    def load_portfolio_data(self, portfolio_file) -> bool:
        """Load portfolio holdings data from Excel file."""
        try:
            # Read all sheets from the portfolio file
            xl_file = pd.ExcelFile(portfolio_file)
            portfolio_sheets = {}
            
            for sheet_name in xl_file.sheet_names:
                # Parse the date format DD.MM.YY
                try:
                    # Convert sheet name to datetime
                    date_obj = datetime.strptime(sheet_name, '%d.%m.%y')
                    
                    # Read the sheet data
                    df = pd.read_excel(portfolio_file, sheet_name=sheet_name)
                    
                    # Clean data - only keep rows with ISIN values
                    df_clean = df[df['ISIN'].notna()].copy()
                    
                    # Calculate total portfolio value for this period
                    total_value = df_clean['TotalNominal'].sum()
                    
                    # Calculate weights
                    df_clean['Weight'] = df_clean['TotalNominal'] / total_value
                    df_clean['Date'] = date_obj
                    
                    portfolio_sheets[date_obj] = df_clean
                    
                except (ValueError, KeyError) as e:
                    st.warning(f"Skipping sheet {sheet_name}: {str(e)}")
                    continue
            
            if not portfolio_sheets:
                st.error("No valid portfolio data sheets found")
                return False
            
            self.portfolio_data = portfolio_sheets
            st.success(f"Loaded portfolio data for {len(portfolio_sheets)} periods")
            return True
            
        except Exception as e:
            st.error(f"Error loading portfolio data: {str(e)}")
            return False
    
    def calculate_portfolio_carbon_exposure(self) -> Optional[pd.DataFrame]:
        """Calculate portfolio carbon exposure changes over time."""
        if not self.portfolio_data:
            st.error("No portfolio data loaded")
            return None
        
        try:
            exposure_results = []
            sorted_dates = sorted(self.portfolio_data.keys())
            
            for i in range(len(sorted_dates) - 1):
                current_date = sorted_dates[i]
                next_date = sorted_dates[i + 1]
                
                current_holdings = self.portfolio_data[current_date]
                
                # Calculate exposure change for this period
                period_exposure = self._calculate_period_exposure(
                    current_holdings, current_date, next_date
                )
                
                if period_exposure is not None:
                    exposure_results.append({
                        'period_start': current_date,
                        'period_end': next_date,
                        'portfolio_carbon_change': period_exposure['total_change'],
                        'weighted_exposure': period_exposure['weighted_exposure'],
                        'num_holdings': len(current_holdings),
                        'period_months': self._get_period_months(current_date, next_date)
                    })
            
            if exposure_results:
                self.portfolio_analysis = pd.DataFrame(exposure_results)
                return self.portfolio_analysis
            else:
                st.warning("No portfolio exposure data could be calculated")
                return None
                
        except Exception as e:
            st.error(f"Error calculating portfolio exposure: {str(e)}")
            return None
    
    def _calculate_period_exposure(self, holdings: pd.DataFrame, 
                                 start_date: datetime, end_date: datetime) -> Optional[Dict]:
        """Calculate carbon exposure for a single period."""
        try:
            total_weighted_change = 0.0
            valid_holdings = 0
            detailed_exposure = []
            
            for _, holding in holdings.iterrows():
                isin = str(holding['ISIN'])
                weight = float(holding['Weight'])
                
                # Find company by ISIN
                company_name = self._find_company_by_isin(isin)
                if not company_name:
                    continue
                
                # Get carbon attribution data for this company
                attribution_data = self.carbon_calculator.calculate_attribution(
                    company_name, 1000000  # $1M investment
                )
                
                if attribution_data is None or attribution_data.empty:
                    continue
                
                # Calculate carbon intensity change over the period
                carbon_change = self._calculate_carbon_change(
                    attribution_data, start_date, end_date
                )
                
                if carbon_change is not None:
                    weighted_change = weight * carbon_change
                    total_weighted_change += weighted_change
                    valid_holdings += 1
                    
                    detailed_exposure.append({
                        'isin': isin,
                        'company': company_name,
                        'weight': weight,
                        'carbon_change': carbon_change,
                        'weighted_change': weighted_change
                    })
            
            if valid_holdings > 0:
                return {
                    'total_change': total_weighted_change,
                    'weighted_exposure': detailed_exposure,
                    'valid_holdings': valid_holdings
                }
            else:
                return None
                
        except Exception as e:
            st.warning(f"Error calculating period exposure: {str(e)}")
            return None
    
    def _find_company_by_isin(self, isin: str) -> Optional[str]:
        """Find company name by ISIN in the carbon data."""
        try:
            if not hasattr(self.carbon_calculator, 'reference_df'):
                return None
            
            # Search for ISIN in reference data
            matches = self.carbon_calculator.reference_df[
                self.carbon_calculator.reference_df['ISIN'] == isin
            ]
            
            if not matches.empty:
                return matches.iloc[0]['Name']
            else:
                return None
                
        except Exception:
            return None
    
    def _calculate_carbon_change(self, attribution_data: pd.DataFrame,
                               start_date: datetime, end_date: datetime) -> Optional[float]:
        """Calculate carbon intensity change between two dates."""
        try:
            # Convert dates to monthly data points
            start_month = pd.Timestamp(year=start_date.year, month=start_date.month, day=1)
            end_month = pd.Timestamp(year=end_date.year, month=end_date.month, day=1)
            
            # Find closest data points
            attribution_data['date'] = pd.to_datetime(
                attribution_data[['year', 'month']].assign(day=1)
            )
            
            start_data = attribution_data[attribution_data['date'] == start_month]
            end_data = attribution_data[attribution_data['date'] == end_month]
            
            if start_data.empty or end_data.empty:
                # Try interpolation if exact dates not available
                return self._interpolate_carbon_change(
                    attribution_data, start_month, end_month
                )
            
            start_emissions = start_data.iloc[0]['monthly_emissions_attributed']
            end_emissions = end_data.iloc[0]['monthly_emissions_attributed']
            
            return end_emissions - start_emissions
            
        except Exception:
            return None
    
    def _interpolate_carbon_change(self, attribution_data: pd.DataFrame,
                                 start_date: pd.Timestamp, end_date: pd.Timestamp) -> Optional[float]:
        """Interpolate carbon emissions for missing dates."""
        try:
            # Sort data by date
            data_sorted = attribution_data.sort_values('date')
            
            if len(data_sorted) < 2:
                return None
            
            # Interpolate emissions at start and end dates
            dates_numeric = data_sorted['date'].astype(np.int64)
            emissions = data_sorted['monthly_emissions_attributed'].values
            
            start_numeric = start_date.value
            end_numeric = end_date.value
            
            start_emissions = np.interp(start_numeric, dates_numeric, emissions)
            end_emissions = np.interp(end_numeric, dates_numeric, emissions)
            
            return end_emissions - start_emissions
            
        except Exception:
            return None
    
    def _get_period_months(self, start_date: datetime, end_date: datetime) -> int:
        """Calculate number of months between two dates."""
        return ((end_date.year - start_date.year) * 12 + 
                (end_date.month - start_date.month))
    
    def get_portfolio_summary(self) -> Optional[Dict]:
        """Get summary statistics for portfolio analysis."""
        if self.portfolio_analysis is None:
            return None
        
        try:
            summary = {
                'total_periods': len(self.portfolio_analysis),
                'date_range': {
                    'start': self.portfolio_analysis['period_start'].min(),
                    'end': self.portfolio_analysis['period_end'].max()
                },
                'avg_carbon_change': self.portfolio_analysis['portfolio_carbon_change'].mean(),
                'total_carbon_change': self.portfolio_analysis['portfolio_carbon_change'].sum(),
                'max_exposure': self.portfolio_analysis['portfolio_carbon_change'].max(),
                'min_exposure': self.portfolio_analysis['portfolio_carbon_change'].min(),
                'volatility': self.portfolio_analysis['portfolio_carbon_change'].std()
            }
            
            return summary
            
        except Exception:
            return None