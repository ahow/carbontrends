#!/usr/bin/env python3
import pandas as pd
import numpy as np

# Load and examine 3M data from uploaded file to understand the estimation
try:
    excel_data = pd.read_excel('sample_data.xlsx', sheet_name=None, engine='openpyxl')
    reference_df = excel_data['Reference']
    carbon_df = excel_data['Carbon']
    sales_df = excel_data['Sales']
    
    # Find 3M in the data
    company_3m = reference_df[reference_df['Company'].str.contains('3M', case=False, na=False)]
    print("=== 3M COMPANY DATA ===")
    print(company_3m)
    
    if not company_3m.empty:
        isin = company_3m['ISIN'].iloc[0]
        print(f"\n3M ISIN: {isin}")
        
        # Get 3M carbon data
        carbon_3m = carbon_df[carbon_df['ISIN'] == isin]
        sales_3m = sales_df[sales_df['ISIN'] == isin]
        
        print("\n=== 3M CARBON DATA ===")
        year_columns = [col for col in carbon_df.columns if str(col).isdigit()]
        carbon_values = {}
        for year_col in year_columns:
            value = carbon_3m[year_col].iloc[0] if not carbon_3m.empty else None
            if pd.notna(value) and value > 0:
                carbon_values[int(year_col)] = float(value)
                print(f"{year_col}: {value:,.0f} tCO2e")
        
        print("\n=== 3M SALES DATA ===")
        sales_values = {}
        for year_col in year_columns:
            value = sales_3m[year_col].iloc[0] if not sales_3m.empty else None
            if pd.notna(value) and value > 0:
                sales_values[int(year_col)] = float(value)
                print(f"{year_col}: ${value:,.0f}")
        
        print("\n=== 3M CARBON INTENSITIES ===")
        intensities = {}
        for year in sorted(set(carbon_values.keys()) & set(sales_values.keys())):
            if sales_values[year] > 0:
                intensity = carbon_values[year] / sales_values[year]
                intensities[year] = intensity
                print(f"{year}: {intensity:.6f} tCO2e/USD")
        
        # Now show how linear interpolation works
        print("\n=== LINEAR ESTIMATION MODEL ===")
        years_list = sorted(intensities.keys())
        intensities_list = [intensities[year] for year in years_list]
        
        if len(years_list) >= 2:
            # Linear regression to find trend
            years_array = np.array(years_list)
            intensities_array = np.array(intensities_list)
            
            # Calculate slope and intercept
            slope = np.sum((years_array - np.mean(years_array)) * (intensities_array - np.mean(intensities_array))) / np.sum((years_array - np.mean(years_array))**2)
            intercept = np.mean(intensities_array) - slope * np.mean(years_array)
            
            print(f"Linear trend: slope = {slope:.8f} tCO2e/USD per year")
            print(f"Linear trend: intercept = {intercept:.6f}")
            
            # Show estimates for missing years
            print(f"\nEstimated values using linear extrapolation:")
            for test_year in [2007, 2024, 2025]:
                estimated = slope * test_year + intercept
                print(f"{test_year}: {estimated:.6f} tCO2e/USD")
                
            print(f"\nExplanation for 2007 vs 2019 (first reported year):")
            if 2019 in intensities:
                reported_2019 = intensities[2019]
                estimated_2007 = slope * 2007 + intercept
                print(f"- 2019 reported (first year): {reported_2019:.6f} tCO2e/USD")
                print(f"- 2007 estimated: {estimated_2007:.6f} tCO2e/USD")
                print(f"- Difference: {reported_2019 - estimated_2007:.6f} tCO2e/USD")
                
                if slope < 0:
                    print(f"- Negative slope ({slope:.8f}) means carbon intensity DECREASES each year")
                    print(f"- This represents efficiency improvements over time")
                    print(f"- Going backwards to 2007 would INCREASE the estimated intensity")
                    print(f"- So 2007 should be HIGHER than 2019, not lower!")
                    print(f"- BUT: Model caps extrapolation to 0.5x-2x median to avoid unrealistic values")
                    
                    median_intensity = np.median(intensities_list)
                    capped_2007 = np.clip(estimated_2007, median_intensity * 0.5, median_intensity * 2.0)
                    print(f"- Median intensity: {median_intensity:.6f} tCO2e/USD")
                    print(f"- Raw 2007 estimate: {estimated_2007:.6f} tCO2e/USD")
                    print(f"- Capped 2007 estimate: {capped_2007:.6f} tCO2e/USD")
                    print(f"- This explains why 2007 appears lower than expected!")
                else:
                    print(f"- Positive slope ({slope:.8f}) means carbon intensity INCREASES each year") 
                    print(f"- Going backwards in time DECREASES the estimated intensity")
    
except Exception as e:
    print(f"Error analyzing data: {e}")