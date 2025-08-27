#!/usr/bin/env python3
import sys
import os
sys.path.append(os.getcwd())

import pandas as pd
import numpy as np

def evaluate_estimation_methodology():
    """Evaluate current estimation methodology by testing against known data."""
    
    # Load sample data
    try:
        excel_data = pd.read_excel('sample_data.xlsx', sheet_name=None, engine='openpyxl')
        reference_df = excel_data['Reference']
        carbon_df = excel_data['Carbon']
        sales_df = excel_data['Sales']
    except Exception as e:
        print(f"Error loading data: {e}")
        return
    
    print("=== ESTIMATION METHODOLOGY EVALUATION ===")
    print("Testing accuracy by hiding known data and estimating it")
    print()
    
    # Analyze each company
    companies = reference_df.to_dict('records')
    all_errors = []
    all_relative_errors = []
    company_results = []
    
    for company in companies:
        company_name = company.get('Company', 'Unknown')
        isin = company.get('ISIN', '')
        
        if not isin:
            continue
            
        # Get company data
        carbon_data = get_company_data(carbon_df, isin)
        sales_data = get_company_data(sales_df, isin)
        
        # Calculate intensities
        intensities = {}
        for year in sorted(set(carbon_data.keys()) & set(sales_data.keys())):
            if sales_data[year] > 0:
                intensity = carbon_data[year] / sales_data[year]
                intensities[year] = intensity
        
        if len(intensities) < 4:  # Need enough data for meaningful testing
            continue
            
        print(f"\n--- {company_name} ---")
        print(f"Available years: {sorted(intensities.keys())}")
        
        # Test estimation by hiding different years
        year_errors = test_estimation_accuracy(intensities, company_name)
        
        if year_errors:
            company_results.append({
                'company': company_name,
                'errors': year_errors,
                'mean_error': np.mean([abs(e['error']) for e in year_errors]),
                'mean_relative_error': np.mean([abs(e['relative_error']) for e in year_errors])
            })
            
            for error_data in year_errors:
                all_errors.append(abs(error_data['error']))
                all_relative_errors.append(abs(error_data['relative_error']))
    
    # Overall analysis
    print(f"\n=== OVERALL ACCURACY RESULTS ===")
    if all_errors:
        print(f"Mean Absolute Error: {np.mean(all_errors):.6f} tCO2e/USD")
        print(f"Median Absolute Error: {np.median(all_errors):.6f} tCO2e/USD")
        print(f"Mean Relative Error: {np.mean(all_relative_errors)*100:.2f}%")
        print(f"Median Relative Error: {np.median(all_relative_errors)*100:.2f}%")
        print(f"Max Relative Error: {np.max(all_relative_errors)*100:.2f}%")
        
        # Identify problematic patterns
        high_error_threshold = 0.5  # 50% relative error
        high_errors = [e for e in all_relative_errors if e > high_error_threshold]
        print(f"Estimates with >50% error: {len(high_errors)}/{len(all_relative_errors)} ({len(high_errors)/len(all_relative_errors)*100:.1f}%)")
        
        # Company-level analysis
        print(f"\n=== COMPANY-LEVEL ACCURACY ===")
        for result in sorted(company_results, key=lambda x: x['mean_relative_error'], reverse=True):
            print(f"{result['company']}: {result['mean_relative_error']*100:.1f}% avg error")
            
        return analyze_estimation_patterns(company_results)
    else:
        print("No estimation errors to analyze")
        return None

def test_estimation_accuracy(intensities, company_name):
    """Test estimation accuracy by hiding known data points."""
    sorted_years = sorted(intensities.keys())
    errors = []
    
    # Test hiding middle years (most common missing scenario)
    for i in range(1, len(sorted_years) - 1):  # Don't hide first/last
        hidden_year = sorted_years[i]
        actual_value = intensities[hidden_year]
        
        # Create dataset without this year
        test_intensities = {k: v for k, v in intensities.items() if k != hidden_year}
        
        # Estimate the hidden year
        estimated_value = estimate_missing_year(test_intensities, hidden_year)
        
        if estimated_value is not None:
            error = estimated_value - actual_value
            relative_error = error / actual_value if actual_value != 0 else 0
            
            errors.append({
                'year': hidden_year,
                'actual': actual_value,
                'estimated': estimated_value,
                'error': error,
                'relative_error': relative_error
            })
            
            print(f"  {hidden_year}: Actual={actual_value:.6f}, Est={estimated_value:.6f}, Error={relative_error*100:+.1f}%")
    
    return errors

