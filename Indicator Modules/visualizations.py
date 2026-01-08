"""
Visualization functions for financial risk assessment indicators.

This module provides plotting functions for individual and combined KPI distributions,
with support for file saving and base64 encoding for API responses.
"""

import numpy as np
import matplotlib.pyplot as plt
import base64
from io import BytesIO
from typing import Dict, Any, Optional, Union
from indicator_outputs import get_full_distribution


def plot_indicator_distribution(
    simulation_results: Dict[str, Any],
    indicator: str,
    save_path: Optional[str] = None,
    return_base64: bool = False,
    figsize: tuple = (10, 6),
    color: str = 'steelblue',
    show_plot: bool = True
) -> Optional[Union[str, plt.Figure]]:
    """
    Plot distribution for a single indicator with P10/P50/P90 markers.
    
    Parameters
    ----------
    simulation_results : dict
        Output from run_simulation()
    indicator : str
        One of: 'IRR', 'NPV', 'PBP', 'DPP', 'ROI'
    save_path : str, optional
        Path to save the plot (e.g., 'plots/irr.png')
    return_base64 : bool, default False
        If True, return base64-encoded image string for API responses
    figsize : tuple, default (10, 6)
        Figure size (width, height) in inches
    color : str, default 'steelblue'
        Color for the histogram
    show_plot : bool, default True
        Whether to display the plot (use False for API/batch processing)
    
    Returns
    -------
    str or Figure or None
        - If return_base64=True: base64 string
        - If return_base64=False and save_path: Figure object
        - Otherwise: None
    
    Examples
    --------
    >>> results = run_simulation(...)
    >>> # Display plot
    >>> plot_indicator_distribution(results, 'NPV')
    >>> 
    >>> # Save to file
    >>> plot_indicator_distribution(results, 'IRR', save_path='plots/irr.png', show_plot=False)
    >>> 
    >>> # Get base64 for API
    >>> img_base64 = plot_indicator_distribution(results, 'NPV', return_base64=True, show_plot=False)
    """
    valid_indicators = ['IRR', 'NPV', 'PBP', 'DPP', 'ROI']
    if indicator not in valid_indicators:
        raise ValueError(f"indicator must be one of {valid_indicators}, got: {indicator}")
    
    # Get data
    data = get_full_distribution(simulation_results, indicator, remove_nan=True)
    project_lifetime = simulation_results['metadata']['project_lifetime']
    
    # Separate feasible and infeasible based on indicator type
    if indicator in ['PBP', 'DPP']:
        # For payback: only periods within project lifetime are feasible
        feasible = data[data <= project_lifetime]
        infeasible = data[data > project_lifetime]
    else:
        # For other indicators, negative = infeasible
        if indicator in ['NPV', 'IRR', 'ROI']:
            feasible = data[data >= 0]
            infeasible = data[data < 0]
        else:
            feasible = data
            infeasible = np.array([])
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Plot feasible values
    if len(feasible) > 0:
        ax.hist(feasible, bins=50, alpha=0.7, color=color, edgecolor='black', label='Feasible')
    
    # Plot infeasible values
    if len(infeasible) > 0:
        ax.hist(infeasible, bins=30, alpha=0.7, color='red', edgecolor='black', label='Infeasible')
    
    # Calculate percentiles on full data
    p10, p50, p90 = np.percentile(data, [10, 50, 90])
    
    # Add percentile markers
    ax.axvspan(p10, p90, alpha=0.15, color='orange', label='P10–P90')
    ax.axvline(p10, linestyle='--', linewidth=1.5, color='orange', label=f'P10={p10:.3g}')
    ax.axvline(p50, linestyle='-', linewidth=2, color='red', label=f'P50={p50:.3g}')
    ax.axvline(p90, linestyle='--', linewidth=1.5, color='orange', label=f'P90={p90:.3g}')
    
    # Special marker for payback periods
    if indicator in ['PBP', 'DPP']:
        ax.axvline(project_lifetime, linestyle='-', linewidth=2, color='black', 
                   label=f'Project lifetime ({project_lifetime}y)')
    
    # Special marker for NPV = 0
    if indicator == 'NPV':
        ax.axvline(0, linestyle='-', linewidth=1, color='black', alpha=0.5, label='Break-even')
    
    # Labels and title
    ax.set_xlabel(indicator)
    ax.set_ylabel('Frequency')
    ax.set_title(f'{indicator} Distribution ({simulation_results["metadata"]["n_sims"]:,} simulations)')
    ax.legend(loc='best', frameon=False, fontsize=9)
    ax.grid(True, axis='y', linestyle='--', alpha=0.3)
    
    plt.tight_layout()
    
    # Handle output
    if return_base64:
        buffer = BytesIO()
        fig.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        plt.close(fig)
        return f"data:image/png;base64,{img_base64}"
    
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"✓ Plot saved to {save_path}")
    
    if show_plot:
        plt.show()
    else:
        plt.close(fig)
    
    return fig if not return_base64 else None


