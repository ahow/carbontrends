import numpy as np

# 3M carbon intensity data from the user's screenshot
# Units are different but values match console output patterns
carbon_intensities = [275, 215, 233, 206, 221, 258, 208, 186, 199, 154, 203, 181, 154, 129, 113, 112]
years = [2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023]

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