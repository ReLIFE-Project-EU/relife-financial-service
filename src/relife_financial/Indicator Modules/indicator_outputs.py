"""
Indicator extraction and formatting functions.

This module provides functions to extract individual KPI results from 
simulation output in various formats (point forecasts, distributions, probabilities).
"""

import numpy as np
from typing import Dict, Any, List, Optional


def get_point_forecast(
    simulation_results: Dict[str, Any],
    indicator: str,
    statistic: str = "median"
) -> float:
    """
    Extract a single point forecast for an indicator.
    
    Parameters
    ----------
    simulation_results : dict
        Output from run_simulation()
    indicator : str
        One of: 'IRR', 'NPV', 'PBP', 'DPP', 'ROI'
    statistic : str, default 'median'
        One of: 'mean', 'median', 'P50' (same as median)
    
    Returns
    -------
    float
        Point forecast value
    
    Examples
    --------
    >>> results = run_simulation(...)
    >>> median_irr = get_point_forecast(results, 'IRR', 'median')
    >>> mean_npv = get_point_forecast(results, 'NPV', 'mean')
    """
    valid_indicators = ['IRR', 'NPV', 'PBP', 'DPP', 'ROI']
    if indicator not in valid_indicators:
        raise ValueError(f"indicator must be one of {valid_indicators}, got: {indicator}")
    
    raw_data = simulation_results['raw_data'][indicator.lower()]
    
    if statistic in ['median', 'P50']:
        return float(np.nanmedian(raw_data))
    elif statistic == 'mean':
        return float(np.nanmean(raw_data))
    else:
        raise ValueError(f"statistic must be 'mean', 'median', or 'P50', got: {statistic}")


def get_distribution_summary(
    simulation_results: Dict[str, Any],
    indicator: str,
    percentiles: Optional[List[int]] = None
) -> Dict[str, float]:
    """
    Get percentile summary for an indicator.
    
    Parameters
    ----------
    simulation_results : dict
        Output from run_simulation()
    indicator : str
        One of: 'IRR', 'NPV', 'PBP', 'DPP', 'ROI'
    percentiles : list of int, optional
        Percentiles to compute. Default: [5, 10, 25, 50, 75, 90, 95]
    
    Returns
    -------
    dict
        {
            'P5': value,
            'P10': value,
            ...
            'mean': value,
            'std': value
        }
    
    Examples
    --------
    >>> results = run_simulation(...)
    >>> irr_dist = get_distribution_summary(results, 'IRR')
    >>> print(f"IRR P50: {irr_dist['P50']:.2%}")
    """
    valid_indicators = ['IRR', 'NPV', 'PBP', 'DPP', 'ROI']
    if indicator not in valid_indicators:
        raise ValueError(f"indicator must be one of {valid_indicators}, got: {indicator}")
    
    if percentiles is None:
        percentiles = [5, 10, 25, 50, 75, 90, 95]
    
    # Get from pre-computed summary if using default percentiles
    if percentiles == [5, 10, 25, 50, 75, 90, 95]:
        summary = simulation_results['summary']['percentiles'][indicator].copy()
    else:
        raw_data = simulation_results['raw_data'][indicator.lower()]
        summary = {f"P{p}": np.nanpercentile(raw_data, p) for p in percentiles}
    
    # Add mean and std
    raw_data = simulation_results['raw_data'][indicator.lower()]
    summary['mean'] = float(np.nanmean(raw_data))
    summary['std'] = float(np.nanstd(raw_data))
    
    return summary


def get_full_distribution(
    simulation_results: Dict[str, Any],
    indicator: str,
    remove_nan: bool = True
) -> np.ndarray:
    """
    Get the raw distribution array for an indicator.
    
    Parameters
    ----------
    simulation_results : dict
        Output from run_simulation()
    indicator : str
        One of: 'IRR', 'NPV', 'PBP', 'DPP', 'ROI'
    remove_nan : bool, default True
        Whether to filter out NaN values
    
    Returns
    -------
    np.ndarray
        Array of all simulation values (n_sims values)
    
    Examples
    --------
    >>> results = run_simulation(...)
    >>> npv_values = get_full_distribution(results, 'NPV')
    >>> print(f"Got {len(npv_values)} NPV samples")
    """
    valid_indicators = ['IRR', 'NPV', 'PBP', 'DPP', 'ROI']
    if indicator not in valid_indicators:
        raise ValueError(f"indicator must be one of {valid_indicators}, got: {indicator}")
    
    raw_data = simulation_results['raw_data'][indicator.lower()]
    
    if remove_nan:
        return raw_data[~np.isnan(raw_data)]
    else:
        return raw_data.copy()


def get_success_probabilities(
    simulation_results: Dict[str, Any]
) -> Dict[str, float]:
    """
    Get all success probability metrics.
    
    Parameters
    ----------
    simulation_results : dict
        Output from run_simulation()
    
    Returns
    -------
    dict
        {
            'Pr(NPV > 0)': probability,
            'Pr(PBP < Ty)': probability,
            'Pr(DPP < Ty)': probability
        }
    
    Examples
    --------
    >>> results = run_simulation(...)
    >>> probs = get_success_probabilities(results)
    >>> print(f"Success rate: {probs['Pr(NPV > 0)']:.1%}")
    """
    return simulation_results['summary']['probabilities'].copy()