def plot_success_probabilities(
    simulation_results: Dict[str, Any],
    save_path: Optional[str] = None,
    return_base64: bool = False,
    figsize: tuple = (8, 5),
    show_plot: bool = True
) -> Optional[Union[str, plt.Figure]]:
    """
    Plot success probability bar chart.
    
    Parameters
    ----------
    simulation_results : dict
        Output from run_simulation()
    save_path : str, optional
        Path to save the plot
    return_base64 : bool, default False
        If True, return base64-encoded image string
    figsize : tuple, default (8, 5)
        Figure size (width, height) in inches
    show_plot : bool, default True
        Whether to display the plot
    
    Returns
    -------
    str or Figure or None
    
    Examples
    --------
    >>> results = run_simulation(...)
    >>> plot_success_probabilities(results)
    """
    probabilities = simulation_results['summary']['probabilities']
    
    fig, ax = plt.subplots(figsize=figsize)
    
    labels = list(probabilities.keys())
    values = list(probabilities.values())
    colors = ['royalblue', 'blue', 'navy']
    
    bars = ax.bar(labels, values, color=colors, alpha=0.8, edgecolor='black')
    
    # Add value labels on bars
    for bar, val in zip(bars, values):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 0.02,
                f'{val:.1%}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax.set_ylim(0, 1)
    ax.set_ylabel('Probability', fontsize=11)
    ax.set_title('Success Probabilities', fontsize=13, fontweight='bold')
    ax.grid(True, axis='y', linestyle='--', alpha=0.3)
    
    # Rotate x labels if needed
    plt.xticks(rotation=15, ha='right')
    plt.tight_layout()
    
    # Handle output
    if return_base64:
        buffer = BytesIO()
        fig.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        plt.close(fig)
        return f"data:image/png;base64,{img_base64}"
    
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"✓ Plot saved to {save_path}")
    
    if show_plot:
        plt.show()
    else:
        plt.close(fig)
    
    return fig if not return_base64 else None


