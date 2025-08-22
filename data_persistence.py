"""
Data Persistence Module

Handles saving and loading of carbon data and portfolio data across sessions.
Provides portfolio library management functionality.
"""

import pandas as pd
import json
import os
import pickle
from datetime import datetime
from typing import Dict, List, Optional, Any
import streamlit as st


class DataPersistence:
    """Manages persistent storage of data across sessions."""
    
    def __init__(self):
        self.data_dir = "persistent_data"
        self.carbon_data_file = os.path.join(self.data_dir, "carbon_data.pkl")
        self.portfolio_library_file = os.path.join(self.data_dir, "portfolio_library.json")
        self.portfolios_dir = os.path.join(self.data_dir, "portfolios")
        
        # Create directories if they don't exist
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.portfolios_dir, exist_ok=True)
    
    def save_carbon_data(self, carbon_data: Dict[str, pd.DataFrame]) -> bool:
        """Save carbon data to persistent storage."""
        try:
            with open(self.carbon_data_file, 'wb') as f:
                pickle.dump(carbon_data, f)
            
            # Save metadata
            metadata = {
                'saved_at': datetime.now().isoformat(),
                'num_companies': len(carbon_data.get('reference', [])),
                'sheets': list(carbon_data.keys())
            }
            
            metadata_file = os.path.join(self.data_dir, "carbon_data_metadata.json")
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            return True
            
        except Exception as e:
            st.error(f"Error saving carbon data: {str(e)}")
            return False
    
    def load_carbon_data(self) -> Optional[Dict[str, pd.DataFrame]]:
        """Load carbon data from persistent storage."""
        try:
            if os.path.exists(self.carbon_data_file):
                with open(self.carbon_data_file, 'rb') as f:
                    return pickle.load(f)
            return None
            
        except Exception as e:
            st.error(f"Error loading carbon data: {str(e)}")
            return None
    
    def has_carbon_data(self) -> bool:
        """Check if carbon data exists in storage."""
        return os.path.exists(self.carbon_data_file)
    
    def get_carbon_data_info(self) -> Optional[Dict[str, Any]]:
        """Get carbon data metadata."""
        try:
            metadata_file = os.path.join(self.data_dir, "carbon_data_metadata.json")
            if os.path.exists(metadata_file):
                with open(metadata_file, 'r') as f:
                    return json.load(f)
            return None
            
        except Exception:
            return None
    
    def save_portfolio(self, portfolio_name: str, portfolio_data: Dict[datetime, pd.DataFrame]) -> bool:
        """Save a portfolio to the library."""
        try:
            # Save portfolio data
            portfolio_file = os.path.join(self.portfolios_dir, f"{portfolio_name}.pkl")
            with open(portfolio_file, 'wb') as f:
                pickle.dump(portfolio_data, f)
            
            # Update portfolio library
            library = self.load_portfolio_library()
            
            library[portfolio_name] = {
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat(),
                'num_periods': len(portfolio_data),
                'date_range': {
                    'start': min(portfolio_data.keys()).isoformat(),
                    'end': max(portfolio_data.keys()).isoformat()
                },
                'total_holdings': sum(len(df) for df in portfolio_data.values())
            }
            
            self.save_portfolio_library(library)
            return True
            
        except Exception as e:
            st.error(f"Error saving portfolio: {str(e)}")
            return False
    
    def load_portfolio(self, portfolio_name: str) -> Optional[Dict[datetime, pd.DataFrame]]:
        """Load a specific portfolio from the library."""
        try:
            portfolio_file = os.path.join(self.portfolios_dir, f"{portfolio_name}.pkl")
            if os.path.exists(portfolio_file):
                with open(portfolio_file, 'rb') as f:
                    return pickle.load(f)
            return None
            
        except Exception as e:
            st.error(f"Error loading portfolio {portfolio_name}: {str(e)}")
            return None
    
    def add_data_to_portfolio(self, portfolio_name: str, new_data: Dict[datetime, pd.DataFrame]) -> bool:
        """Add new data to an existing portfolio."""
        try:
            # Load existing portfolio
            existing_data = self.load_portfolio(portfolio_name)
            if existing_data is None:
                st.error(f"Portfolio {portfolio_name} not found")
                return False
            
            # Merge with new data
            merged_data = existing_data.copy()
            
            for date, df in new_data.items():
                if date in merged_data:
                    st.warning(f"Data for {date.strftime('%d.%m.%y')} already exists. Replacing...")
                merged_data[date] = df
            
            # Save updated portfolio
            return self.save_portfolio(portfolio_name, merged_data)
            
        except Exception as e:
            st.error(f"Error adding data to portfolio: {str(e)}")
            return False
    
    def delete_portfolio(self, portfolio_name: str) -> bool:
        """Delete a portfolio from the library."""
        try:
            # Remove portfolio file
            portfolio_file = os.path.join(self.portfolios_dir, f"{portfolio_name}.pkl")
            if os.path.exists(portfolio_file):
                os.remove(portfolio_file)
            
            # Update library
            library = self.load_portfolio_library()
            if portfolio_name in library:
                del library[portfolio_name]
                self.save_portfolio_library(library)
            
            return True
            
        except Exception as e:
            st.error(f"Error deleting portfolio: {str(e)}")
            return False
    
    def load_portfolio_library(self) -> Dict[str, Any]:
        """Load the portfolio library metadata."""
        try:
            if os.path.exists(self.portfolio_library_file):
                with open(self.portfolio_library_file, 'r') as f:
                    return json.load(f)
            return {}
            
        except Exception:
            return {}
    
    def save_portfolio_library(self, library: Dict[str, Any]) -> bool:
        """Save the portfolio library metadata."""
        try:
            with open(self.portfolio_library_file, 'w') as f:
                json.dump(library, f, indent=2)
            return True
            
        except Exception as e:
            st.error(f"Error saving portfolio library: {str(e)}")
            return False
    
    def get_portfolio_names(self) -> List[str]:
        """Get list of all portfolio names."""
        library = self.load_portfolio_library()
        return list(library.keys())
    
    def parse_portfolio_file(self, portfolio_file) -> Optional[Dict[datetime, pd.DataFrame]]:
        """Parse uploaded portfolio Excel file into structured data."""
        try:
            xl_file = pd.ExcelFile(portfolio_file)
            portfolio_sheets = {}
            
            for sheet_name in xl_file.sheet_names:
                try:
                    # Parse the date format DD.MM.YY
                    date_obj = datetime.strptime(sheet_name, '%d.%m.%y')
                    
                    # Read the sheet data
                    df = pd.read_excel(portfolio_file, sheet_name=sheet_name)
                    
                    # Clean data - only keep rows with ISIN values
                    df_clean = df[df['ISIN'].notna()].copy()
                    
                    if not df_clean.empty:
                        # Calculate total portfolio value for this period
                        total_value = df_clean['TotalNominal'].sum()
                        
                        # Calculate weights
                        df_clean['Weight'] = df_clean['TotalNominal'] / total_value
                        df_clean['Date'] = date_obj
                        
                        portfolio_sheets[date_obj] = df_clean
                    
                except (ValueError, KeyError) as e:
                    st.warning(f"Skipping sheet {sheet_name}: {str(e)}")
                    continue
            
            return portfolio_sheets if portfolio_sheets else None
            
        except Exception as e:
            st.error(f"Error parsing portfolio file: {str(e)}")
            return None
    
    def cleanup_old_data(self, days_old: int = 30) -> None:
        """Clean up old data files (optional maintenance function)."""
        try:
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            # Clean up old portfolio files
            for filename in os.listdir(self.portfolios_dir):
                file_path = os.path.join(self.portfolios_dir, filename)
                if os.path.getmtime(file_path) < cutoff_date.timestamp():
                    os.remove(file_path)
                    st.info(f"Cleaned up old portfolio file: {filename}")
                    
        except Exception as e:
            st.warning(f"Error during cleanup: {str(e)}")