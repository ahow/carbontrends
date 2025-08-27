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

# Calculate carbon intensities (tCO2e per USD)
carbon_intensities = []
years = []
for year in sorted(carbon_data.keys()):
    if year in sales_data and sales_data[year] > 0:
        intensity = carbon_data[year] / sales_data[year]
        carbon_intensities.append(intensity)
        years.append(year)
        
print("=== CALCULATED CARBON INTENSITIES ===")
for year, intensity in zip(years, carbon_intensities):
    print(f"  {year}: {intensity:.6f} tCO2e/USD")

print("=== 3M OUTLIER DETECTION ANALYSIS ===")
print("Raw carbon intensity data:")
for year, intensity in zip(years, carbon_intensities):
    print(f"  {year}: {intensity}")

# Convert to numpy array for calculations
intensities_array = np.array(carbon_intensities)

# Calculate median and MAD (exactly as in the code)
median_intensity = np.median(intensities_array)
mad_intensity = np.median(np.abs(intensities_array - median_intensity))

print(f"\nStatistical measures:")
print(f"  Median carbon intensity: {median_intensity:.1f}")
print(f"  MAD (Median Absolute Deviation): {mad_intensity:.1f}")

# Apply outlier detection thresholds
intensity_threshold = 3 * mad_intensity if mad_intensity > 0 else median_intensity * 0.1
print(f"  3-MAD threshold: {intensity_threshold:.1f}")
print(f"  5x median threshold: {median_intensity * 5:.1f}")

print(f"\nOutlier analysis:")
for year, intensity in zip(years, carbon_intensities):
    deviation = abs(intensity - median_intensity)
    is_3mad_outlier = deviation > intensity_threshold
    is_5x_outlier = intensity > (median_intensity * 5)
    is_outlier = is_3mad_outlier or is_5x_outlier
    
    status = "OUTLIER" if is_outlier else "Normal"
    print(f"  {year}: {intensity:3.0f} | Deviation: {deviation:5.1f} | 3-MAD: {is_3mad_outlier} | 5x: {is_5x_outlier} | {status}")

print(f"\nThreshold comparison:")
print(f"  Any value with deviation > {intensity_threshold:.1f} is flagged as outlier")
print(f"  Any value > {median_intensity * 5:.1f} is flagged as outlier")