def plot_all_indicators(
    simulation_results: Dict[str, Any],
    save_path: Optional[str] = None,
    return_base64: bool = False,
    figsize: tuple = (16, 10),
    show_plot: bool = True
) -> Optional[Union[str, plt.Figure]]:
    """
    Plot 6-panel summary: 5 indicator distributions + success probabilities.
    
    This creates the comprehensive view similar to the original get_kpi_results() output.
    
    Parameters
    ----------
    simulation_results : dict
        Output from run_simulation()
    save_path : str, optional
        Path to save the plot (e.g., 'plots/full_summary.png')
    return_base64 : bool, default False
        If True, return base64-encoded image string
    figsize : tuple, default (16, 10)
        Figure size (width, height) in inches
    show_plot : bool, default True
        Whether to display the plot
    
    Returns
    -------
    str or Figure or None
    
    Examples
    --------
    >>> results = run_simulation(...)
    >>> # Display comprehensive summary
    >>> plot_all_indicators(results)
    >>> 
    >>> # Save to file for reporting
    >>> plot_all_indicators(results, save_path='reports/summary.png', show_plot=False)
    >>> 
    >>> # Get base64 for API endpoint
    >>> img = plot_all_indicators(results, return_base64=True, show_plot=False)
    """
    fig, axs = plt.subplots(2, 3, figsize=figsize)
    axs = axs.ravel()
    
    indicators = ['IRR', 'NPV', 'PBP', 'DPP', 'ROI']
    colors = ['steelblue', 'seagreen', 'coral', 'mediumorchid', 'goldenrod']
    
    project_lifetime = simulation_results['metadata']['project_lifetime']
    
    # Plot each indicator
    for idx, (indicator, color) in enumerate(zip(indicators, colors)):
        ax = axs[idx]
        data = get_full_distribution(simulation_results, indicator, remove_nan=True)
        
        # Determine feasible/infeasible
        if indicator in ['PBP', 'DPP']:
            feasible = data[data <= project_lifetime]
            infeasible = data[data > project_lifetime]
        elif indicator in ['NPV', 'IRR', 'ROI']:
            feasible = data[data >= 0]
            infeasible = data[data < 0]
        else:
            feasible = data
            infeasible = np.array([])
        
        # Plot histograms
        if len(feasible) > 0:
            ax.hist(feasible, bins=30, alpha=0.7, color=color, edgecolor='black', label='Feasible')
        if len(infeasible) > 0:
            ax.hist(infeasible, bins=20, alpha=0.7, color='red', edgecolor='black', label='Infeasible')
        
        # Percentile markers
        p10, p50, p90 = np.percentile(data, [10, 50, 90])
        ax.axvspan(p10, p90, alpha=0.15, color='orange')
        ax.axvline(p10, linestyle='--', linewidth=1, color='orange', label=f'P10={p10:.3g}')
        ax.axvline(p50, linestyle='-', linewidth=1.5, color='red', label=f'P50={p50:.3g}')
        ax.axvline(p90, linestyle='--', linewidth=1, color='orange', label=f'P90={p90:.3g}')
        
        # Special markers
        if indicator in ['PBP', 'DPP']:
            ax.axvline(project_lifetime, linestyle='-', linewidth=1.5, color='black', 
                       label=f'Project lifetime')
        if indicator == 'NPV':
            ax.axvline(0, linestyle='-', linewidth=1, color='black', alpha=0.5)
        
        ax.set_title(f'{indicator} (P10–P90 band, P50)', fontsize=11, fontweight='bold')
        ax.set_xlabel(indicator, fontsize=10)
        ax.set_ylabel('Frequency', fontsize=10)
        ax.legend(loc='best', frameon=False, fontsize=8)
        ax.grid(True, axis='y', linestyle='--', alpha=0.3)
    
    # Plot success probabilities in 6th panel
    ax = axs[5]
    probabilities = simulation_results['summary']['probabilities']
    labels = list(probabilities.keys())
    values = list(probabilities.values())
    colors_prob = ['royalblue', 'blue', 'navy']
    
    bars = ax.bar(labels, values, color=colors_prob, alpha=0.8, edgecolor='black')
    for bar, val in zip(bars, values):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 0.02,
                f'{val:.2f}', ha='center', va='bottom', fontsize=9)
    
    ax.set_ylim(0, 1)
    ax.set_ylabel('Probability', fontsize=10)
    ax.set_title('Success Probabilities', fontsize=11, fontweight='bold')
    ax.grid(True, axis='y', linestyle='--', alpha=0.3)
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=15, ha='right', fontsize=8)
    
    plt.suptitle(f'Monte Carlo Risk Assessment ({simulation_results["metadata"]["n_sims"]:,} simulations)', 
                 fontsize=14, fontweight='bold', y=0.995)
    plt.tight_layout()
    
    # Handle output
    if return_base64:
        buffer = BytesIO()
        fig.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        plt.close(fig)
        return f"data:image/png;base64,{img_base64}"
    
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"✓ Plot saved to {save_path}")
    
    if show_plot:
        plt.show()
    else:
        plt.close(fig)
    
    return fig if not return_base64 else None


