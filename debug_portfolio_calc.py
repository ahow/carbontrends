import pandas as pd
import numpy as np
from data_processor import DataProcessor
from carbon_calculator import CarbonCalculator
from portfolio_analyzer import PortfolioAnalyzer
from datetime import datetime

# Load the data
processor = DataProcessor()
with open('attached_assets/CarbonAlphaHC_1755798308840.xlsx', 'rb') as f:
    data = processor.load_excel_data(f)

# Initialize calculator
calculator = CarbonCalculator(data)

# Get 3M carbon attribution for 2020
attribution_3m = calculator.calculate_attribution('3M', 1000000)

print("=== 3M Carbon Attribution Data ===")
if attribution_3m is not None:
    # Filter for 2020 April and July
    april_2020 = attribution_3m[(attribution_3m['year'] == 2020) & (attribution_3m['month'] == 4)]
    july_2020 = attribution_3m[(attribution_3m['year'] == 2020) & (attribution_3m['month'] == 7)]
    
    print("\nApril 2020 data:")
    if not april_2020.empty:
        row = april_2020.iloc[0]
        print(f"  Carbon Intensity: {row['carbon_intensity']:.6f} tCO2e/USD")
        print(f"  Monthly Emissions Attributed: {row['monthly_emissions_attributed']:.2f} tCO2e")
        print(f"  EV: {row['ev']:.0f} USD")
        print(f"  Carbon Emissions: {row['carbon_emissions']:.0f} tCO2e")
    else:
        print("  No data found")
    
    print("\nJuly 2020 data:")
    if not july_2020.empty:
        row = july_2020.iloc[0]
        print(f"  Carbon Intensity: {row['carbon_intensity']:.6f} tCO2e/USD")
        print(f"  Monthly Emissions Attributed: {row['monthly_emissions_attributed']:.2f} tCO2e")
        print(f"  EV: {row['ev']:.0f} USD")
        print(f"  Carbon Emissions: {row['carbon_emissions']:.0f} tCO2e")
    else:
        print("  No data found")
    
    if not april_2020.empty and not july_2020.empty:
        april_intensity = april_2020.iloc[0]['carbon_intensity']
        july_intensity = july_2020.iloc[0]['carbon_intensity']
        intensity_change = july_intensity - april_intensity
        print(f"\nCalculated Intensity Change: {july_intensity:.6f} - {april_intensity:.6f} = {intensity_change:.6f} tCO2e/USD")
        print(f"For $1M investment: {intensity_change * 1000000:.2f} tCO2e")
        
        april_monthly = april_2020.iloc[0]['monthly_emissions_attributed']
        july_monthly = july_2020.iloc[0]['monthly_emissions_attributed']
        monthly_change = july_monthly - april_monthly
        print(f"\nCurrent Portfolio Calculation (monthly emissions change): {july_monthly:.2f} - {april_monthly:.2f} = {monthly_change:.2f} tCO2e")

# Now test portfolio analyzer
print("\n=== Portfolio Analyzer Test ===")
# Create a simple portfolio with 100% 3M
portfolio_data = {
    'Date': [datetime(2020, 4, 1), datetime(2020, 7, 1)],
    'ISIN': ['US88579Y1010', 'US88579Y1010'],  # 3M ISIN
    'TotalNominal': [1000000, 1000000]
}
portfolio_df = pd.DataFrame(portfolio_data)

# Initialize portfolio analyzer
analyzer = PortfolioAnalyzer(calculator)
analyzer.load_portfolio_data(portfolio_df)

# Calculate exposure
exposure = analyzer.calculate_portfolio_carbon_exposure()
if exposure is not None and not exposure.empty:
    print("\nPortfolio exposure results:")
    for _, row in exposure.iterrows():
        print(f"Period: {row['period_start']} to {row['period_end']}")
        print(f"Carbon Change: {row['portfolio_carbon_change']:.2f} tCO2e")
        print(f"Number of holdings: {row['num_holdings']}")
else:
    print("No portfolio exposure calculated")