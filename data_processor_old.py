import pandas as pd
import numpy as np
from typing import Dict, Optional, Any
import streamlit as st

class DataProcessor:
    """Handles loading and preprocessing of Excel data files."""
    
    def __init__(self):
        self.required_sheets = ['Reference', 'Carbon', 'Sales', 'EV']
        
    def load_excel_data(self, file) -> Optional[Dict[str, pd.DataFrame]]:
        """
        Load and validate Excel file with multiple sheets.
        
        Args:
            file: Uploaded file object from Streamlit
            
        Returns:
            Dictionary containing DataFrames for each sheet or None if failed
        """
        try:
            # Read all sheets from Excel file
            excel_data = pd.read_excel(file, sheet_name=None, engine='openpyxl')
            
            # Validate required sheets exist
            missing_sheets = []
            for sheet in self.required_sheets:
                if sheet not in excel_data:
                    missing_sheets.append(sheet)
            
            if missing_sheets:
                st.error(f"Missing required sheets: {', '.join(missing_sheets)}")
                return None
            
            # Process each sheet
            processed_data = {}
            
            # Process Reference sheet
            processed_data['reference'] = self._process_reference_sheet(excel_data['Reference'])
            
            # Process Carbon sheet
            processed_data['carbon'] = self._process_carbon_sheet(excel_data['Carbon'])
            
            # Process Sales sheet
            processed_data['sales'] = self._process_sales_sheet(excel_data['Sales'])
            
            # Process EV sheet
            processed_data['ev'] = self._process_ev_sheet(excel_data['EV'])
            
            # Validate data consistency
            if self._validate_data_consistency(processed_data):
                return processed_data
            else:
                return None
                
        except Exception as e:
            st.error(f"Error loading Excel file: {str(e)}")
            return None
    
    def _process_reference_sheet(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process the Reference sheet containing company metadata."""
        try:
            # Ensure required columns exist
            required_cols = ['ISIN', 'Company']
            for col in required_cols:
                if col not in df.columns:
                    st.error(f"Reference sheet missing required column: {col}")
                    return pd.DataFrame()
            
            # Clean and standardize data
            df_clean = df.copy()
            df_clean['ISIN'] = df_clean['ISIN'].astype(str).str.strip()
            df_clean['Company'] = df_clean['Company'].astype(str).str.strip()
            
            # Fill missing values for optional columns
            optional_cols = ['Sector', 'Subsector', 'Industry', 'Subindustry', 'Country']
            for col in optional_cols:
                if col in df_clean.columns:
                    df_clean[col] = df_clean[col].fillna('Unknown').astype(str)
                else:
                    df_clean[col] = 'Unknown'
            
            # Remove rows with invalid ISIN or Company names
            df_clean = df_clean[
                (df_clean['ISIN'] != 'nan') & 
                (df_clean['Company'] != 'nan') &
                (df_clean['ISIN'].astype(str).str.len() > 0) &
                (df_clean['Company'].astype(str).str.len() > 0)
            ].copy()
            
            return df_clean
            
        except Exception as e:
            st.error(f"Error processing Reference sheet: {str(e)}")
            return pd.DataFrame()
    
    def _process_carbon_sheet(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process the Carbon sheet containing emissions data."""
        try:
            # Ensure ISIN column exists
            if 'ISIN' not in df.columns:
                st.error("Carbon sheet missing ISIN column")
                return pd.DataFrame()
            
            df_clean = df.copy()
            df_clean['ISIN'] = df_clean['ISIN'].astype(str).str.strip()
            
            # Identify year columns (numeric columns)
            year_columns = []
            for col in df_clean.columns:
                if col != 'ISIN':
                    try:
                        year = int(col)
                        if 2000 <= year <= 2030:  # Reasonable year range
                            year_columns.append(col)
                    except (ValueError, TypeError):
                        continue
            
            if not year_columns:
                st.error("No valid year columns found in Carbon sheet")
                return pd.DataFrame()
            
            # Convert year columns to numeric, replacing invalid values with NaN
            for col in year_columns:
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
            
            # Keep only ISIN and year columns
            df_clean = df_clean[['ISIN'] + year_columns]
            
            # Remove rows with invalid ISIN
            df_clean = df_clean[
                (df_clean['ISIN'] != 'nan') & 
                (df_clean['ISIN'].str.len() > 0)
            ]
            
            return df_clean
            
        except Exception as e:
            st.error(f"Error processing Carbon sheet: {str(e)}")
            return pd.DataFrame()
    
    def _process_sales_sheet(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process the Sales sheet containing revenue data."""
        return self._process_numeric_sheet(df, "Sales")
    
    def _process_ev_sheet(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process the EV sheet containing enterprise value data."""
        return self._process_numeric_sheet(df, "EV")
    
    def _process_numeric_sheet(self, df: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
        """Generic processor for numeric data sheets (Sales, EV)."""
        try:
            # Ensure ISIN column exists
            if 'ISIN' not in df.columns:
                st.error(f"{sheet_name} sheet missing ISIN column")
                return pd.DataFrame()
            
            df_clean = df.copy()
            df_clean['ISIN'] = df_clean['ISIN'].astype(str).str.strip()
            
            # Identify year columns
            year_columns = []
            for col in df_clean.columns:
                if col != 'ISIN':
                    try:
                        year = int(col)
                        if 2000 <= year <= 2030:
                            year_columns.append(col)
                    except (ValueError, TypeError):
                        continue
            
            if not year_columns:
                st.warning(f"No valid year columns found in {sheet_name} sheet")
                return pd.DataFrame(columns=['ISIN'])
            
            # Convert year columns to numeric
            for col in year_columns:
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
            
            # Keep only ISIN and year columns
            df_clean = df_clean[['ISIN'] + year_columns]
            
            # Remove rows with invalid ISIN
            df_clean = df_clean[
                (df_clean['ISIN'] != 'nan') & 
                (df_clean['ISIN'].str.len() > 0)
            ]
            
            return df_clean
            
        except Exception as e:
            st.error(f"Error processing {sheet_name} sheet: {str(e)}")
            return pd.DataFrame()
    
    def _validate_data_consistency(self, data: Dict[str, pd.DataFrame]) -> bool:
        """Validate that all sheets have consistent ISIN values."""
        try:
            reference_isins = set(data['reference']['ISIN'].values)
            
            # Check if other sheets have matching ISINs
            for sheet_name, df in data.items():
                if sheet_name == 'reference':
                    continue
                
                if df.empty:
                    continue
                
                sheet_isins = set(df['ISIN'].values)
                
                # Find ISINs in reference but not in this sheet
                missing_isins = reference_isins - sheet_isins
                if missing_isins:
                    st.warning(f"{sheet_name} sheet missing data for {len(missing_isins)} companies")
                
                # Find ISINs in this sheet but not in reference
                extra_isins = sheet_isins - reference_isins
                if extra_isins:
                    st.warning(f"{sheet_name} sheet has data for {len(extra_isins)} companies not in Reference sheet")
            
            return True
            
        except Exception as e:
            st.error(f"Error validating data consistency: {str(e)}")
            return False
    
    def get_data_summary(self, data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Generate summary statistics for the loaded data."""
        summary = {}
        
        try:
            # Company count
            summary['total_companies'] = len(data['reference'])
            
            # Year range for each sheet
            for sheet_name in ['carbon', 'sales', 'ev']:
                if sheet_name in data and not data[sheet_name].empty:
                    year_cols = [col for col in data[sheet_name].columns if col != 'ISIN' and str(col).isdigit()]
                    if year_cols:
                        summary[f'{sheet_name}_year_range'] = (min(year_cols), max(year_cols))
                    else:
                        summary[f'{sheet_name}_year_range'] = None
                else:
                    summary[f'{sheet_name}_year_range'] = None
            
            # Data completeness
            for sheet_name in ['carbon', 'sales', 'ev']:
                if sheet_name in data and not data[sheet_name].empty:
                    year_cols = [col for col in data[sheet_name].columns if col != 'ISIN']
                    if year_cols:
                        total_cells = len(data[sheet_name]) * len(year_cols)
                        non_null_cells = data[sheet_name][year_cols].count().sum()
                        summary[f'{sheet_name}_completeness'] = non_null_cells / total_cells if total_cells > 0 else 0
                    else:
                        summary[f'{sheet_name}_completeness'] = 0
                else:
                    summary[f'{sheet_name}_completeness'] = 0
            
            return summary
            
        except Exception as e:
            st.error(f"Error generating data summary: {str(e)}")
            return {}
