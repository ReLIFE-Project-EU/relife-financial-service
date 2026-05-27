"""
Visualization Script for Professional Output Chart Metadata

This script demonstrates how to render the distribution histograms
described in the professional output's chart_metadata.

It generates example visualizations showing:
- Histogram with frequency distribution
- Vertical lines for P10, P50 (median), P90
- Statistical overlays

Usage:
    python scripts/visualize_chart_metadata.py

Output:
    Generates PNG files in the docs/visualizations/ folder for each indicator.
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Dict, Any


def render_distribution_chart(
    chart_data: Dict[str, Any],
    indicator_name: str,
    output_path: Path
) -> None:
    """
    Render a distribution histogram from chart_metadata.
    
    Args:
        chart_data: The chart_metadata entry for a single indicator
        indicator_name: Name of the indicator (NPV, IRR, etc.)
        output_path: Path where to save the PNG file
    """
    
    # Extract data from chart_metadata
    bins_data = chart_data.get("bins", {})
    stats = chart_data.get("statistics", {})
    config = chart_data.get("chart_config", {})
    
    bin_edges = bins_data.get("edges", [])
    bin_counts = bins_data.get("counts", [])
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # Plot histogram
    if bin_edges and bin_counts:
        ax.bar(
            range(len(bin_counts)),
            bin_counts,
            color='steelblue',
            alpha=0.7,
            edgecolor='navy',
            linewidth=0.5
        )
        
        # Set x-axis labels to show actual values instead of bin indices
        n_ticks = min(6, len(bin_edges) - 1)  # Show ~6 ticks
        tick_indices = np.linspace(0, len(bin_counts) - 1, n_ticks, dtype=int)
        tick_labels = [f"{bin_edges[i]:.1f}" for i in tick_indices]
        ax.set_xticks(tick_indices)
        ax.set_xticklabels(tick_labels)
    
    # Add vertical lines for percentiles
    p10 = stats.get("P10", 0)
    p50 = stats.get("P50", 0)
    p90 = stats.get("P90", 0)
    
    y_max = max(bin_counts) if bin_counts else 1
    
    # Convert actual values to approximate bin positions
    if bin_edges:
        min_val = min(bin_edges)
        max_val = max(bin_edges)
        value_range = max_val - min_val
        
        if value_range > 0:
            p10_pos = (p10 - min_val) / value_range * len(bin_counts)
            p50_pos = (p50 - min_val) / value_range * len(bin_counts)
            p90_pos = (p90 - min_val) / value_range * len(bin_counts)
            
            ax.axvline(p10_pos, color='orange', linestyle='--', linewidth=2, label=f'P10: {p10:.2f}', alpha=0.8)
            ax.axvline(p50_pos, color='green', linestyle='-', linewidth=2.5, label=f'P50 (Median): {p50:.2f}', alpha=0.8)
            ax.axvline(p90_pos, color='red', linestyle='--', linewidth=2, label=f'P90: {p90:.2f}', alpha=0.8)
    
    # Add statistics box
    stats_text = (
        f"Mean: {stats.get('mean', 0):.2f}\n"
        f"Std Dev: {stats.get('std', 0):.2f}\n"
        f"P10: {p10:.2f}\n"
        f"P50: {p50:.2f}\n"
        f"P90: {p90:.2f}"
    )
    ax.text(
        0.98, 0.97,
        stats_text,
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment='top',
        horizontalalignment='right',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8)
    )
    
    # Labels and title
    ax.set_xlabel(config.get("xlabel", "Value"), fontsize=12, fontweight='bold')
    ax.set_ylabel(config.get("ylabel", "Frequency"), fontsize=12, fontweight='bold')
    ax.set_title(config.get("title", f"{indicator_name} Distribution"), fontsize=14, fontweight='bold')
    ax.legend(loc='upper left', fontsize=10)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    
    plt.tight_layout()
    
    # Save figure
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ Saved: {output_path}")
    plt.close()


def generate_sample_chart_metadata() -> Dict[str, Any]:
    """
    Generate realistic sample chart_metadata based on typical simulation results.
    
    This demonstrates what the professional endpoint would return.
    """
    
    # Sample distributions similar to what Monte Carlo simulation produces
    np.random.seed(42)
    
    npv_data = np.random.normal(15000, 8000, 10000)
    irr_data = np.random.normal(0.085, 0.025, 10000)
    roi_data = np.random.normal(1.45, 0.35, 10000)
    pbp_data = np.random.normal(10.2, 3.5, 10000)
    dpp_data = np.random.normal(12.8, 4.2, 10000)
    
    datasets = {
        "NPV": {"data": npv_data, "label": "Net Present Value (€)"},
        "IRR": {"data": irr_data, "label": "Internal Rate of Return"},
        "ROI": {"data": roi_data, "label": "Return on Investment"},
        "PBP": {"data": pbp_data, "label": "Payback Period (years)"},
        "DPP": {"data": dpp_data, "label": "Discounted Payback Period (years)"}
    }
    
    chart_metadata = {}
    
    for indicator, dataset_info in datasets.items():
        data = dataset_info["data"]
        
        # Calculate histogram
        hist, bin_edges = np.histogram(data, bins=30, density=False)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        
        # Calculate percentiles
        p10, p50, p90 = np.percentile(data, [10, 50, 90])
        
        chart_metadata[indicator] = {
            "bins": {
                "centers": [float(x) for x in bin_centers],
                "counts": [int(x) for x in hist],
                "edges": [float(x) for x in bin_edges]
            },
            "statistics": {
                "mean": round(float(np.mean(data)), 4),
                "std": round(float(np.std(data)), 4),
                "P10": round(float(p10), 4),
                "P50": round(float(p50), 4),
                "P90": round(float(p90), 4)
            },
            "chart_config": {
                "xlabel": dataset_info["label"],
                "ylabel": "Frequency (Number of Scenarios)",
                "title": f"{indicator} Distribution (10,000 Simulations)"
            }
        }
    
    return chart_metadata


def main():
    """Generate visualization files from sample chart metadata."""
    
    print("=" * 70)
    print("Professional Output Chart Metadata Visualization")
    print("=" * 70)
    
    # Generate sample data
    print("\n[1/2] Generating sample chart metadata...")
    chart_metadata = generate_sample_chart_metadata()
    
    # Create output directory
    output_dir = Path(__file__).parent.parent / "docs" / "visualizations"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n[2/2] Rendering distribution charts...")
    
    # Render each chart
    for indicator, chart_data in chart_metadata.items():
        output_file = output_dir / f"distribution_{indicator.lower()}.png"
        render_distribution_chart(chart_data, indicator, output_file)
    
    # Save metadata as JSON for reference
    metadata_file = output_dir / "sample_chart_metadata.json"
    with open(metadata_file, 'w') as f:
        json.dump(chart_metadata, f, indent=2)
    print(f"✓ Saved: {metadata_file}")
    
    print("\n" + "=" * 70)
    print("SUCCESS! Generated visualization files:")
    print("=" * 70)
    for indicator in chart_metadata.keys():
        print(f"  - distribution_{indicator.lower()}.png")
    print(f"\nAll files saved to: {output_dir}")
    print("\nThese images demonstrate how to render the professional endpoint's")
    print("chart_metadata into interactive histograms with P10, P50, P90 overlays.")
    print("=" * 70)


if __name__ == "__main__":
    main()
