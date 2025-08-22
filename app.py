"""
Carbon Attribution Dashboard - Clean Version

A Streamlit dashboard for analyzing carbon emissions attribution with portfolio management.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from typing import Dict, List, Optional, Any
import warnings
warnings.filterwarnings('ignore')

# Avoid TYPE_CHECKING imports that cause issues
import sys
if hasattr(sys, '_getframe'):
    TYPE_CHECKING = False

from data_processor import DataProcessor
from carbon_calculator import CarbonCalculator
from visualization import ChartBuilder
from portfolio_analyzer import PortfolioAnalyzer
from data_persistence import DataPersistence

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

# Navigation
st.sidebar.header("Navigation")
page = st.sidebar.radio(
    "Select Page",
    ["Dashboard", "Portfolio Library"],
    index=0
)

# Initialize session state
if 'data_processor' not in st.session_state:
    st.session_state.data_processor = None
if 'calculator' not in st.session_state:
    st.session_state.calculator = None
if 'chart_builder' not in st.session_state:
    st.session_state.chart_builder = None
if 'portfolio_analyzer' not in st.session_state:
    st.session_state.portfolio_analyzer = None
if 'data_persistence' not in st.session_state:
    st.session_state.data_persistence = DataPersistence()
if 'current_portfolio' not in st.session_state:
    st.session_state.current_portfolio = None

# Load persistent data on startup
if st.session_state.calculator is None and st.session_state.data_persistence.has_carbon_data():
    with st.spinner("Loading saved carbon data..."):
        carbon_data = st.session_state.data_persistence.load_carbon_data()
        if carbon_data:
            st.session_state.calculator = CarbonCalculator(carbon_data)
            st.session_state.chart_builder = ChartBuilder()
            st.session_state.portfolio_analyzer = PortfolioAnalyzer(st.session_state.calculator)
            
            data_info = st.session_state.data_persistence.get_carbon_data_info()
            if data_info:
                st.sidebar.success(f"✅ Loaded saved data with {data_info.get('num_companies', 0)} companies")

# Dashboard Page
if page == "Dashboard":
    # Sidebar - File Upload
    st.sidebar.header("Data Upload")
    
    # Show current data status
    if st.session_state.calculator is not None:
        data_info = st.session_state.data_persistence.get_carbon_data_info()
        if data_info:
            st.sidebar.info(f"📊 Current: {data_info.get('num_companies', 0)} companies")
    
    uploaded_file = st.sidebar.file_uploader(
        "Upload Excel file with company data",
        type=['xlsx', 'xls'],
        help="Excel file should contain sheets: Reference, Carbon, Sales, EV"
    )

    # Process carbon data when file is uploaded
    if uploaded_file is not None:
        try:
            with st.spinner("Processing carbon data..."):
                # Initialize data processor
                st.session_state.data_processor = DataProcessor()
                
                # Load and process data
                data = st.session_state.data_processor.load_excel_data(uploaded_file)
                
                if data is not None:
                    # Save data persistently
                    if st.session_state.data_persistence.save_carbon_data(data):
                        st.sidebar.success("✅ Carbon data saved successfully!")
                    
                    # Initialize calculator and chart builder
                    st.session_state.calculator = CarbonCalculator(data)
                    st.session_state.chart_builder = ChartBuilder()
                    st.session_state.portfolio_analyzer = PortfolioAnalyzer(st.session_state.calculator)
                    
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

    # Portfolio analysis file upload
    st.sidebar.header("Portfolio Analysis")
    
    # Portfolio selection
    portfolio_names = st.session_state.data_persistence.get_portfolio_names()
    if portfolio_names:
        selected_portfolio = st.sidebar.selectbox(
            "Select existing portfolio",
            ["-- None --"] + portfolio_names,
            key="portfolio_selector"
        )
        
        if selected_portfolio != "-- None --":
            st.session_state.current_portfolio = selected_portfolio
            st.sidebar.info(f"📁 Active: {selected_portfolio}")
    
    portfolio_file = st.sidebar.file_uploader(
        "Upload new portfolio data",
        type=['xlsx', 'xls'],
        help="Excel file with sheets named DD.MM.YY containing ISIN and TotalNominal columns",
        key="portfolio_upload"
    )
    
    # Portfolio name input for new uploads
    if portfolio_file is not None:
        portfolio_action = st.sidebar.radio(
            "Action",
            ["Create new portfolio", "Add to existing portfolio"],
            key="portfolio_action"
        )
        
        if portfolio_action == "Create new portfolio":
            portfolio_name = st.sidebar.text_input(
                "Portfolio name",
                key="new_portfolio_name",
                help="Enter a name for this portfolio"
            )
        else:
            if portfolio_names:
                portfolio_name = st.sidebar.selectbox(
                    "Select portfolio to update",
                    portfolio_names,
                    key="update_portfolio_name"
                )
            else:
                st.sidebar.error("No existing portfolios found. Please create a new one.")
                portfolio_name = None

        # Process portfolio data when uploaded
        if portfolio_name:
            try:
                with st.spinner("Processing portfolio data..."):
                    portfolio_data = st.session_state.data_persistence.parse_portfolio_file(portfolio_file)
                    
                    if portfolio_data:
                        if portfolio_action == "Create new portfolio":
                            if st.session_state.data_persistence.save_portfolio(portfolio_name, portfolio_data):
                                st.sidebar.success(f"✅ Portfolio '{portfolio_name}' created successfully!")
                                st.session_state.current_portfolio = portfolio_name
                            else:
                                st.sidebar.error("❌ Failed to save portfolio")
                        
                        elif portfolio_action == "Add to existing portfolio":
                            if st.session_state.data_persistence.add_data_to_portfolio(portfolio_name, portfolio_data):
                                st.sidebar.success(f"✅ Data added to portfolio '{portfolio_name}'!")
                                st.session_state.current_portfolio = portfolio_name
                            else:
                                st.sidebar.error("❌ Failed to add data to portfolio")
                    
                    else:
                        st.sidebar.error("❌ Failed to parse portfolio data")
                        
            except Exception as e:
                st.sidebar.error(f"❌ Error processing portfolio: {str(e)}")

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
                    
                    # Prepare data for export
                    export_data = attribution_data.copy()
                    export_data['date'] = pd.to_datetime(export_data[['year', 'month']].assign(day=1))
                    
                    csv_data = export_data.to_csv(index=False)
                    st.download_button(
                        label="📥 Download CSV",
                        data=csv_data,
                        file_name=f"carbon_attribution_{selected_company}_{investment_amount}.csv",
                        mime="text/csv",
                        help="Download the carbon attribution data as CSV"
                    )
                
                else:
                    st.warning("No carbon attribution data available for the selected company.")
                    
            except Exception as e:
                st.error(f"Error calculating carbon attribution: {str(e)}")
    
    else:
        # Show guidance if no data loaded
        st.info("📂 Upload an Excel file with company carbon data to get started")
        st.markdown("""
        **Required Excel sheets:**
        - **Reference**: Company information (Name, ISIN, Sector, Industry, Country)
        - **Carbon**: Annual carbon emissions data
        - **Sales**: Annual sales/revenue data  
        - **EV**: Enterprise value data
        """)
    
    # Portfolio Analysis Section
    if st.session_state.portfolio_analyzer is not None and st.session_state.current_portfolio is not None:
        st.markdown("---")
        st.header("Portfolio Carbon Exposure Analysis")
    
        # Load selected portfolio data
        portfolio_data = st.session_state.data_persistence.load_portfolio(st.session_state.current_portfolio)
        if portfolio_data:
            st.session_state.portfolio_analyzer.portfolio_data = portfolio_data
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

elif page == "Portfolio Library":
    st.header("Portfolio Library")
    st.markdown("Manage your portfolio collection and data")
    
    # Get portfolio library
    portfolio_library = st.session_state.data_persistence.load_portfolio_library()
    
    if not portfolio_library:
        st.info("No portfolios found. Upload portfolio data on the Dashboard page to get started.")
    else:
        # Display portfolio library
        st.subheader("Your Portfolios")
        
        for portfolio_name, info in portfolio_library.items():
            with st.expander(f"📁 {portfolio_name}", expanded=False):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Periods", info['num_periods'])
                    st.metric("Total Holdings", info['total_holdings'])
                
                with col2:
                    created_date = pd.to_datetime(info['created_at']).strftime('%Y-%m-%d')
                    updated_date = pd.to_datetime(info['updated_at']).strftime('%Y-%m-%d')
                    st.write(f"**Created:** {created_date}")
                    st.write(f"**Updated:** {updated_date}")
                
                with col3:
                    start_date = pd.to_datetime(info['date_range']['start']).strftime('%d.%m.%y')
                    end_date = pd.to_datetime(info['date_range']['end']).strftime('%d.%m.%y')
                    st.write(f"**Period:** {start_date} - {end_date}")
                
                # Portfolio actions
                st.markdown("---")
                action_col1, action_col2, action_col3 = st.columns(3)
                
                with action_col1:
                    if st.button(f"Select for Analysis", key=f"select_{portfolio_name}"):
                        st.session_state.current_portfolio = portfolio_name
                        st.success(f"Selected '{portfolio_name}' for analysis")
                        st.rerun()
                
                with action_col2:
                    # File uploader for adding data
                    add_data_file = st.file_uploader(
                        "Add new data",
                        type=['xlsx', 'xls'],
                        key=f"add_data_{portfolio_name}",
                        help="Upload Excel file with additional time periods"
                    )
                    
                    if add_data_file is not None:
                        with st.spinner("Adding data..."):
                            new_data = st.session_state.data_persistence.parse_portfolio_file(add_data_file)
                            if new_data:
                                if st.session_state.data_persistence.add_data_to_portfolio(portfolio_name, new_data):
                                    st.success(f"Data added to '{portfolio_name}'!")
                                    st.rerun()
                                else:
                                    st.error("Failed to add data")
                            else:
                                st.error("Failed to parse file")
                
                with action_col3:
                    if st.button(f"Delete", key=f"delete_{portfolio_name}", type="secondary"):
                        if st.session_state.data_persistence.delete_portfolio(portfolio_name):
                            st.success(f"Deleted '{portfolio_name}'")
                            if st.session_state.current_portfolio == portfolio_name:
                                st.session_state.current_portfolio = None
                            st.rerun()
                        else:
                            st.error(f"Failed to delete '{portfolio_name}'")
        
        # Bulk operations
        st.markdown("---")
        st.subheader("Bulk Operations")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Refresh Library", type="secondary"):
                st.rerun()
        
        with col2:
            if st.button("Clean Up Old Data", type="secondary"):
                st.session_state.data_persistence.cleanup_old_data()
                st.success("Cleanup completed")

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