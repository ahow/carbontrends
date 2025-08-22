#!/usr/bin/env python3
"""
Debug script to test monthly conversion in carbon calculations
"""
import pandas as pd
import numpy as np
from carbon_calculator import CarbonCalculator
from data_processor import DataProcessor
import streamlit as st

def debug_with_real_data():
    """Test with the actual carbon data file"""
    
    # Try to read the actual carbon data file
    try:
        processor = DataProcessor()
        # Load using the read_excel approach like in the app
        excel_file = pd.ExcelFile('attached_assets/CarbonAlphaHC_1755798308840.xlsx')
        
        # Process the data
        data = {}
        
        # Reference sheet
        if 'Reference' in excel_file.sheet_names:
            ref_df = pd.read_excel('attached_assets/CarbonAlphaHC_1755798308840.xlsx', sheet_name='Reference')
            data['reference'] = processor._process_reference_sheet(ref_df)
            print(f"Reference sheet: {len(data['reference'])} companies")
        
        # Carbon sheet
        if 'Carbon' in excel_file.sheet_names:
            carbon_df = pd.read_excel('attached_assets/CarbonAlphaHC_1755798308840.xlsx', sheet_name='Carbon')
            data['carbon'] = processor._process_numeric_sheet(carbon_df, 'Carbon')
            print(f"Carbon sheet: {len(data['carbon'])} companies")
        
        # Sales sheet
        if 'Sales' in excel_file.sheet_names:
            sales_df = pd.read_excel('attached_assets/CarbonAlphaHC_1755798308840.xlsx', sheet_name='Sales')
            data['sales'] = processor._process_numeric_sheet(sales_df, 'Sales')
            print(f"Sales sheet: {len(data['sales'])} companies")
        
        # EV sheet
        if 'EV' in excel_file.sheet_names:
            ev_df = pd.read_excel('attached_assets/CarbonAlphaHC_1755798308840.xlsx', sheet_name='EV')
            data['ev'] = processor._process_numeric_sheet(ev_df, 'EV')
            print(f"EV sheet: {len(data['ev'])} companies")
        
        # Find all 3M companies in the data
        threeM_companies = data['reference'][data['reference']['Company'].str.contains('3M', case=False, na=False)]
        if threeM_companies.empty:
            threeM_companies = data['reference'][data['reference']['Name'].str.contains('3M', case=False, na=False)]
        
        print(f"\n=== All 3M Companies Found ===")
        for _, row in threeM_companies.iterrows():
            print(f"Company: {row['Company']}, ISIN: {row['ISIN']}, Country: {row.get('Country', 'N/A')}")
        
        # Find the US 3M company specifically (ISIN: US88579Y1010)
        us_3m = threeM_companies[threeM_companies['ISIN'] == 'US88579Y1010']
        
        if not us_3m.empty:
            threeM_ref = us_3m
            print(f"\n=== Selected US 3M Company ===")
        else:
            # If no US match, use the first one found
            threeM_ref = threeM_companies.head(1)
            print(f"\n=== Selected First 3M Company (US not found) ===")
        
        if not threeM_ref.empty:
            company_name = threeM_ref.iloc[0]['Company']
            isin = threeM_ref.iloc[0]['ISIN']
            print(f"\n=== Found 3M Company ===")
            print(f"Company name: {company_name}")
            print(f"ISIN: {isin}")
            
            # Check carbon data for this ISIN
            carbon_data = data['carbon'][data['carbon']['ISIN'] == isin]
            if not carbon_data.empty:
                print(f"\n=== Carbon Data ===")
                for col in carbon_data.columns:
                    if col != 'ISIN':
                        value = carbon_data.iloc[0][col]
                        if pd.notna(value):
                            print(f"{col}: {value}")
            
            # Check EV data
            ev_data = data['ev'][data['ev']['ISIN'] == isin]
            if not ev_data.empty:
                print(f"\n=== EV Data ===")
                for col in ev_data.columns:
                    if col != 'ISIN':
                        value = ev_data.iloc[0][col]
                        if pd.notna(value):
                            print(f"{col}: {value}")
            
            # Now test the calculator
            calc = CarbonCalculator(data)
            result = calc.calculate_attribution(company_name, 1000000)
            
            if result is not None and not result.empty:
                print(f"\n=== Attribution Results for {company_name} ===")
                
                # Get latest data point
                latest = result.iloc[-1]
                print(f"Latest data point: {latest['year']}-{latest['month']:02d}")
                print(f"Monthly emissions attributed: {latest['monthly_emissions_attributed']:.2f} tCO2e")
                print(f"Ownership percentage: {latest['ownership_percentage']*100:.6f}%")
                print(f"Enterprise value: ${latest['enterprise_value']/1e6:.1f}M")
                print(f"Data quality: {latest['data_quality']}")
                
                # Check for annual values that might be wrong
                if latest['monthly_emissions_attributed'] > 1000:
                    print("❌ WARNING: Monthly value seems too high (>1000), might be annual!")
                else:
                    print("✅ Monthly value seems reasonable")
                    
            else:
                print("❌ No attribution data generated")
        else:
            print("❌ 3M company not found in reference data")
            
    except Exception as e:
        print(f"❌ Error loading real data: {e}")

