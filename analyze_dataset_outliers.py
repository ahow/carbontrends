#!/usr/bin/env python3
import sys
import os
sys.path.append(os.getcwd())

from data_processor import DataProcessor
from carbon_calculator import CarbonCalculator
import pandas as pd
import numpy as np

def analyze_outlier_percentage():
    """Analyze what percentage of reported annual values are flagged as outliers."""
    
    # Load sample data directly
    sample_file_path = 'sample_data.xlsx'
    try:
        excel_data = pd.read_excel(sample_file_path, sheet_name=None, engine='openpyxl')
        
        # Process the data sheets
        reference_df = excel_data['Reference']
        carbon_df = excel_data['Carbon']
        sales_df = excel_data['Sales']
        
        print("Successfully loaded sample data")
        print(f"Companies in reference: {len(reference_df)}")
        print(f"Carbon data rows: {len(carbon_df)}")
        print(f"Sales data rows: {len(sales_df)}")
        
    except Exception as e:
        print(f"Error loading sample data: {e}")
        return
    
    companies = reference_df.to_dict('records')
    
    total_reported_values = 0
    total_outliers = 0
    company_results = []
    
    print("=== DATASET-WIDE OUTLIER ANALYSIS ===")
    print("Testing year-over-year methodology (+100%/-50% thresholds)")
    print()
    
    for company in companies:
        company_name = company.get('Company', company.get('Name', 'Unknown'))
        isin = company.get('ISIN', '')
        
        if not isin:
            continue
        
        # Get raw data for this company
        carbon_data = get_company_data(carbon_df, isin)
        sales_data = get_company_data(sales_df, isin)
        
        # Calculate carbon intensities
        intensity_data = {}
        for year in sorted(set(carbon_data.keys()) & set(sales_data.keys())):
            if sales_data[year] > 0:
                intensity = carbon_data[year] / sales_data[year]
                intensity_data[int(year)] = {
                    'intensity': intensity,
                    'has_carbon': True,
                    'has_sales': True,
                    'is_outlier': False
                }
        
        # Debug: show intensity data for first few companies
        if len(company_results) < 3:
            print(f"\nDEBUG - {company_name} intensity data:")
            for year in sorted(intensity_data.keys()):
                print(f"  {year}: {intensity_data[year]['intensity']:.6f}")
            print()
        
        if len(intensity_data) < 2:
            # Skip companies with insufficient data
            continue
        
        # Apply outlier detection manually
        outliers_for_company = detect_year_over_year_outliers(intensity_data, company_name)
        
        # Count reported values and outliers
        company_reported = len(intensity_data)
        company_outliers = len(outliers_for_company)
        
        total_reported_values += company_reported
        total_outliers += company_outliers
        
        outlier_percentage = (company_outliers / company_reported * 100) if company_reported > 0 else 0
        
        company_results.append({
            'company': company_name,
            'reported_values': company_reported,
            'outliers': company_outliers,
            'outlier_percentage': outlier_percentage,
            'outlier_years': outliers_for_company
        })
        
        # Show all companies (including 0 outliers) for debugging
        print(f"{company_name}: {company_outliers}/{company_reported} outliers ({outlier_percentage:.1f}%) - Years: {outliers_for_company if outliers_for_company else 'None'}")
    
    # Summary statistics
    overall_percentage = (total_outliers / total_reported_values * 100) if total_reported_values > 0 else 0
    
    print(f"\n=== SUMMARY STATISTICS ===")
    print(f"Total companies analyzed: {len(company_results)}")
    print(f"Total reported annual values: {total_reported_values:,}")
    print(f"Total values flagged as outliers: {total_outliers:,}")
    print(f"Overall outlier percentage: {overall_percentage:.2f}%")
    
    # Distribution analysis
    outlier_percentages = [r['outlier_percentage'] for r in company_results]
    companies_with_outliers = len([r for r in company_results if r['outliers'] > 0])
    
    print(f"\nCompanies with any outliers: {companies_with_outliers}/{len(company_results)} ({companies_with_outliers/len(company_results)*100:.1f}%)")
    print(f"Average outlier rate per company: {np.mean(outlier_percentages):.2f}%")
    print(f"Median outlier rate per company: {np.median(outlier_percentages):.2f}%")
    print(f"Max outlier rate for any company: {np.max(outlier_percentages):.1f}%")
    
    # Show companies with highest outlier rates
    top_outlier_companies = sorted(company_results, key=lambda x: x['outlier_percentage'], reverse=True)[:10]
    print(f"\n=== TOP COMPANIES BY OUTLIER RATE ===")
    for result in top_outlier_companies:
        if result['outliers'] > 0:
            print(f"{result['company']}: {result['outliers']}/{result['reported_values']} ({result['outlier_percentage']:.1f}%)")

