import streamlit as st
import pandas as pd
import numpy as np

# Load the actual data processor to see what's happening
st.set_page_config(page_title="Debug 3M", layout="wide")

# Load processors
@st.cache_data
def load_processors():
    from data_processor import DataProcessor
    from carbon_calculator import CarbonCalculator
    
    # Load sample data
    processor = DataProcessor()
    processor.load_sample_data()
    calculator = CarbonCalculator(processor)
    
    return processor, calculator

processor, calculator = load_processors()

st.title("3M Outlier Detection Debug")

# Get 3M data specifically
companies = processor.get_available_companies()
company_3m = None
for company in companies:
    if "3M" in company['name']:
        company_3m = company
        break

if company_3m:
    st.write(f"Found company: {company_3m['name']} (ISIN: {company_3m['isin']})")
    
    # Get raw data for 3M
    carbon_data = calculator._get_company_data(processor.carbon_df, company_3m['isin'])
    sales_data = calculator._get_company_data(processor.sales_df, company_3m['isin'])
    
    st.write("Raw Carbon Data:", carbon_data)
    st.write("Raw Sales Data:", sales_data)
    
    # Calculate carbon intensities
    intensities = {}
    for year in sorted(set(carbon_data.keys()) & set(sales_data.keys())):
        if sales_data[year] > 0:
            intensity = carbon_data[year] / sales_data[year]
            intensities[int(year)] = intensity
    
    st.write("Carbon Intensities:")
    for year, intensity in sorted(intensities.items()):
        st.write(f"  {year}: {intensity:.6f} tCO2e/USD")
    
    # Apply outlier detection manually
    if len(intensities) >= 3:
        values = list(intensities.values())
        values_array = np.array(values)
        
        median_intensity = np.median(values_array)
        mad_intensity = np.median(np.abs(values_array - median_intensity))
        threshold = 3 * mad_intensity
        
        st.write(f"\nOutlier Detection:")
        st.write(f"Median: {median_intensity:.6f}")
        st.write(f"MAD: {mad_intensity:.6f}")
        st.write(f"3-MAD Threshold: {threshold:.6f}")
        
        for year, intensity in sorted(intensities.items()):
            deviation = abs(intensity - median_intensity)
            is_outlier = deviation > threshold
            st.write(f"{year}: {intensity:.6f} | Dev: {deviation:.6f} | Outlier: {is_outlier}")
else:
    st.error("3M company not found in data")