def debug_monthly_conversion():
    """Test monthly conversion with sample data"""
    
    # Create a simple test case
    test_data = {
        'reference': pd.DataFrame({
            'ISIN': ['US88579Y1010'],
            'Company': ['3M Co'],
            'Name': ['3M Co'],
            'Sector': ['Industrials'],
            'Country': ['United States']
        }),
        'carbon': pd.DataFrame({
            'ISIN': ['US88579Y1010'],
            '2023': [41004.0]  # Annual emissions in tCO2e
        }),
        'sales': pd.DataFrame({
            'ISIN': ['US88579Y1010'],
            '2023': [34229000000.0]  # Annual sales in USD
        }),
        'ev': pd.DataFrame({
            'ISIN': ['US88579Y1010'],
            '2023': [12000000000.0]  # Enterprise value in USD
        })
    }
    
    print("=== DEBUG: Monthly Conversion Test ===")
    print(f"Input annual carbon emissions: {test_data['carbon'].iloc[0]['2023']} tCO2e")
    print(f"Expected monthly emissions for $1M investment: {(1000000/12000000000)*41004/12:.2f} tCO2e")
    
    # Test the calculator
    calc = CarbonCalculator(test_data)
    result = calc.calculate_attribution('3M Co', 1000000)
    
    if result is not None and not result.empty:
        print("\n=== Monthly Attribution Results ===")
        
        # Check 2023 data
        data_2023 = result[result['year'] == 2023]
        if not data_2023.empty:
            sample_month = data_2023.iloc[0]
            print(f"Year 2023, Month {sample_month['month']}")
            print(f"Monthly emissions attributed: {sample_month['monthly_emissions_attributed']:.2f} tCO2e")
            print(f"Ownership percentage: {sample_month['ownership_percentage']*100:.6f}%")
            print(f"Enterprise value: ${sample_month['enterprise_value']/1e6:.1f}M")
            
            # Manual calculation check
            expected_ownership = 1000000 / 12000000000
            expected_annual_attributed = expected_ownership * 41004
            expected_monthly_attributed = expected_annual_attributed / 12
            
            print(f"\n=== Manual Calculation Check ===")
            print(f"Expected ownership: {expected_ownership*100:.6f}%")
            print(f"Expected annual attributed: {expected_annual_attributed:.2f} tCO2e")
            print(f"Expected monthly attributed: {expected_monthly_attributed:.2f} tCO2e")
            
            actual_monthly = sample_month['monthly_emissions_attributed']
            print(f"Actual monthly attributed: {actual_monthly:.2f} tCO2e")
            print(f"Ratio (actual/expected): {actual_monthly/expected_monthly_attributed:.2f}")
            
            if abs(actual_monthly - expected_monthly_attributed) > 0.01:
                print("❌ ISSUE FOUND: Monthly conversion not working correctly!")
            else:
                print("✅ Monthly conversion working correctly")
    else:
        print("❌ No attribution data generated")

if __name__ == "__main__":
    debug_monthly_conversion()
    print("\n" + "="*50)
    debug_with_real_data()