def compare_indicators(
    simulation_results: Dict[str, Any],
    indicators: list = ['IRR', 'NPV', 'ROI'],
    save_path: Optional[str] = None,
    return_base64: bool = False,
    figsize: tuple = (14, 5),
    show_plot: bool = True
) -> Optional[Union[str, plt.Figure]]:
    """
    Plot multiple indicators side-by-side for comparison.
    
    Parameters
    ----------
    simulation_results : dict
        Output from run_simulation()
    indicators : list, default ['IRR', 'NPV', 'ROI']
        List of indicators to compare
    save_path : str, optional
        Path to save the plot
    return_base64 : bool, default False
        If True, return base64-encoded image string
    figsize : tuple, default (14, 5)
        Figure size (width, height) in inches
    show_plot : bool, default True
        Whether to display the plot
    
    Returns
    -------
    str or Figure or None
    
    Examples
    --------
    >>> results = run_simulation(...)
    >>> # Compare profitability indicators
    >>> compare_indicators(results, ['IRR', 'NPV', 'ROI'])
    >>> 
    >>> # Compare payback periods
    >>> compare_indicators(results, ['PBP', 'DPP'])
    """
    n_indicators = len(indicators)
    fig, axes = plt.subplots(1, n_indicators, figsize=figsize)
    if n_indicators == 1:
        axes = [axes]
    
    colors = ['steelblue', 'seagreen', 'coral', 'mediumorchid', 'goldenrod']
    
    for idx, indicator in enumerate(indicators):
        ax = axes[idx]
        data = get_full_distribution(simulation_results, indicator, remove_nan=True)
        
        ax.hist(data, bins=40, alpha=0.7, color=colors[idx % len(colors)], edgecolor='black')
        
        p50 = np.percentile(data, 50)
        ax.axvline(p50, linestyle='-', linewidth=2, color='red', label=f'Median={p50:.3g}')
        
        if indicator == 'NPV':
            ax.axvline(0, linestyle='--', linewidth=1, color='black', alpha=0.5, label='Break-even')
        
        ax.set_xlabel(indicator, fontsize=11)
        ax.set_ylabel('Frequency', fontsize=11)
        ax.set_title(f'{indicator} Distribution', fontsize=12, fontweight='bold')
        ax.legend(loc='best', frameon=False)
        ax.grid(True, axis='y', linestyle='--', alpha=0.3)
    
    plt.tight_layout()
    
    # Handle output
    if return_base64:
        buffer = BytesIO()
        fig.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        plt.close(fig)
        return f"data:image/png;base64,{img_base64}"
    
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"✓ Plot saved to {save_path}")
    
    if show_plot:
        plt.show()
    else:
        plt.close(fig)
    
    return fig if not return_base64 else None



