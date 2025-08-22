import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Any
import streamlit as st

class ChartBuilder:
    """Handles creation of interactive visualizations for carbon attribution data."""
    
    def __init__(self):
        self.color_palette = {
            'smooth_trend': '#2E8B57',  # Sea Green
            'reported_data': '#1f77b4',  # Blue
            'estimated_data': '#808080',  # Gray
            'background': '#ffffff',
            'grid': '#e0e0e0'
        }
    
    def create_attribution_chart(self, data: pd.DataFrame, company_name: str, 
                               investment_amount: float) -> Optional[go.Figure]:
        """
        Create the main carbon attribution time series chart.
        
        Args:
            data: Monthly attribution data
            company_name: Name of the company
            investment_amount: Investment amount in USD
            
        Returns:
            Plotly figure object
        """
        try:
            if data.empty:
                return None
            
            # Prepare data
            data_sorted = data.sort_values(['year', 'month']).copy()
            data_sorted['date'] = pd.to_datetime(data_sorted[['year', 'month']].assign(day=1))
            
            # Create figure
            fig = go.Figure()
            
            # Add smooth monthly trend line
            fig.add_trace(go.Scatter(
                x=data_sorted['date'],
                y=data_sorted['monthly_emissions_attributed'],
                mode='lines',
                name='Monthly Smooth Trend',
                line=dict(color=self.color_palette['smooth_trend'], width=3),
                hovertemplate='<b>%{x|%Y-%m}</b><br>' +
                            'Monthly Attribution: %{y:.1f} tCO₂e<br>' +
                            '<extra></extra>',
                showlegend=True
            ))
            
            # Add annual reported data points as step functions
            reported_data = self._get_annual_points(data_sorted, 'reported')
            if not reported_data.empty:
                fig.add_trace(go.Scatter(
                    x=reported_data['date'],
                    y=reported_data['monthly_emissions_attributed'],
                    mode='lines',
                    name='Annual Reported Data (Steps)',
                    line=dict(color=self.color_palette['reported_data'], width=2, shape='hv'),
                    connectgaps=False,
                    hovertemplate='<b>%{x|%Y-%m}</b><br>' +
                                'Annual Data: %{y:.1f} tCO₂e/month<br>' +
                                'Data Quality: Reported<br>' +
                                '<extra></extra>',
                    showlegend=True
                ))
            
            # Add annual estimated data points as step functions (only for years without reported data)
            estimated_data = self._get_estimated_only_points(data_sorted)
            if not estimated_data.empty:
                # Create separate traces for each continuous estimated period to avoid connecting across gaps
                self._add_estimated_traces(fig, estimated_data)
            
            # Update layout
            fig.update_layout(
                title=dict(
                    text=f"Carbon Attribution for ${investment_amount/1e6:.1f}M Investment in {company_name}",
                    x=0.5,
                    font=dict(size=16, color='#2c3e50')
                ),
                xaxis=dict(
                    title="Date",
                    showgrid=True,
                    gridcolor=self.color_palette['grid'],
                    tickformat='%Y-%m',
                    dtick='M6'  # Show ticks every 6 months
                ),
                yaxis=dict(
                    title="Monthly Carbon Attribution (tCO₂e)",
                    showgrid=True,
                    gridcolor=self.color_palette['grid'],
                    tickformat='.1f'
                ),
                plot_bgcolor='white',
                paper_bgcolor='white',
                font=dict(family="Arial", size=12),
                hovermode='x unified',
                legend=dict(
                    x=0.02,
                    y=0.98,
                    bgcolor='rgba(255,255,255,0.8)',
                    bordercolor='rgba(0,0,0,0.2)',
                    borderwidth=1
                ),
                height=500
            )
            
            # Add range selector and slider
            fig.update_layout(
                xaxis=dict(
                    rangeselector=dict(
                        buttons=list([
                            dict(count=1, label="1Y", step="year", stepmode="backward"),
                            dict(count=3, label="3Y", step="year", stepmode="backward"),
                            dict(count=5, label="5Y", step="year", stepmode="backward"),
                            dict(step="all", label="All")
                        ]),
                        bgcolor="rgba(240,240,240,0.8)",
                        bordercolor="rgba(0,0,0,0.2)",
                        borderwidth=1
                    ),
                    rangeslider=dict(
                        visible=True, 
                        thickness=0.08,
                        bgcolor="rgba(248,249,250,1)",
                        bordercolor="rgba(0,0,0,0.1)",
                        borderwidth=1
                    ),
                    type="date"
                )
            )
            
            return fig
            
        except Exception as e:
            st.error(f"Error creating attribution chart: {str(e)}")
            return None
    
    def _get_annual_points(self, data: pd.DataFrame, quality_filter: str) -> pd.DataFrame:
        """Extract annual data points for specific quality level, creating step functions."""
        try:
            # Filter by data quality
            filtered_data = data[data['data_quality'] == quality_filter].copy()
            
            if filtered_data.empty:
                return pd.DataFrame()
            
            # Get unique years and their representative values (use January value as representative)
            year_values = {}
            unique_years = sorted(filtered_data['year'].unique())
            
            for year in unique_years:
                # Get January data for this year as representative
                jan_data = filtered_data[(filtered_data['year'] == year) & (filtered_data['month'] == 1)]
                if not jan_data.empty:
                    year_values[year] = jan_data['monthly_emissions_attributed'].iloc[0]
                else:
                    # Fallback to any month if January not available
                    year_data = filtered_data[filtered_data['year'] == year]
                    year_values[year] = year_data['monthly_emissions_attributed'].iloc[0]
            
            if not year_values:
                return pd.DataFrame()
            
            # No debugging output needed for production
            
            # Create step function points - only connect consecutive years
            step_points = []
            sorted_years = sorted(year_values.keys())
            
            for i, year in enumerate(sorted_years):
                value = year_values[year]
                
                # Add monthly points throughout the year to align with smooth trend
                for month in range(1, 13):
                    step_points.append({
                        'date': pd.Timestamp(year=year, month=month, day=1),
                        'monthly_emissions_attributed': value,
                        'year': year,
                        'month': month,
                        'data_quality': quality_filter
                    })
            
            step_df = pd.DataFrame(step_points)
            return step_df.sort_values('date').reset_index(drop=True)
            
        except Exception as e:
            print(f"Error creating step function for {quality_filter}: {e}")
            return pd.DataFrame()
    
    def _get_estimated_only_points(self, data: pd.DataFrame) -> pd.DataFrame:
        """Extract estimated data points only for years that don't have reported data."""
        try:
            # Get years that have reported data
            reported_years = set(data[data['data_quality'] == 'reported']['year'].unique())
            
            # Get estimated data only for years without reported data
            estimated_data = data[data['data_quality'] == 'estimated'].copy()
            estimated_only = estimated_data[~estimated_data['year'].isin(reported_years)]
            
            if estimated_only.empty:
                return pd.DataFrame()
            
            # Get unique years and their representative values (use January value)
            year_values = {}
            unique_years = sorted(estimated_only['year'].unique())
            
            for year in unique_years:
                # Get January data for this year as representative
                jan_data = estimated_only[(estimated_only['year'] == year) & (estimated_only['month'] == 1)]
                if not jan_data.empty:
                    year_values[year] = jan_data['monthly_emissions_attributed'].iloc[0]
                else:
                    # Fallback to any month if January not available
                    year_data = estimated_only[estimated_only['year'] == year]
                    year_values[year] = year_data['monthly_emissions_attributed'].iloc[0]
            
            if not year_values:
                return pd.DataFrame()
            
            # Clean separation: only show estimated data for years without reported data
            
            # Create step function points
            step_points = []
            sorted_years = sorted(year_values.keys())
            
            for year in sorted_years:
                value = year_values[year]
                
                # Add monthly points throughout the year to align with smooth trend
                for month in range(1, 13):
                    step_points.append({
                        'date': pd.Timestamp(year=year, month=month, day=1),
                        'monthly_emissions_attributed': value,
                        'year': year,
                        'month': month,
                        'data_quality': 'estimated'
                    })
            
            step_df = pd.DataFrame(step_points)
            return step_df.sort_values('date').reset_index(drop=True)
            
        except Exception as e:
            print(f"Error creating estimated-only step function: {e}")
            return pd.DataFrame()
    
    def _add_estimated_traces(self, fig: go.Figure, estimated_data: pd.DataFrame) -> None:
        """Add estimated data as separate traces for each continuous period."""
        try:
            if estimated_data.empty:
                return
            
            # Group by continuous year periods to avoid connecting across gaps
            years = sorted(estimated_data['year'].unique())
            continuous_periods = []
            current_period = [years[0]]
            
            for i in range(1, len(years)):
                if years[i] == years[i-1] + 1:  # Consecutive year
                    current_period.append(years[i])
                else:  # Gap detected, start new period
                    continuous_periods.append(current_period)
                    current_period = [years[i]]
            
            continuous_periods.append(current_period)  # Add the last period
            
            # Add separate trace for each continuous period
            for i, period in enumerate(continuous_periods):
                period_data = estimated_data[estimated_data['year'].isin(period)]
                
                show_legend = i == 0  # Only show legend for first trace
                trace_name = 'Annual Estimated Data (Steps)' if show_legend else None
                
                fig.add_trace(go.Scatter(
                    x=period_data['date'],
                    y=period_data['monthly_emissions_attributed'],
                    mode='lines',
                    name=trace_name,
                    line=dict(color=self.color_palette['estimated_data'], width=2, shape='hv', dash='dash'),
                    connectgaps=False,
                    hovertemplate='<b>%{x|%Y-%m}</b><br>' +
                                'Annual Data: %{y:.1f} tCO₂e/month<br>' +
                                'Data Quality: Estimated<br>' +
                                '<extra></extra>',
                    showlegend=show_legend,
                    legendgroup='estimated'  # Group all estimated traces together
                ))
                
        except Exception as e:
            print(f"Error adding estimated traces: {e}")
    
    def create_sector_comparison_chart(self, data: List[Dict[str, Any]]) -> Optional[go.Figure]:
        """Create a chart comparing carbon attribution across sectors."""
        try:
            df = pd.DataFrame(data)
            
            if df.empty:
                return None
            
            # Create bar chart
            fig = go.Figure(data=[
                go.Bar(
                    x=df['sector'],
                    y=df['monthly_attribution'],
                    text=df['monthly_attribution'].round(1),
                    textposition='auto',
                    marker_color=px.colors.qualitative.Set3[:len(df)]
                )
            ])
            
            fig.update_layout(
                title="Carbon Attribution by Sector (Monthly Average)",
                xaxis_title="Sector",
                yaxis_title="Monthly Attribution (tCO₂e)",
                showlegend=False,
                height=400
            )
            
            return fig
            
        except Exception as e:
            st.error(f"Error creating sector comparison chart: {str(e)}")
            return None
    
    def create_portfolio_exposure_chart(self, exposure_data: pd.DataFrame) -> Optional[go.Figure]:
        """Create a chart showing portfolio carbon exposure over time."""
        try:
            if exposure_data.empty:
                return None
            
            # Prepare data for plotting
            exposure_sorted = exposure_data.sort_values('period_start')
            
            # Create figure
            fig = go.Figure()
            
            # Add portfolio exposure line
            fig.add_trace(go.Scatter(
                x=exposure_sorted['period_start'],
                y=exposure_sorted['portfolio_carbon_change'],
                mode='lines+markers',
                name='Portfolio Carbon Exposure',
                line=dict(color='#2E86AB', width=3),
                marker=dict(
                    color='#2E86AB',
                    size=8,
                    symbol='circle',
                    line=dict(width=2, color='white')
                ),
                hovertemplate='<b>%{x}</b><br>' +
                            'Carbon Exposure: %{y:.2f} tCO₂e<br>' +
                            '<extra></extra>',
                showlegend=True
            ))
            
            # Add zero reference line
            fig.add_hline(
                y=0, 
                line_dash="dash", 
                line_color="gray", 
                annotation_text="Neutral Exposure",
                annotation_position="bottom right"
            )
            
            # Update layout
            fig.update_layout(
                title="Portfolio Carbon Exposure Over Time",
                xaxis_title="Period",
                yaxis_title="Carbon Exposure Change (tCO₂e)",
                template='plotly_white',
                hovermode='x unified',
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                height=400
            )
            
            # Color-code positive/negative exposure
            colors = ['#e74c3c' if val > 0 else '#27ae60' for val in exposure_sorted['portfolio_carbon_change']]
            
            # Add bar chart overlay for better visualization
            fig.add_trace(go.Bar(
                x=exposure_sorted['period_start'],
                y=exposure_sorted['portfolio_carbon_change'],
                name='Period Change',
                marker_color=colors,
                opacity=0.3,
                showlegend=False,
                hoverinfo='skip'
            ))
            
            return fig
            
        except Exception as e:
            st.error(f"Error creating portfolio exposure chart: {str(e)}")
            return None
    
    def create_data_quality_chart(self, data: pd.DataFrame) -> Optional[go.Figure]:
        """Create a chart showing data quality over time."""
        try:
            if data.empty:
                return None
            
            # Aggregate by year and data quality
            quality_summary = data.groupby(['year', 'data_quality']).size().unstack(fill_value=0)
            
            fig = go.Figure()
            
            # Add bars for each quality type
            for quality in ['reported', 'estimated']:
                if quality in quality_summary.columns:
                    fig.add_trace(go.Bar(
                        name=quality.title(),
                        x=quality_summary.index,
                        y=quality_summary[quality],
                        marker_color=self.color_palette['reported_data'] if quality == 'reported' else self.color_palette['estimated_data']
                    ))
            
            fig.update_layout(
                title="Data Quality Distribution by Year",
                xaxis_title="Year",
                yaxis_title="Number of Data Points",
                barmode='stack',
                height=300
            )
            
            return fig
            
        except Exception as e:
            st.error(f"Error creating data quality chart: {str(e)}")
            return None
    
    def create_ownership_chart(self, data: pd.DataFrame, investment_amount: float) -> Optional[go.Figure]:
        """Create a chart showing ownership percentage over time."""
        try:
            if data.empty:
                return None
            
            data_sorted = data.sort_values(['year', 'month']).copy()
            data_sorted['date'] = pd.to_datetime(data_sorted[['year', 'month']].assign(day=1))
            
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=data_sorted['date'],
                y=data_sorted['ownership_percentage'] * 100,
                mode='lines',
                name='Ownership Percentage',
                line=dict(color='#ff7f0e', width=2),
                hovertemplate='<b>%{x}</b><br>' +
                            'Ownership: %{y:.4f}%<br>' +
                            f'Investment: ${investment_amount/1e6:.1f}M<br>' +
                            '<extra></extra>'
            ))
            
            fig.update_layout(
                title="Ownership Percentage Over Time",
                xaxis_title="Date",
                yaxis_title="Ownership Percentage (%)",
                showlegend=False,
                height=300
            )
            
            return fig
            
        except Exception as e:
            st.error(f"Error creating ownership chart: {str(e)}")
            return None
