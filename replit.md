# Carbon Attribution Dashboard

## Overview

This is a Streamlit-based carbon emissions attribution dashboard that analyzes the carbon footprint attributable to $1M investments across companies. The application processes financial and emissions data from Excel files to calculate and visualize carbon attribution over time with smooth temporal trends and data quality transparency. Users can upload company data or work with sample data to explore carbon attribution patterns across different investments.

## Recent Changes (June 2026)

- **Validated estimation methodology** (`methodology.py`): the carbon-intensity pipeline was reworked and validated offline against real data before going live. It removes one-off spikes, fills interior gaps with shape-preserving log-space PCHIP interpolation, and projects forward years by blending each company's own trend toward its subsector's trend (the further out, the more weight on the sector). Every estimate is capped against the company's typical level.
- **Measured improvement**: on a backtest that hides recent years and checks the guess (7,134 companies, no data leakage), the typical error on next-year estimates dropped from ~29% to ~16%, and the worst-case average (the "tail") fell from several hundred percent to ~60%. Interior-gap accuracy improved from ~17% to ~11%.
- **Forward nowcasting**: company charts now extend through the current year (2026). Sales are held flat for projected years (conservative) while the validated trend drives carbon intensity.
- **Smoother, safe monthly curve**: monthly smoothing now uses log-space PCHIP instead of a cubic spline, which avoids the overshoot/negative dips a spline can produce, while still preserving exact annual totals via proportional scaling.
- **Confidence bands**: charts show a shaded band around the trend that widens for estimated and further-out years, reflecting measured uncertainty by horizon.
- **Validation harness** (`backtest_methodology.py`): a reproducible offline tool that loads the real dataset and reports error by horizon for each methodology variant; the production path shares the exact same code so results match the validation.

## Earlier Changes (January 2025)

- **Enhanced Tab Structure**: Reorganized application into 6 logical tabs (About, Data Upload, Company Analysis, Portfolio Analysis, Portfolio Library, System Status) for improved user workflow.
- **Improved Data Processing**: Enhanced upload error handling and progress indicators to prevent "stuck on processing" issues.

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

**CarbonCalculator**: Core business logic component that calculates carbon attribution for investments. Uses cubic spline interpolation through annual data midpoints with constraint satisfaction to create smooth monthly estimates. Handles temporal data processing, company metadata retrieval, and performs the mathematical calculations to determine carbon footprint per investment dollar.

**ChartBuilder**: Visualization engine using Plotly to create interactive time-series charts. Displays smooth monthly carbon attribution trends (green lines) and flat annual step functions (blue lines). Handles chart styling, data presentation, and provides visual feedback on data quality and trends.

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