def generate_private_cash_flow_chart(
    capex: float,
    project_lifetime: int,
    annual_energy_savings: float,
    annual_maintenance_cost: float,
    loan_amount: float,
    loan_term: int,
    market_distributions: Dict[str, Any],
    loan_rate: Optional[float] = None,
    return_base64: bool = True,
    figsize: tuple = (18, 8)
) -> Optional[Union[str, plt.Figure]]:
    """
    Generate enhanced annual cash flow timeline chart for private users (homeowners).
    
    This visualization shows the complete investment journey:
    - Year 0: Initial out-of-pocket investment
    - Years 1-N: Annual inflows (energy savings) vs outflows (maintenance + loan payments)
    - Net cash flow line overlay
    - Break-even point marker with annotation
    - Loan paid-off marker with annotation (if applicable)
    - Value labels on bars for key years
    
    Parameters
    ----------
    capex : float
        Total capital expenditure (initial investment)
    project_lifetime : int
        Duration of the project in years
    annual_energy_savings : float
        Annual energy savings in kWh
    annual_maintenance_cost : float
        Annual maintenance cost in € (Year 0, will be inflated over time)
    loan_amount : float
        Total loan amount in €
    loan_term : int
        Loan duration in years
    market_distributions : dict
        Market distribution parameters from run_simulation() results
        Must contain: 'elec_price', 'inflation', 'loan_rate'
    loan_rate : float, optional
        Fixed loan interest rate as decimal (e.g., 0.05 for 5%)
        If None, uses median from market_distributions
    return_base64 : bool, default True
        If True, return base64-encoded PNG with data URI prefix
        If False, return Figure object
    figsize : tuple, default (18, 8)
        Figure size (width, height) in inches
    
    Returns
    -------
    str or Figure
        - If return_base64=True: base64-encoded PNG with data URI prefix
        - If return_base64=False: matplotlib Figure object
    
    Notes
    -----
    - Uses median trajectories from market distributions for visualization
    - Inflation rates stored as percentages in distributions (e.g., 2.5 for 2.5%)
    - Includes enhanced styling with colored annotations and value labels
    """
    import numpy_financial as npf
    
    # Get market distributions
    market_dist = market_distributions
    
    # Calculate using median market values
    median_elec_prices = np.exp(market_dist['elec_price']['mu_ln'])
    median_inflation = market_dist['inflation']['mu']
    
    # INFLOWS: Energy savings value (revenue)
    annual_revenues = annual_energy_savings * median_elec_prices[:project_lifetime]
    
    # OUTFLOWS: Maintenance costs (inflated over time)
    annual_opex = np.array([annual_maintenance_cost * np.prod([1 + median_inflation[j]/100 for j in range(i+1)]) 
                            for i in range(project_lifetime)])
    
    # OUTFLOWS: Loan payments (if loan exists)
    if loan_amount > 0 and loan_term > 0:
        # Determine loan rate
        if loan_rate is None:
            loan_rate_mu = market_dist.get('loan_rate', {}).get('mu')
            if loan_rate_mu is not None:
                loan_rate = float(loan_rate_mu[0]) / 100  # Convert percentage to decimal
            else:
                loan_rate = 0.04  # Fallback to 4%
        
        # Calculate annual loan payment using PMT formula
        annual_loan_payment = npf.pmt(loan_rate, loan_term, -loan_amount)
        
        # Create array of loan payments (only for loan term years)
        annual_loan_payments = np.zeros(project_lifetime)
        annual_loan_payments[:loan_term] = annual_loan_payment
    else:
        annual_loan_payments = np.zeros(project_lifetime)
    
    # Total annual outflows (maintenance + loan payments)
    total_annual_outflows = annual_opex + annual_loan_payments
    
    # Net cash flow per year (operational years only)
    annual_net_cf = annual_revenues - total_annual_outflows
    
    # Cumulative position (for break-even calculation)
    cumulative_position = np.zeros(project_lifetime + 1)
    cumulative_position[0] = -(capex - loan_amount)  # Year 0: Out-of-pocket investment
    for i in range(project_lifetime):
        cumulative_position[i+1] = cumulative_position[i] + annual_net_cf[i]
    
    # Find break-even year
    breakeven_year = np.where(cumulative_position >= 0)[0][0] if any(cumulative_position >= 0) else None
    
    # Create figure for annual cash flows
    fig, ax = plt.subplots(1, 1, figsize=figsize)
    
    # Prepare x-axis including year 0
    years_all = np.arange(0, project_lifetime + 1)
    bar_width = 0.35
    
    # Year 0: Initial out-of-pocket investment
    initial_investment = -(capex - loan_amount)
    
    # Combine year 0 with operational years for plotting
    all_inflows = np.concatenate([[0], annual_revenues])  # Year 0 has no inflows
    all_outflows = np.concatenate([[initial_investment], -total_annual_outflows])  # Year 0 has investment outflow
    all_net_cf = np.concatenate([[initial_investment], annual_net_cf])  # Net cash flow including year 0
    
    x_pos = np.arange(len(years_all))
    
    # Plot inflows (positive)
    bars_inflow = ax.bar(x_pos - bar_width/2, all_inflows, bar_width, 
                          label='Annual Inflows (Energy Savings)', 
                          color='#27ae60', alpha=0.8, edgecolor='darkgreen')
    
    # Plot outflows (negative)
    bars_outflow = ax.bar(x_pos + bar_width/2, all_outflows, bar_width,
                           label='Annual Outflows (Maintenance + Loan)', 
                           color='#e74c3c', alpha=0.8, edgecolor='darkred')
    
    # Add net cash flow as a line
    ax.plot(x_pos, all_net_cf, color='#2c3e50', linewidth=3, marker='o', 
             markersize=6, label='Net Annual Cash Flow', zorder=5)
    
    # Add zero line
    ax.axhline(y=0, color='black', linestyle='-', linewidth=1.5, alpha=0.7)
    
    # Get y-axis limits for positioning annotations at bottom
    y_min, y_max = ax.get_ylim()
    
    # Add vertical line for break-even point
    if breakeven_year:
        ax.axvline(x=breakeven_year, color='green', linestyle='--', linewidth=2.5, 
                   alpha=0.7, label=f'Break-Even (Year {breakeven_year})')
        # Add text annotation at bottom
        ax.text(breakeven_year, y_min + (y_max - y_min)*0.05, f'Break-Even\nYear {breakeven_year}',
               ha='center', va='bottom', fontsize=11, fontweight='bold', color='darkgreen',
               bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgreen', alpha=0.85))
    
    # Add vertical line for loan term end (if loan exists)
    if loan_amount > 0 and loan_term > 0:
        ax.axvline(x=loan_term, color='orange', linestyle='--', linewidth=2.5, 
                   alpha=0.7, label=f'Loan Paid Off (Year {loan_term})')
        # Add text annotation at bottom
        ax.text(loan_term, y_min + (y_max - y_min)*0.05, f'Loan Paid Off\nYear {loan_term}',
               ha='center', va='bottom', fontsize=11, fontweight='bold', color='darkorange',
               bbox=dict(boxstyle='round,pad=0.5', facecolor='#ffe6cc', alpha=0.85))
    
    # Add value labels on bars (every 5 years to avoid clutter)
    for i in range(0, len(years_all), 5):
        if i == 0:  # Year 0 special label
            ax.text(i + bar_width/2, all_outflows[i], f'€{-all_outflows[i]/1000:.1f}k',
                   ha='center', va='top', fontsize=10, fontweight='bold', color='darkred')
        else:
            # Inflow label
            ax.text(i - bar_width/2, all_inflows[i], f'€{all_inflows[i]/1000:.1f}k',
                   ha='center', va='bottom', fontsize=9, fontweight='bold', color='darkgreen')
            # Outflow label
            ax.text(i + bar_width/2, all_outflows[i], f'€{-all_outflows[i]/1000:.1f}k',
                   ha='center', va='top', fontsize=9, fontweight='bold', color='darkred')
    
    # Formatting
    ax.set_xlabel('Year', fontsize=14, fontweight='bold')
    ax.set_ylabel('Cash Flow (€)', fontsize=14, fontweight='bold')
    ax.set_title('Annual Cash Flow Timeline', 
                 fontsize=16, fontweight='bold', pad=20)
    
    # Move legend outside the plot area (to the right)
    ax.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), fontsize=11, framealpha=0.95)
    
    ax.grid(True, alpha=0.3, linestyle=':', linewidth=0.8)
    ax.set_xticks(x_pos[::2])
    ax.set_xticklabels(years_all[::2])
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'€{x:,.0f}'))
    
    plt.tight_layout()
    
    # Return as base64 or Figure
    if return_base64:
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        return f"data:image/png;base64,{img_base64}"
    else:
        return fig
