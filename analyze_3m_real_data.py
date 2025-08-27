#!/usr/bin/env python3
import numpy as np

# 3M actual data from user's uploaded spreadsheet
carbon_data = {
    2008: 6940000, 2009: 4980000, 2010: 6220000, 2011: 6080000, 2012: 6820000,
    2013: 7950000, 2014: 6630000, 2015: 5530000, 2016: 5980000, 2017: 5640000,
    2018: 6650000, 2019: 5830000, 2020: 5280000, 2021: 4570000, 2022: 3880000, 2023: 3580000
}

sales_data = {
    2008: 25269000, 2009: 23123000, 2010: 26662000, 2011: 29611000, 2012: 29904000,
    2013: 30871000, 2014: 31821000, 2015: 30274000, 2016: 30109000, 2017: 31657000,
    2018: 32765000, 2019: 32136000, 2020: 32184000, 2021: 35355000, 2022: 34229000, 2023: 32681000
}

print("=== 3M REAL DATA ANALYSIS ===")
print("Carbon Emissions (tCO2e):")
for year in sorted(carbon_data.keys()):
    print(f"  {year}: {carbon_data[year]:,}")

print("\nSales Revenue (USD):")
for year in sorted(sales_data.keys()):
    print(f"  {year}: {sales_data[year]:,}")

# Calculate carbon intensities (tCO2e per USD)
intensities = {}
print("\nCarbon Intensities (tCO2e per USD):")
for year in sorted(carbon_data.keys()):
    if year in sales_data and sales_data[year] > 0:
        intensity = carbon_data[year] / sales_data[year]
        intensities[year] = intensity
        print(f"  {year}: {intensity:.6f}")

# Now run outlier detection on the real intensities
intensity_values = list(intensities.values())
intensity_array = np.array(intensity_values)

median_intensity = np.median(intensity_array)
mad_intensity = np.median(np.abs(intensity_array - median_intensity))
threshold_3mad = 3 * mad_intensity
threshold_5x = median_intensity * 5

print(f"\n=== OUTLIER DETECTION ===")
print(f"Median intensity: {median_intensity:.6f} tCO2e/USD")
print(f"MAD: {mad_intensity:.6f}")
print(f"3-MAD threshold: {threshold_3mad:.6f}")
print(f"5x median threshold: {threshold_5x:.6f}")

print(f"\nYear-by-year analysis:")
for year in sorted(intensities.keys()):
    intensity = intensities[year]
    deviation = abs(intensity - median_intensity)
    is_3mad_outlier = deviation > threshold_3mad
    is_5x_outlier = intensity > threshold_5x
    is_outlier = is_3mad_outlier or is_5x_outlier
    
    status = "OUTLIER" if is_outlier else "Normal"
    print(f"  {year}: {intensity:.6f} | Deviation: {deviation:.6f} | 3-MAD: {is_3mad_outlier} | 5x: {is_5x_outlier} | Status: {status}")

print(f"\n=== KEY INSIGHTS ===")
print(f"- Any deviation > {threshold_3mad:.6f} triggers outlier flag")
print(f"- 2021 carbon intensity: {intensities[2021]:.6f}")
print(f"- 2021 deviation: {abs(intensities[2021] - median_intensity):.6f}")
print(f"- Should 2021 be outlier? {abs(intensities[2021] - median_intensity) > threshold_3mad}")