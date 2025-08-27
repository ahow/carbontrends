#!/usr/bin/env python3
import numpy as np
from typing import Dict, List, Tuple

def enhanced_estimate_missing_intensities(intensity_data: Dict, company_name: str) -> None:
    """
    Enhanced estimation methodology based on accuracy evaluation results.
    
    Key improvements:
    1. Adaptive polynomial vs linear fitting based on data volatility
    2. Improved capping strategy for middle years vs extrapolation
    3. Better handling of companies with different trend patterns
    """
    
    # Get valid intensities for interpolation
    valid_years = []
    valid_intensities = []
    
    for year_int in sorted(intensity_data.keys()):
        data = intensity_data[year_int]
        if data['intensity'] is not None and not data.get('is_outlier', False):
            valid_years.append(year_int)
            valid_intensities.append(data['intensity'])
    
    if len(valid_intensities) < 2:
        # Use fallback for insufficient data
        _fallback_estimation(intensity_data, valid_intensities, company_name)
        return
    
    valid_years_array = np.array(valid_years)
    valid_intensities_array = np.array(valid_intensities)
    
    # Determine best fitting approach based on data characteristics
    model_type, model_params = _select_optimal_model(valid_years_array, valid_intensities_array)
    
    print(f"Enhanced estimation for {company_name}: using {model_type} model")
    
    # Apply estimation to missing years
    for year_int, data in intensity_data.items():
        if data['intensity'] is None and data['sales'] is not None:
            estimated_intensity = _estimate_year(
                year_int, valid_years_array, valid_intensities_array, 
                model_type, model_params, company_name
            )
            
            intensity_data[year_int]['intensity'] = estimated_intensity
            print(f"Enhanced estimate for {company_name} year {year_int}: {estimated_intensity:.6f} tCO2e/USD")

def _select_optimal_model(years: np.ndarray, intensities: np.ndarray) -> Tuple[str, Dict]:
    """Select optimal estimation model based on data characteristics."""
    
    # Calculate data volatility (coefficient of variation)
    cv = np.std(intensities) / np.mean(intensities) if np.mean(intensities) > 0 else 0
    
    # Calculate trend strength
    linear_fit = np.polyfit(years, intensities, 1)
    linear_pred = np.polyval(linear_fit, years)
    linear_r2 = 1 - np.sum((intensities - linear_pred)**2) / np.sum((intensities - np.mean(intensities))**2)
    
    # Decision logic based on evaluation results
    if len(intensities) >= 5 and cv > 0.3 and linear_r2 < 0.7:
        # High volatility, poor linear fit -> try quadratic
        quad_fit = np.polyfit(years, intensities, 2)
        quad_pred = np.polyval(quad_fit, years)
        quad_r2 = 1 - np.sum((intensities - quad_pred)**2) / np.sum((intensities - np.mean(intensities))**2)
        
        if quad_r2 > linear_r2 + 0.1:  # Significant improvement
            return "quadratic", {"coeffs": quad_fit, "r2": quad_r2}
    
    # Default to linear (which performed well in evaluation)
    return "linear", {"coeffs": linear_fit, "r2": linear_r2}

def _estimate_year(year: int, valid_years: np.ndarray, valid_intensities: np.ndarray,
                  model_type: str, model_params: Dict, company_name: str) -> float:
    """Estimate intensity for a specific year using selected model."""
    
    median_intensity = np.median(valid_intensities)
    is_extrapolation = year < np.min(valid_years) or year > np.max(valid_years)
    
    # Base estimation
    if model_type == "quadratic":
        estimated = np.polyval(model_params["coeffs"], year)
    else:  # linear
        estimated = np.polyval(model_params["coeffs"], year)
    
    # Adaptive capping based on evaluation findings
    if is_extrapolation:
        # Stricter caps for extrapolation (evaluation showed these are more error-prone)
        cap_factor = 1.5 if model_params.get("r2", 0) > 0.8 else 1.25
        lower_bound = median_intensity * (1.0 / cap_factor)
        upper_bound = median_intensity * cap_factor
    else:
        # More lenient for interpolation (evaluation showed these are more accurate)
        cap_factor = 2.0
        lower_bound = median_intensity * (1.0 / cap_factor)
        upper_bound = median_intensity * cap_factor
    
    # Apply capping
    capped_estimate = np.clip(estimated, lower_bound, upper_bound)
    
    # Additional business logic constraints
    if capped_estimate <= 0:
        capped_estimate = median_intensity * 0.5  # Minimum reasonable value
    
    return capped_estimate

def _fallback_estimation(intensity_data: Dict, valid_intensities: List, company_name: str):
    """Fallback estimation for insufficient data."""
    if len(valid_intensities) == 1:
        default_intensity = valid_intensities[0]
    else:
        # Industry default based on evaluation results
        default_intensity = 0.0001  # 0.1 tCO2e per $1000 sales
    
    for year_int, data in intensity_data.items():
        if data['intensity'] is None and data['sales'] is not None:
            intensity_data[year_int]['intensity'] = default_intensity
            print(f"Fallback estimate for {company_name} year {year_int}: {default_intensity:.6f} tCO2e/USD")

# Test the enhanced methodology
def test_enhanced_methodology():
    """Test enhanced methodology against the same test cases."""
    print("=== TESTING ENHANCED METHODOLOGY ===")
    
    # Test case: Apple (showed 11.9% avg error with current method)
    apple_intensities = {
        2019: 97.242615, 2020: 83.055571, 2021: 60.412720, 
        2022: 53.001562, 2023: 51.397785, 2024: 47.314578, 2025: 42.195122
    }
    
    # Test hiding 2021 (showed +21.1% error)
    test_data = {k: v for k, v in apple_intensities.items() if k != 2021}
    years_array = np.array(list(test_data.keys()))
    values_array = np.array(list(test_data.values()))
    
    model_type, model_params = _select_optimal_model(years_array, values_array)
    estimated_2021 = _estimate_year(2021, years_array, values_array, model_type, model_params, "Apple Test")
    actual_2021 = apple_intensities[2021]
    error = (estimated_2021 - actual_2021) / actual_2021 * 100
    
    print(f"Apple 2021 - Enhanced method:")
    print(f"  Actual: {actual_2021:.6f}")
    print(f"  Enhanced Estimate: {estimated_2021:.6f}")
    print(f"  Error: {error:+.1f}% (vs +21.1% with current method)")
    
    # Test similar for other high-error cases
    return estimated_2021, error

if __name__ == "__main__":
    test_enhanced_methodology()