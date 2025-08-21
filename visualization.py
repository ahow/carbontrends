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
                hovertemplate='<b>%{x}</b><br>' +
                            'Monthly Attribution: %{y:.1f} tCO₂e<br>' +
                            '<extra></extra>',
                showlegend=True
            ))
            
            # Add annual reported data points
            reported_data = self._get_annual_points(data_sorted, 'reported')
            if not reported_data.empty:
                fig.add_trace(go.Scatter(
                    x=reported_data['date'],
                    y=reported_data['monthly_emissions_attributed'],
                    mode='lines+markers',
                    name='Annual Reported Data (Steps)',
                    line=dict(color=self.color_palette['reported_data'], width=2, shape='hv'),
                    marker=dict(
                        color=self.color_palette['reported_data'],
                        size=8,
                        symbol='circle',
                        line=dict(width=1, color='white')
                    ),
                    hovertemplate='<b>%{x|%Y}</b><br>' +
                                'Annual Data: %{y:.1f} tCO₂e/month<br>' +
                                'Data Quality: Reported<br>' +
                                '<extra></extra>',
                    showlegend=True
                ))
            
            # Add annual estimated data points
            estimated_data = self._get_annual_points(data_sorted, 'estimated')
            if not estimated_data.empty:
                fig.add_trace(go.Scatter(
                    x=estimated_data['date'],
                    y=estimated_data['monthly_emissions_attributed'],
                    mode='lines+markers',
                    name='Annual Estimated Data (Steps)',
                    line=dict(color=self.color_palette['estimated_data'], width=2, shape='hv', dash='dash'),
                    marker=dict(
                        color=self.color_palette['estimated_data'],
                        size=6,
                        symbol='triangle-up',
                        line=dict(width=1, color='white')
                    ),
                    hovertemplate='<b>%{x|%Y}</b><br>' +
                                'Annual Data: %{y:.1f} tCO₂e/month<br>' +
                                'Data Quality: Estimated<br>' +
                                '<extra></extra>',
                    showlegend=True
                ))
            
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
            
            # Add range selector
            fig.update_layout(
                xaxis=dict(
                    rangeselector=dict(
                        buttons=list([
                            dict(count=1, label="1Y", step="year", stepmode="backward"),
                            dict(count=3, label="3Y", step="year", stepmode="backward"),
                            dict(count=5, label="5Y", step="year", stepmode="backward"),
                            dict(step="all", label="All")
                        ])
                    ),
                    rangeslider=dict(visible=True, thickness=0.05),
                    type="date"
                )
            )
            
            return fig
            
        except Exception as e:
            st.error(f"Error creating attribution chart: {str(e)}")
            return None
    
    def _get_annual_points(self, data: pd.DataFrame, quality_filter: str) -> pd.DataFrame:
        """Extract annual data points for specific quality level."""
        try:
            # Filter by data quality
            filtered_data = data[data['data_quality'] == quality_filter].copy()
            
            if filtered_data.empty:
                return pd.DataFrame()
            
            # Get one point per year (preferably from June/mid-year)
            annual_points = []
            unique_years = filtered_data['year'].unique()
            for year in unique_years:
                year_data = filtered_data[filtered_data['year'] == year]
                
                # Prefer June data (month 6) or closest to mid-year
                if len(year_data) > 1:
                    june_data = year_data[year_data['month'] == 6]
                    if not june_data.empty:
                        annual_points.append(june_data.iloc[0].to_dict())
                    else:
                        # Find closest to middle of year
                        year_data_copy = year_data.copy()
                        year_data_copy['month_diff'] = abs(year_data_copy['month'] - 6.5)
                        closest_idx = year_data_copy['month_diff'].idxmin()
                        closest = year_data_copy.loc[closest_idx]
                        annual_points.append(closest.to_dict())
                else:
                    annual_points.append(year_data.iloc[0].to_dict())
            
            return pd.DataFrame(annual_points)
            
        except Exception:
            return pd.DataFrame()
    
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
