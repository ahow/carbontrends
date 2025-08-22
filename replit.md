# Carbon Attribution Dashboard

## Overview

This is a Streamlit-based carbon emissions attribution dashboard that analyzes the carbon footprint attributable to $1M investments across companies. The application processes financial and emissions data from Excel files to calculate and visualize carbon attribution over time with smooth temporal trends and data quality transparency. Users can upload company data or work with sample data to explore carbon attribution patterns across different investments.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
The application uses Streamlit as the web framework with a modern multi-tab interface featuring:
- **Tab 1 - About**: Application overview, features explanation, and getting started guide
- **Tab 2 - Data Upload**: Carbon data and portfolio file upload with persistent storage
- **Tab 3 - Company Analysis**: Individual company carbon attribution analysis and investment calculations
- **Tab 4 - Portfolio Analysis**: Portfolio-level carbon exposure tracking and aggregated portfolio analysis
- **Tab 5 - Portfolio Library**: Complete portfolio management with create/update/delete operations
- **Tab 6 - System Status**: Health monitoring, error messages, and maintenance tools
- Interactive visualizations using Plotly for charts and graphs
- Wide layout configuration optimized for data visualization
- Persistent data storage across sessions

### Backend Architecture
The system follows a modular architecture with three main processing classes:

**DataProcessor**: Handles Excel file ingestion and validation, requiring four specific sheets (Reference, Carbon, Sales, EV). Processes and validates data structure before making it available to other components.

**CarbonCalculator**: Core business logic component that calculates carbon attribution for investments. Handles temporal data processing, company metadata retrieval, and performs the mathematical calculations to determine carbon footprint per investment dollar.

**ChartBuilder**: Visualization engine using Plotly to create interactive time-series charts. Handles chart styling, data presentation, and provides visual feedback on data quality and trends.

### Data Processing Pipeline
The system processes data through a sequential pipeline:
1. Excel file upload and sheet validation
2. Data preprocessing and cleaning for each required sheet
3. Company selection and metadata extraction
4. Carbon attribution calculations with temporal smoothing
5. Interactive visualization generation

### Session State Management
Uses Streamlit's session state to maintain component instances across user interactions, ensuring data persistence during dashboard navigation and reducing redundant processing.

## External Dependencies

### Core Libraries
- **Streamlit**: Web application framework for the dashboard interface
- **Pandas**: Data manipulation and analysis for Excel processing
- **NumPy**: Numerical computations for carbon calculations
- **Plotly**: Interactive visualization library for charts and graphs
- **SciPy**: Scientific computing library used for interpolation and data smoothing

### Data Sources
- **Excel Files**: Primary data input requiring structured sheets for Reference, Carbon, Sales, and EV data
- **Sample Data**: Built-in fallback data when no file is uploaded

### File Processing
- **OpenPyXL**: Excel file reading engine for processing .xlsx and .xls formats
- **IO Operations**: In-memory file handling for uploaded Excel documents