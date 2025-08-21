import pandas as pd
import numpy as np

# Create sample data matching the expected Excel structure
def create_sample_excel():
    # Sample companies with realistic data
    companies = [
        {'ISIN': 'US88579Y1010', 'Company': '3M Company', 'Sector': 'Industrial', 
         'Subsector': 'Industrial Conglomerates', 'Industry': 'Industrial Machinery', 
         'Subindustry': 'Diversified Manufacturing', 'Country': 'United States'},
        {'ISIN': 'DE0005545503', 'Company': '1&1 AG', 'Sector': 'Telecommunications', 
         'Subsector': 'Telecom Services', 'Industry': 'Internet Services', 
         'Subindustry': 'Internet Service Providers', 'Country': 'Germany'},
        {'ISIN': 'US0378331005', 'Company': 'Apple Inc', 'Sector': 'Technology', 
         'Subsector': 'Technology Hardware', 'Industry': 'Consumer Electronics', 
         'Subindustry': 'Smartphones & Tablets', 'Country': 'United States'},
        {'ISIN': 'US5949181045', 'Company': 'Microsoft Corporation', 'Sector': 'Technology', 
         'Subsector': 'Software', 'Industry': 'Application Software', 
         'Subindustry': 'Systems Software', 'Country': 'United States'},
        {'ISIN': 'US00206R1023', 'Company': 'AT&T Inc', 'Sector': 'Telecommunications', 
         'Subsector': 'Telecom Services', 'Industry': 'Wireless Telecom', 
         'Subindustry': 'Wireless Networks', 'Country': 'United States'}
    ]
    
    # Create Reference sheet
    reference_df = pd.DataFrame(companies)
    
    years = ['2019', '2020', '2021', '2022', '2023', '2024', '2025']
    
    # Create Carbon emissions data (in tonnes CO2e annually)
    carbon_data = {
        'ISIN': [c['ISIN'] for c in companies],
        '2019': [234000, 890, 25300000, 11600000, 31000000],  # 3M, 1&1, Apple, Microsoft, AT&T
        '2020': [220000, 920, 22800000, 10800000, 29500000],
        '2021': [210000, 950, 22100000, 10200000, 28200000],
        '2022': [198000, 980, 20900000, 9800000, 26800000],
        '2023': [185000, 1020, 19700000, 9500000, 25500000],
        '2024': [175000, 1050, 18500000, 9200000, 24200000],
        '2025': [165000, 1080, 17300000, 8900000, 23000000]
    }
    carbon_df = pd.DataFrame(carbon_data)
    
    # Create Sales data (in USD millions annually)
    sales_data = {
        'ISIN': [c['ISIN'] for c in companies],
        '2019': [32136, 4200, 260174, 125843, 181193],  # 3M, 1&1, Apple, Microsoft, AT&T
        '2020': [32184, 4350, 274515, 143015, 171760],
        '2021': [35355, 4500, 365817, 168088, 168864],
        '2022': [34229, 4680, 394328, 198270, 120741],
        '2023': [32681, 4820, 383285, 211915, 122425],
        '2024': [33200, 4950, 391000, 245122, 125000],
        '2025': [34000, 5100, 410000, 260000, 128000]
    }
    sales_df = pd.DataFrame(sales_data)
    
    # Create Enterprise Value data (in USD millions)
    ev_data = {
        'ISIN': [c['ISIN'] for c in companies],
        '2019': [98000, 4200, 1100000, 1050000, 230000],  # 3M, 1&1, Apple, Microsoft, AT&T
        '2020': [105000, 4100, 2000000, 1600000, 200000],
        '2021': [115000, 4000, 2800000, 2200000, 210000],
        '2022': [95000, 3900, 2300000, 1800000, 180000],
        '2023': [85000, 3800, 2900000, 2800000, 160000],
        '2024': [74000, 3700, 3400000, 3100000, 155000],
        '2025': [70000, 3600, 3500000, 3200000, 150000]
    }
    ev_df = pd.DataFrame(ev_data)
    
    # Create Excel file with multiple sheets
    with pd.ExcelWriter('sample_data.xlsx', engine='openpyxl') as writer:
        reference_df.to_excel(writer, sheet_name='Reference', index=False)
        carbon_df.to_excel(writer, sheet_name='Carbon', index=False)
        sales_df.to_excel(writer, sheet_name='Sales', index=False)
        ev_df.to_excel(writer, sheet_name='EV', index=False)
    
    print("Sample Excel file created successfully!")
    return reference_df, carbon_df, sales_df, ev_df

if __name__ == "__main__":
    create_sample_excel()