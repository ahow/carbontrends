import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import io
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from data_processor import DataProcessor
from carbon_calculator import CarbonCalculator
from visualization import ChartBuilder

# Page configuration
st.set_page_config(
    page_title="Carbon Attribution Dashboard",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Title and description
st.title("🌱 Carbon Attribution Dashboard")
st.markdown("""
**Analyze carbon emissions attributable to $1M investments across companies**

This dashboard calculates the carbon footprint attributable to a $1M investment in each company,
providing smooth temporal trends and data quality transparency.
""")

# Initialize session state
if 'data_processor' not in st.session_state:
    st.session_state.data_processor = None
if 'calculator' not in st.session_state:
    st.session_state.calculator = None
if 'chart_builder' not in st.session_state:
    st.session_state.chart_builder = None

# Sidebar - File Upload
st.sidebar.header("📊 Data Upload")
uploaded_file = st.sidebar.file_uploader(
    "Upload Excel file with company data",
    type=['xlsx', 'xls'],
    help="Excel file should contain sheets: Reference, Carbon, Sales, EV"
)

# Load sample data if no file uploaded
if uploaded_file is None:
    st.sidebar.info("No file uploaded. Using sample data for demonstration.")
    # Note: In production, this would load actual data or show empty state
    st.sidebar.warning("⚠️ Please upload an Excel file with the required sheets to analyze real data.")

# Process data when file is uploaded
if uploaded_file is not None:
    try:
        with st.spinner("Processing data..."):
            # Initialize data processor
            st.session_state.data_processor = DataProcessor()
            
            # Load and process data
            data = st.session_state.data_processor.load_excel_data(uploaded_file)
            
            if data is not None:
                # Initialize calculator and chart builder
                st.session_state.calculator = CarbonCalculator(data)
                st.session_state.chart_builder = ChartBuilder()
                
                st.sidebar.success("✅ Data loaded successfully!")
                
                # Display data summary in sidebar
                st.sidebar.subheader("📈 Data Summary")
                companies_count = len(data['reference'])
                st.sidebar.metric("Total Companies", companies_count)
                
                # Show data date range
                carbon_data = data['carbon']
                if not carbon_data.empty:
                    years = [col for col in carbon_data.columns if str(col).isdigit()]
                    if years:
                        min_year, max_year = min(years), max(years)
                        st.sidebar.metric("Data Range", f"{min_year} - {max_year}")
                
            else:
                st.error("❌ Failed to load data. Please check your Excel file format.")
                
    except Exception as e:
        st.error(f"❌ Error processing file: {str(e)}")
        st.info("Please ensure your Excel file contains the required sheets: Reference, Carbon, Sales, EV")

# Main dashboard content
if st.session_state.calculator is not None:
    # Company selection
    companies = st.session_state.calculator.get_companies_list()
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        selected_company = st.selectbox(
            "🏢 Select Company",
            companies,
            help="Choose a company to analyze carbon attribution"
        )
    
    with col2:
        investment_amount = st.number_input(
            "💰 Investment Amount ($)",
            min_value=100000,
            max_value=100000000,
            value=1000000,
            step=100000,
            format="%d",
            help="Investment amount in USD"
        )
    
    if selected_company:
        try:
            # Get company information
            company_info = st.session_state.calculator.get_company_info(selected_company)
            
            # Display company information
            st.subheader(f"📋 Company Profile: {selected_company}")
            
            info_cols = st.columns(4)
            with info_cols[0]:
                st.metric("Sector", company_info.get('sector', 'N/A'))
            with info_cols[1]:
                st.metric("Industry", company_info.get('industry', 'N/A'))
            with info_cols[2]:
                st.metric("Country", company_info.get('country', 'N/A'))
            with info_cols[3]:
                isin = company_info.get('isin', 'N/A')
                st.metric("ISIN", isin[:12] + "..." if len(isin) > 12 else isin)
            
            # Calculate carbon attribution
            attribution_data = st.session_state.calculator.calculate_attribution(
                selected_company, investment_amount
            )
            
            if attribution_data is not None and not attribution_data.empty:
                # Current metrics
                st.subheader("📊 Current Metrics (2025)")
                
                current_data = attribution_data[attribution_data['year'] == 2025].iloc[0] if len(attribution_data[attribution_data['year'] == 2025]) > 0 else None
                
                if current_data is not None:
                    metric_cols = st.columns(4)
                    
                    with metric_cols[0]:
                        ownership_pct = current_data['ownership_percentage'] * 100
                        st.metric(
                            "Ownership Share",
                            f"{ownership_pct:.3f}%",
                            help="Percentage of company owned by $1M investment"
                        )
                    
                    with metric_cols[1]:
                        enterprise_value = current_data['enterprise_value'] / 1e6
                        st.metric(
                            "Enterprise Value",
                            f"${enterprise_value:.1f}M",
                            help="Current enterprise value in millions USD"
                        )
                    
                    with metric_cols[2]:
                        monthly_emissions = current_data['monthly_emissions_attributed']
                        st.metric(
                            "Monthly Attribution",
                            f"{monthly_emissions:.1f} tCO₂e",
                            help="Monthly carbon emissions attributed to investment"
                        )
                    
                    with metric_cols[3]:
                        annual_emissions = monthly_emissions * 12
                        st.metric(
                            "Annual Attribution",
                            f"{annual_emissions:.0f} tCO₂e",
                            help="Annual carbon emissions attributed to investment"
                        )
                
                # Time series visualization
                st.subheader("📈 Carbon Attribution Time Series")
                
                # Create the chart
                fig = st.session_state.chart_builder.create_attribution_chart(
                    attribution_data, selected_company, investment_amount
                )
                
                if fig is not None:
                    st.plotly_chart(fig, use_container_width=True)
                
                # Data quality information
                st.subheader("🔍 Data Quality Assessment")
                
                quality_cols = st.columns(2)
                
                with quality_cols[0]:
                    # Calculate confidence score
                    reported_data_pct = (attribution_data['data_quality'] == 'reported').mean() * 100
                    confidence_score = min(100, reported_data_pct + 20)  # Base confidence + reporting bonus
                    
                    st.metric(
                        "Confidence Score",
                        f"{confidence_score:.1f}%",
                        help="Overall confidence in the carbon attribution calculations"
                    )
                
                with quality_cols[1]:
                    estimated_points = (attribution_data['data_quality'] == 'estimated').sum()
                    total_points = len(attribution_data)
                    
                    st.metric(
                        "Estimated Data Points",
                        f"{estimated_points}/{total_points}",
                        help="Number of data points that are estimated vs total"
                    )
                
                # Detailed monthly data table
                with st.expander("📋 Detailed Monthly Data"):
                    # Prepare data for display
                    display_data = attribution_data.copy()
                    display_data['date'] = pd.to_datetime(display_data[['year', 'month']].assign(day=1))
                    display_data = display_data.sort_values('date')
                    
                    # Format columns for display
                    formatted_data = display_data[['date', 'monthly_emissions_attributed', 'ownership_percentage', 'data_quality', 'enterprise_value']].copy()
                    formatted_data.columns = ['Date', 'Monthly Attribution (tCO₂e)', 'Ownership %', 'Data Quality', 'Enterprise Value ($M)']
                    formatted_data['Ownership %'] = (formatted_data['Ownership %'] * 100).round(4)
                    formatted_data['Enterprise Value ($M)'] = (formatted_data['Enterprise Value ($M)'] / 1e6).round(1)
                    formatted_data['Monthly Attribution (tCO₂e)'] = formatted_data['Monthly Attribution (tCO₂e)'].round(2)
                    
                    st.dataframe(
                        formatted_data,
                        use_container_width=True,
                        hide_index=True
                    )
                
                # Download data
                st.subheader("💾 Export Data")
                
                # Prepare CSV data
                csv_data = attribution_data.copy()
                csv_data['company'] = selected_company
                csv_data['investment_amount'] = investment_amount
                
                csv_buffer = io.StringIO()
                csv_data.to_csv(csv_buffer, index=False)
                csv_string = csv_buffer.getvalue()
                
                st.download_button(
                    label="📥 Download Attribution Data (CSV)",
                    data=csv_string,
                    file_name=f"carbon_attribution_{selected_company.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    help="Download detailed carbon attribution data for further analysis"
                )
                
            else:
                st.warning(f"⚠️ No carbon attribution data available for {selected_company}")
                
        except Exception as e:
            st.error(f"❌ Error calculating carbon attribution: {str(e)}")
            st.info("Please ensure the selected company has valid data in all required sheets.")

else:
    # Empty state - no data loaded
    st.info("📁 **Please upload an Excel file to begin analysis**")
    st.markdown("""
    **Required Excel file structure:**
    - **Reference sheet**: Company metadata (ISIN, sector, industry, country)
    - **Carbon sheet**: Annual emissions data by company
    - **Sales sheet**: Annual sales data by company  
    - **EV sheet**: Enterprise value data by company
    
    **Key features:**
    - 🎯 Calculate carbon emissions per $1M investment
    - 📈 Smooth temporal visualization with spline interpolation
    - 🔍 Data quality transparency (reported vs estimated)
    - 📊 Interactive time series from 2019-2025
    - 💾 Export capabilities for further analysis
    """)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666666; font-size: 0.9em;'>
🌱 Carbon Attribution Dashboard | Built with Streamlit & Plotly
</div>
""", unsafe_allow_html=True)