def estimate_missing_year(intensities, target_year):
    """Estimate a single missing year using current methodology."""
    sorted_years = sorted(intensities.keys())
    sorted_values = [intensities[year] for year in sorted_years]
    
    if len(sorted_values) < 2:
        return None
    
    # Use linear trend (current methodology)
    years_array = np.array(sorted_years)
    values_array = np.array(sorted_values)
    
    # Fit linear trend
    slope = np.sum((years_array - np.mean(years_array)) * (values_array - np.mean(values_array))) / np.sum((years_array - np.mean(years_array))**2)
    intercept = np.mean(values_array) - slope * np.mean(years_array)
    
    # Estimate target year
    estimated = slope * target_year + intercept
    
    # Apply safety caps (current methodology)
    median_value = np.median(values_array)
    capped_estimate = np.clip(estimated, median_value * 0.5, median_value * 2.0)
    
    return capped_estimate

def analyze_estimation_patterns(company_results):
    """Analyze patterns in estimation errors to suggest improvements."""
    print(f"\n=== ESTIMATION PATTERN ANALYSIS ===")
    
    # Collect all error data
    all_error_data = []
    for result in company_results:
        for error in result['errors']:
            all_error_data.append({
                'company': result['company'],
                'year': error['year'],
                'actual': error['actual'],
                'estimated': error['estimated'],
                'relative_error': abs(error['relative_error'])
            })
    
    if not all_error_data:
        return None
    
    # Analyze by year position (early, middle, late in timeline)
    early_errors = []
    middle_errors = []
    late_errors = []
    
    for result in company_results:
        years = sorted([e['year'] for e in result['errors']])
        if len(years) >= 3:
            third = len(years) // 3
            early_years = years[:third]
            late_years = years[-third:]
            middle_years = [y for y in years if y not in early_years and y not in late_years]
            
            for error in result['errors']:
                if error['year'] in early_years:
                    early_errors.append(abs(error['relative_error']))
                elif error['year'] in late_years:
                    late_errors.append(abs(error['relative_error']))
                else:
                    middle_errors.append(abs(error['relative_error']))
    
    print(f"Early years error: {np.mean(early_errors)*100:.1f}% (n={len(early_errors)})")
    print(f"Middle years error: {np.mean(middle_errors)*100:.1f}% (n={len(middle_errors)})")
    print(f"Late years error: {np.mean(late_errors)*100:.1f}% (n={len(late_errors)})")
    
    # Suggest improvements
    suggest_improvements(all_error_data)
    
    return all_error_data

def suggest_improvements(error_data):
    """Suggest improvements to estimation methodology."""
    print(f"\n=== IMPROVEMENT RECOMMENDATIONS ===")
    
    # Check if polynomial would be better than linear
    high_error_cases = [e for e in error_data if e['relative_error'] > 0.3]
    
    print(f"Cases with >30% error: {len(high_error_cases)}/{len(error_data)}")
    
    if len(high_error_cases) > len(error_data) * 0.3:
        print("✓ RECOMMENDATION: Consider polynomial (quadratic) fitting instead of linear")
        print("✓ RECOMMENDATION: Adaptive capping based on data volatility")
        print("✓ RECOMMENDATION: Sector-specific estimation models")
    else:
        print("✓ Current linear methodology appears adequate for most cases")
        print("✓ Consider minor tuning of safety caps")

def get_company_data(df, isin):
    """Extract company data by ISIN."""
    company_row = df[df['ISIN'] == isin]
    if company_row.empty:
        return {}
    
    year_columns = [col for col in df.columns if str(col).isdigit()]
    year_data = {}
    
    for year_col in year_columns:
        value = company_row[year_col].iloc[0]
        if pd.notna(value) and value > 0:
            year_data[int(year_col)] = float(value)
    
    return year_data

if __name__ == "__main__":
    evaluate_estimation_methodology()