def get_indicator_probability(
    simulation_results: Dict[str, Any],
    indicator: str,
    threshold: float,
    operator: str = ">"
) -> float:
    """
    Calculate custom probability for an indicator.
    
    Parameters
    ----------
    simulation_results : dict
        Output from run_simulation()
    indicator : str
        One of: 'IRR', 'NPV', 'PBP', 'DPP', 'ROI'
    threshold : float
        Threshold value for comparison
    operator : str, default '>'
        Comparison operator: '>', '>=', '<', '<=', '==', '!='
    
    Returns
    -------
    float
        Probability (0 to 1)
    
    Examples
    --------
    >>> results = run_simulation(...)
    >>> # Probability of IRR > 8%
    >>> p_irr_8 = get_indicator_probability(results, 'IRR', 0.08, '>')
    >>> # Probability of NPV > €10,000
    >>> p_npv_10k = get_indicator_probability(results, 'NPV', 10000, '>')
    """
    valid_indicators = ['IRR', 'NPV', 'PBP', 'DPP', 'ROI']
    if indicator not in valid_indicators:
        raise ValueError(f"indicator must be one of {valid_indicators}, got: {indicator}")
    
    valid_operators = ['>', '>=', '<', '<=', '==', '!=']
    if operator not in valid_operators:
        raise ValueError(f"operator must be one of {valid_operators}, got: {operator}")
    
    raw_data = simulation_results['raw_data'][indicator.lower()]
    raw_data = raw_data[~np.isnan(raw_data)]
    
    if operator == '>':
        mask = raw_data > threshold
    elif operator == '>=':
        mask = raw_data >= threshold
    elif operator == '<':
        mask = raw_data < threshold
    elif operator == '<=':
        mask = raw_data <= threshold
    elif operator == '==':
        mask = np.isclose(raw_data, threshold)
    elif operator == '!=':
        mask = ~np.isclose(raw_data, threshold)
    
    return float(np.mean(mask))


def get_all_indicators_summary(
    simulation_results: Dict[str, Any]
) -> Dict[str, Dict[str, float]]:
    """
    Get distribution summary for all indicators at once.
    
    Parameters
    ----------
    simulation_results : dict
        Output from run_simulation()
    
    Returns
    -------
    dict
        {
            'IRR': {'P5': ..., 'P50': ..., 'mean': ..., 'std': ...},
            'NPV': {...},
            'PBP': {...},
            'DPP': {...},
            'ROI': {...}
        }
    
    Examples
    --------
    >>> results = run_simulation(...)
    >>> all_summaries = get_all_indicators_summary(results)
    >>> print(f"IRR median: {all_summaries['IRR']['P50']:.2%}")
    """
    indicators = ['IRR', 'NPV', 'PBP', 'DPP', 'ROI']
    return {
        ind: get_distribution_summary(simulation_results, ind)
        for ind in indicators
    }


def format_indicator_output(
    simulation_results: Dict[str, Any],
    indicator: str,
    format_type: str = "summary"
) -> Dict[str, Any]:
    """
    Format indicator output for API responses.
    
    Parameters
    ----------
    simulation_results : dict
        Output from run_simulation()
    indicator : str
        One of: 'IRR', 'NPV', 'PBP', 'DPP', 'ROI'
    format_type : str, default 'summary'
        One of: 'point', 'summary', 'full'
    
    Returns
    -------
    dict
        Formatted output ready for JSON serialization
    
    Examples
    --------
    >>> results = run_simulation(...)
    >>> # Point forecast
    >>> point = format_indicator_output(results, 'IRR', 'point')
    >>> # {'indicator': 'IRR', 'value': 0.0573, 'type': 'median'}
    >>> 
    >>> # Summary with percentiles
    >>> summary = format_indicator_output(results, 'NPV', 'summary')
    >>> # {'indicator': 'NPV', 'percentiles': {...}, 'statistics': {...}}
    """
    valid_indicators = ['IRR', 'NPV', 'PBP', 'DPP', 'ROI']
    if indicator not in valid_indicators:
        raise ValueError(f"indicator must be one of {valid_indicators}, got: {indicator}")
    
    valid_formats = ['point', 'summary', 'full']
    if format_type not in valid_formats:
        raise ValueError(f"format_type must be one of {valid_formats}, got: {format_type}")
    
    if format_type == 'point':
        return {
            'indicator': indicator,
            'value': get_point_forecast(simulation_results, indicator, 'median'),
            'type': 'median',
            'n_simulations': simulation_results['metadata']['n_sims']
        }
    
    elif format_type == 'summary':
        dist_summary = get_distribution_summary(simulation_results, indicator)
        return {
            'indicator': indicator,
            'percentiles': {k: v for k, v in dist_summary.items() if k.startswith('P')},
            'statistics': {
                'mean': dist_summary['mean'],
                'std': dist_summary['std']
            },
            'n_simulations': simulation_results['metadata']['n_sims']
        }
    
    elif format_type == 'full':
        raw_data = get_full_distribution(simulation_results, indicator, remove_nan=True)
        return {
            'indicator': indicator,
            'distribution': raw_data.tolist(),  # Convert to list for JSON
            'n_values': len(raw_data),
            'n_simulations': simulation_results['metadata']['n_sims']
        }


def get_metadata(simulation_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract simulation metadata.
    
    Parameters
    ----------
    simulation_results : dict
        Output from run_simulation()
    
    Returns
    -------
    dict
        Metadata including n_sims, project_lifetime, discount_rate, loan info
    """
    return simulation_results['metadata'].copy()