def detect_year_over_year_outliers(intensity_data, company_name):
    """Detect outliers using year-over-year percentage change methodology."""
    sorted_years = sorted(intensity_data.keys())
    outliers = []
    
    for i, year in enumerate(sorted_years):
        data = intensity_data[year]
        if data['intensity'] is None:
            continue
        
        current_intensity = data['intensity']
        
        # Get previous and next year data
        prev_intensity = None
        next_intensity = None
        
        if i > 0:
            prev_data = intensity_data[sorted_years[i-1]]
            if prev_data['intensity'] is not None:
                prev_intensity = prev_data['intensity']
        
        if i < len(sorted_years) - 1:
            next_data = intensity_data[sorted_years[i+1]]
            if next_data['intensity'] is not None:
                next_intensity = next_data['intensity']
        
        # Skip if no neighbors available
        if prev_intensity is None and next_intensity is None:
            continue
        
        # Check percentage changes
        is_outlier = False
        
        if prev_intensity is not None and next_intensity is not None:
            # Both neighbors available - current value vs each neighbor
            prev_change = (current_intensity - prev_intensity) / prev_intensity
            next_change = (next_intensity - current_intensity) / current_intensity  # Fixed direction
            
            prev_outlier = prev_change > 1.0 or prev_change < -0.5
            next_outlier = next_change > 1.0 or next_change < -0.5
            
            is_outlier = prev_outlier and next_outlier
        else:
            # Test against single neighbor
            if prev_intensity is not None:
                prev_change = (current_intensity - prev_intensity) / prev_intensity
                if prev_change > 1.0 or prev_change < -0.5:
                    is_outlier = True
            
            if next_intensity is not None:
                next_change = (next_intensity - current_intensity) / current_intensity  # Fixed direction
                if next_change > 1.0 or next_change < -0.5:
                    is_outlier = True
        
        if is_outlier:
            outliers.append(year)
    
    return outliers

def get_company_data(df, isin):
    """Extract company data by ISIN and convert to year: value dict."""
    company_row = df[df['ISIN'] == isin]
    if company_row.empty:
        return {}
    
    # Get year columns (numeric columns)
    year_columns = [col for col in df.columns if str(col).isdigit()]
    year_data = {}
    
    for year_col in year_columns:
        value = company_row[year_col].iloc[0]
        if pd.notna(value) and value > 0:
            year_data[int(year_col)] = float(value)
    
    return year_data

def test_outlier_logic():
    """Test the outlier detection with some artificial extreme cases."""
    print("\n=== TESTING OUTLIER LOGIC WITH EXTREME CASES ===")
    
    # Test case 1: Normal progression (no outliers expected)
    test_data_1 = {
        2020: {'intensity': 1.0}, 2021: {'intensity': 0.8}, 2022: {'intensity': 0.7}
    }
    outliers_1 = detect_year_over_year_outliers(test_data_1, "Test Normal")
    print(f"Normal data (1.0→0.8→0.7): {outliers_1} outliers expected")
    
    # Test case 2: Extreme spike (outlier expected)
    test_data_2 = {
        2020: {'intensity': 1.0}, 2021: {'intensity': 5.0}, 2022: {'intensity': 1.0}
    }
    outliers_2 = detect_year_over_year_outliers(test_data_2, "Test Spike")
    print(f"Spike data (1.0→5.0→1.0): {outliers_2} outliers expected - should flag 2021")
    
    # Test case 3: Extreme drop (outlier expected)  
    test_data_3 = {
        2020: {'intensity': 1.0}, 2021: {'intensity': 0.1}, 2022: {'intensity': 1.0}
    }
    outliers_3 = detect_year_over_year_outliers(test_data_3, "Test Drop")
    print(f"Drop data (1.0→0.1→1.0): {outliers_3} outliers expected - should flag 2021")
    
    # Test case 4: Edge of threshold (no outlier expected)
    test_data_4 = {
        2020: {'intensity': 1.0}, 2021: {'intensity': 1.99}, 2022: {'intensity': 1.0}
    }
    outliers_4 = detect_year_over_year_outliers(test_data_4, "Test Edge")
    print(f"Edge data (1.0→1.99→1.0): {outliers_4} outliers expected - 99% change, under threshold")

if __name__ == "__main__":
    analyze_outlier_percentage()
    test_outlier_logic()