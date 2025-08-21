import pandas as pd
import sys

def inspect_excel_file(file_path):
    """Inspect the structure of the user's Excel file."""
    try:
        # Read all sheets
        excel_data = pd.read_excel(file_path, sheet_name=None, engine='openpyxl')
        
        print(f"Excel file: {file_path}")
        print(f"Number of sheets: {len(excel_data)}")
        print("\nSheet names:")
        for sheet_name in excel_data.keys():
            print(f"  - {sheet_name}")
        
        print("\nSheet details:")
        for sheet_name, df in excel_data.items():
            print(f"\n=== {sheet_name} ===")
            print(f"Shape: {df.shape}")
            print(f"Columns: {list(df.columns)}")
            
            if len(df) > 0:
                print("First few rows:")
                print(df.head(3).to_string())
            else:
                print("No data in this sheet")
        
        return excel_data
        
    except Exception as e:
        print(f"Error reading Excel file: {str(e)}")
        return None

if __name__ == "__main__":
    file_path = sys.argv[1] if len(sys.argv) > 1 else "attached_assets/CarbonAlphaHC_1755798308840.xlsx"
    inspect_excel_file(file_path)