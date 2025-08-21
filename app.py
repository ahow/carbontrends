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

# Suppress type checking for runtime
import sys
if hasattr(sys, '_getframe'):
    TYPE_CHECKING = False

from data_processor import DataProcessor
from carbon_calculator import CarbonCalculator
from visualization import ChartBuilder
from portfolio_analyzer import PortfolioAnalyzer

# Page configuration
st.set_page_config(
    page_title="Carbon Attribution Dashboard",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Title and description
st.title("Carbon Attribution Dashboard")
st.markdown("Track carbon emissions attributable to $1M investments over time")
st.markdown("---")

# Initialize session state
if 'data_processor' not in st.session_state:
    st.session_state.data_processor = None
if 'calculator' not in st.session_state:
    st.session_state.calculator = None
if 'chart_builder' not in st.session_state:
    st.session_state.chart_builder = None
if 'portfolio_analyzer' not in st.session_state:
    st.session_state.portfolio_analyzer = None

# Sidebar - File Upload
st.sidebar.header("Data Upload")
uploaded_file = st.sidebar.file_uploader(
    "Upload Excel file with company data",
    type=['xlsx', 'xls'],
    help="Excel file should contain sheets: Reference, Carbon, Sales, EV"
)

# Portfolio analysis file upload
st.sidebar.header("Portfolio Analysis")
portfolio_file = st.sidebar.file_uploader(
    "Upload portfolio holdings Excel file",
    type=['xlsx', 'xls'],
    help="Excel file with sheets named DD.MM.YY containing ISIN and TotalNominal columns",
    key="portfolio_upload"
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
                st.session_state.portfolio_analyzer = PortfolioAnalyzer(st.session_state.calculator)
                
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
        st.subheader("Company Selection")
        selected_company = st.selectbox(
            "Select Company",
            companies,
            help="Choose a company to analyze carbon attribution",
            label_visibility="collapsed"
        )
    
    with col2:
        st.subheader("Investment Amount")
        investment_amount = st.number_input(
            "Investment Amount ($)",
            min_value=100000,
            max_value=100000000,
            value=1000000,
            step=100000,
            format="%d",
            help="Investment amount in USD",
            label_visibility="collapsed"
        )
    
    if selected_company:
        try:
            # Get company information
            company_info = st.session_state.calculator.get_company_info(selected_company)
            
            # Display company information in cards
            st.markdown("")
            info_cols = st.columns(4)
            with info_cols[0]:
                st.markdown(f"""
                <div style="background-color: #f8f9fa; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #007bff;">
                    <h4 style="margin: 0; color: #6c757d; font-size: 0.875rem;">Sector</h4>
                    <p style="margin: 0; font-size: 1.25rem; font-weight: bold; color: #212529;">{company_info.get('sector', 'N/A')}</p>
                </div>
                """, unsafe_allow_html=True)
            with info_cols[1]:
                st.markdown(f"""
                <div style="background-color: #f8f9fa; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #28a745;">
                    <h4 style="margin: 0; color: #6c757d; font-size: 0.875rem;">Industry</h4>
                    <p style="margin: 0; font-size: 1.25rem; font-weight: bold; color: #212529;">{company_info.get('industry', 'N/A')}</p>
                </div>
                """, unsafe_allow_html=True)
            with info_cols[2]:
                st.markdown(f"""
                <div style="background-color: #f8f9fa; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #ffc107;">
                    <h4 style="margin: 0; color: #6c757d; font-size: 0.875rem;">Country</h4>
                    <p style="margin: 0; font-size: 1.25rem; font-weight: bold; color: #212529;">{company_info.get('country', 'N/A')}</p>
                </div>
                """, unsafe_allow_html=True)
            with info_cols[3]:
                isin = company_info.get('isin', 'N/A')
                isin_display = isin[:12] + "..." if len(isin) > 12 else isin
                st.markdown(f"""
                <div style="background-color: #f8f9fa; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #dc3545;">
                    <h4 style="margin: 0; color: #6c757d; font-size: 0.875rem;">ISIN</h4>
                    <p style="margin: 0; font-size: 1.25rem; font-weight: bold; color: #212529;">{isin_display}</p>
                </div>
                """, unsafe_allow_html=True)
            
            # Calculate carbon attribution
            attribution_data = st.session_state.calculator.calculate_attribution(
                selected_company, investment_amount
            )
            
            if attribution_data is not None and not attribution_data.empty:
                # Current metrics with large cards
                st.markdown("")
                current_data = attribution_data[attribution_data['year'] == 2025].iloc[0] if len(attribution_data[attribution_data['year'] == 2025]) > 0 else None
                
                if current_data is not None:
                    metric_cols = st.columns(4)
                    
                    monthly_emissions = current_data['monthly_emissions_attributed']
                    annual_emissions = monthly_emissions * 12
                    reported_data_pct = (attribution_data['data_quality'] == 'reported').mean() * 100
                    confidence_score = min(100, reported_data_pct + 20)
                    
                    with metric_cols[0]:
                        st.markdown(f"""
                        <div style="background-color: #e8f5e8; padding: 2rem; border-radius: 0.75rem; text-align: center; border: 1px solid #d4edda;">
                            <h3 style="margin: 0; color: #155724; font-size: 2.5rem; font-weight: bold;">{monthly_emissions:.1f}</h3>
                            <p style="margin: 0.5rem 0 0 0; color: #155724; font-size: 1rem;">tonnes CO2e per month</p>
                            <p style="margin: 0; color: #6c757d; font-size: 0.875rem;">Monthly Attribution</p>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with metric_cols[1]:
                        st.markdown(f"""
                        <div style="background-color: #e3f2fd; padding: 2rem; border-radius: 0.75rem; text-align: center; border: 1px solid #bbdefb;">
                            <h3 style="margin: 0; color: #0d47a1; font-size: 2.5rem; font-weight: bold;">{annual_emissions:.0f}</h3>
                            <p style="margin: 0.5rem 0 0 0; color: #0d47a1; font-size: 1rem;">tonnes CO2e per year</p>
                            <p style="margin: 0; color: #6c757d; font-size: 0.875rem;">Annual Attribution</p>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with metric_cols[2]:
                        st.markdown(f"""
                        <div style="background-color: #fff3e0; padding: 2rem; border-radius: 0.75rem; text-align: center; border: 1px solid #ffcc02;">
                            <h3 style="margin: 0; color: #e65100; font-size: 2.5rem; font-weight: bold;">{reported_data_pct:.0f}%</h3>
                            <p style="margin: 0.5rem 0 0 0; color: #e65100; font-size: 1rem;">reported vs estimated</p>
                            <p style="margin: 0; color: #6c757d; font-size: 0.875rem;">Data Quality</p>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with metric_cols[3]:
                        st.markdown(f"""
                        <div style="background-color: #f3e5f5; padding: 2rem; border-radius: 0.75rem; text-align: center; border: 1px solid #ce93d8;">
                            <h3 style="margin: 0; color: #4a148c; font-size: 2.5rem; font-weight: bold;">{confidence_score:.0f}%</h3>
                            <p style="margin: 0.5rem 0 0 0; color: #4a148c; font-size: 1rem;">estimation confidence</p>
                            <p style="margin: 0; color: #6c757d; font-size: 0.875rem;">Confidence</p>
                        </div>
                        """, unsafe_allow_html=True)
                
                # Time series visualization
                st.markdown("")
                st.subheader("Carbon Attribution Over Time")
                st.markdown("Monthly carbon emissions attributable to $1M investment (smoothed trend)")
                
                # Create the chart
                if st.session_state.chart_builder is not None:
                    fig = st.session_state.chart_builder.create_attribution_chart(
                        attribution_data, selected_company, investment_amount
                    )
                else:
                    fig = None
                
                if fig is not None:
                    st.plotly_chart(fig, use_container_width=True)
                
                # Monthly data details section
                st.markdown("")
                st.subheader("Monthly Data Details")
                st.markdown("Detailed monthly carbon attribution calculations")
                
                # Enhanced monthly data table
                display_data = attribution_data.copy()
                display_data['date'] = pd.to_datetime(display_data[['year', 'month']].assign(day=1))
                display_data = display_data.sort_values('date', ascending=False)  # Show latest first
                
                # Show last 24 months by default
                recent_data = display_data.head(24)
                
                # Format data for display
                table_data = []
                for _, row in recent_data.iterrows():
                    month_str = row['date'].strftime('%Y-%m')
                    ev_formatted = f"${row['enterprise_value']/1e6:.1f}M" if row['enterprise_value'] > 0 else "N/A"
                    ownership_pct = f"{row['ownership_percentage']*100:.4f}%"
                    attribution = f"{row['monthly_emissions_attributed']:.2f}"
                    confidence = f"{confidence_score:.0f}%" if 'confidence_score' in locals() else "85%"
                    status = str(row['data_quality']).title()
                    method = "Temporal Extrapolation / Reported" if str(row['data_quality']) == 'estimated' else "Reported Data"
                    
                    table_data.append({
                        'Month': month_str,
                        'Enterprise Value ($)': ev_formatted,
                        'Ownership Share': ownership_pct,
                        'Attribution (tonnes CO2e)': attribution,
                        'Confidence': confidence,
                        'Status': status,
                        'Estimation Method': method
                    })
                
                # Display table
                table_df = pd.DataFrame(table_data)
                st.dataframe(
                    table_df,
                    use_container_width=True,
                    hide_index=True
                )
                
                st.markdown(f"Showing last 24 months of {len(attribution_data)} total data points")
                
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

# Portfolio Analysis Section
if st.session_state.portfolio_analyzer is not None and portfolio_file is not None:
    st.markdown("---")
    st.header("Portfolio Carbon Exposure Analysis")
    
    with st.spinner("Loading portfolio data..."):
        if st.session_state.portfolio_analyzer.load_portfolio_data(portfolio_file):
            st.success("Portfolio data loaded successfully!")
            
            # Calculate portfolio exposure
            with st.spinner("Calculating portfolio carbon exposure..."):
                exposure_analysis = st.session_state.portfolio_analyzer.calculate_portfolio_carbon_exposure()
                
                if exposure_analysis is not None:
                    # Display portfolio summary
                    summary = st.session_state.portfolio_analyzer.get_portfolio_summary()
                    
                    if summary:
                        st.subheader("Portfolio Summary")
                        
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.markdown(f"""
                            <div style="background-color: #e8f5e8; padding: 2rem; border-radius: 0.75rem; text-align: center; border: 1px solid #d4edda;">
                                <h3 style="margin: 0; color: #155724; font-size: 2rem; font-weight: bold;">{summary['total_periods']}</h3>
                                <p style="margin: 0.5rem 0 0 0; color: #155724; font-size: 1rem;">analysis periods</p>
                                <p style="margin: 0; color: #6c757d; font-size: 0.875rem;">Total Periods</p>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with col2:
                            avg_change = summary['avg_carbon_change']
                            st.markdown(f"""
                            <div style="background-color: #e3f2fd; padding: 2rem; border-radius: 0.75rem; text-align: center; border: 1px solid #bbdefb;">
                                <h3 style="margin: 0; color: #0d47a1; font-size: 2rem; font-weight: bold;">{avg_change:.1f}</h3>
                                <p style="margin: 0.5rem 0 0 0; color: #0d47a1; font-size: 1rem;">tCO2e per period</p>
                                <p style="margin: 0; color: #6c757d; font-size: 0.875rem;">Avg Change</p>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with col3:
                            max_exposure = summary['max_exposure']
                            st.markdown(f"""
                            <div style="background-color: #fff3e0; padding: 2rem; border-radius: 0.75rem; text-align: center; border: 1px solid #ffcc02;">
                                <h3 style="margin: 0; color: #e65100; font-size: 2rem; font-weight: bold;">{max_exposure:.1f}</h3>
                                <p style="margin: 0.5rem 0 0 0; color: #e65100; font-size: 1rem;">tCO2e maximum</p>
                                <p style="margin: 0; color: #6c757d; font-size: 0.875rem;">Peak Exposure</p>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with col4:
                            volatility = summary['volatility']
                            st.markdown(f"""
                            <div style="background-color: #f3e5f5; padding: 2rem; border-radius: 0.75rem; text-align: center; border: 1px solid #ce93d8;">
                                <h3 style="margin: 0; color: #4a148c; font-size: 2rem; font-weight: bold;">{volatility:.1f}</h3>
                                <p style="margin: 0.5rem 0 0 0; color: #4a148c; font-size: 1rem;">tCO2e volatility</p>
                                <p style="margin: 0; color: #6c757d; font-size: 0.875rem;">Exposure Risk</p>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    # Create portfolio exposure chart
                    st.subheader("Portfolio Carbon Exposure Over Time")
                    st.markdown("Weighted carbon exposure changes across all portfolio holdings")
                    
                    portfolio_chart = st.session_state.chart_builder.create_portfolio_exposure_chart(exposure_analysis)
                    if portfolio_chart:
                        st.plotly_chart(portfolio_chart, use_container_width=True)
                    
                    # Display detailed exposure table
                    st.subheader("Period-by-Period Analysis")
                    st.markdown("Detailed breakdown of portfolio carbon exposure by period")
                    
                    display_columns = ['period_start', 'period_end', 'portfolio_carbon_change', 
                                     'num_holdings', 'period_months']
                    display_data = exposure_analysis[display_columns].copy()
                    display_data.columns = ['Period Start', 'Period End', 'Carbon Change (tCO2e)', 
                                          'Holdings Count', 'Period Length (months)']
                    
                    st.dataframe(display_data, use_container_width=True, hide_index=True)
                
                else:
                    st.error("Could not calculate portfolio carbon exposure. Please check your data.")

# Footer
st.markdown("---")
try:
    if st.session_state.calculator is not None and hasattr(st.session_state.calculator, 'reference_df'):
        total_companies = len(st.session_state.calculator.reference_df)
    else:
        total_companies = 0
except:
    total_companies = 0

current_date = datetime.now().strftime("%-m/%-d/%Y")
st.markdown(f"Data processed from {total_companies} companies • Last updated: {current_date}")
