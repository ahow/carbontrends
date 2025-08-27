#!/usr/bin/env python3

# Test the new year-over-year outlier methodology on 3M real data
carbon_intensities = {
    2008: 0.274645, 2009: 0.215370, 2010: 0.233291, 2011: 0.205329, 2012: 0.228063,
    2013: 0.257523, 2014: 0.208353, 2015: 0.182665, 2016: 0.198612, 2017: 0.178160,
    2018: 0.202960, 2019: 0.181416, 2020: 0.164057, 2021: 0.129260, 2022: 0.113354, 2023: 0.109544
}

def test_year_over_year_outliers(intensities, company_name="3M"):
    """Test the new outlier detection methodology."""
    sorted_years = sorted(intensities.keys())
    outliers = []
    
    print(f"=== NEW OUTLIER METHODOLOGY TEST FOR {company_name} ===")
    print("Criteria: +100%/-50% change vs both neighbors (or single neighbor if only one available)")
    print()
    
    for i, year in enumerate(sorted_years):
        current_intensity = intensities[year]
        
        # Get previous and next year data
        prev_intensity = None
        next_intensity = None
        prev_year = None
        next_year = None
        
        if i > 0:
            prev_year = sorted_years[i-1]
            prev_intensity = intensities[prev_year]
        
        if i < len(sorted_years) - 1:
            next_year = sorted_years[i+1]
            next_intensity = intensities[next_year]
        
        # Skip if no neighbors available
        if prev_intensity is None and next_intensity is None:
            print(f"{year}: {current_intensity:.6f} | No neighbors | Status: Normal")
            continue
        
        # Check percentage changes
        is_outlier = False
        outlier_reasons = []
        
        prev_change = None
        next_change = None
        
        if prev_intensity is not None:
            prev_change = (current_intensity - prev_intensity) / prev_intensity
            
        if next_intensity is not None:
            next_change = (current_intensity - next_intensity) / next_intensity
        
        # If testing against both years, both must trigger outlier condition
        if prev_intensity is not None and next_intensity is not None:
            prev_outlier = prev_change > 1.0 or prev_change < -0.5
            next_outlier = next_change > 1.0 or next_change < -0.5
            is_outlier = prev_outlier and next_outlier
            
            if is_outlier:
                outlier_reasons = [f"{prev_change*100:.1f}% vs {prev_year}, {next_change*100:.1f}% vs {next_year}"]
        else:
            # Test against single neighbor
            if prev_intensity is not None:
                if prev_change > 1.0 or prev_change < -0.5:
                    is_outlier = True
                    outlier_reasons = [f"{prev_change*100:.1f}% vs {prev_year}"]
            
            if next_intensity is not None:
                if next_change > 1.0 or next_change < -0.5:
                    is_outlier = True
                    outlier_reasons = [f"{next_change*100:.1f}% vs {next_year}"]
        
        # Display results
        neighbors_info = []
        if prev_intensity is not None:
            neighbors_info.append(f"vs {prev_year}: {prev_change*100:+.1f}%")
        if next_intensity is not None:
            neighbors_info.append(f"vs {next_year}: {next_change*100:+.1f}%")
        
        neighbors_str = ", ".join(neighbors_info)
        status = "OUTLIER" if is_outlier else "Normal"
        
        print(f"{year}: {current_intensity:.6f} | {neighbors_str} | Status: {status}")
        
        if is_outlier:
            outliers.append(year)
    
    print(f"\n=== SUMMARY ===")
    print(f"Years flagged as outliers: {outliers}")
    print(f"Years remaining as reported: {[y for y in sorted_years if y not in outliers]}")
    return outliers

# Test the methodology
test_outliers = test_year_over_year_outliers(carbon_intensities)

print(f"\n=== COMPARISON WITH OLD METHOD ===")
print("Old method flagged: 2021, 2022, 2023")
print(f"New method flags: {test_outliers}")
print("Improvement: 2021 should now be treated as valid reported data ✓")