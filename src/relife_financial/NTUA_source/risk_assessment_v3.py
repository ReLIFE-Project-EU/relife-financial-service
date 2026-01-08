import numpy as np
import numpy_financial as npf
import itertools
import math
import matplotlib.pyplot as plt


# ────────────────────────────────────────────────────────────────────────────────
# Financial-math functions
# ────────────────────────────────────────────────────────────────────────────────

def cash_flows_with_loan(
    capex: float,
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    electricity_prices: list[float],
    inflation_rate: list[float],
    loan_amount: float,
    loan_interest_rate: list[float],
    loan_term: int,
) -> list[float]:
    """Compute the yearly net cash-flow profile **including** debt service.

    Parameters
    ----------
    capex : float
        Up-front capital expenditure (positive number). The function treats this as
        an *outflow* at *t = 0*.
    annual_energy_savings : float
        Nominal number of kWh saved per year.
    annual_maintenace_cost : float
        Nominal yearly O&M cost in today's money.
    project_lifetime : int
        Evaluation horizon in *years* (must be at least 1).
    electricity_prices : list[float]
        Forecast grid prices for each year **indexed the same as `inflation_rate`**.
    inflation_rate : list[float]
        Inflation rates for each year (indexed the same as `electricity_prices`).
    loan_amount : float
        Principal borrowed at *t = 0*.
    loan_interest_rate : list[float]
        Annual interest rate applicable **per remaining principal**.
    loan_term : int
        Term of loan in *years* (must be at least 1).
    Returns
    -------
    list[float]
        Sequence of net cash-flows (index 0 … ``project_lifetime - 1``).  The first
        element is *negative* (the equity outflow) and subsequent entries may be
        positive or negative depending on operating surplus and debt service.
    """
    try:
        flows = []
        
        # capex minus the loan received
        flows.append(-(capex-loan_amount))
        
        outstanding = loan_amount
        constant_principal_payment = loan_amount / loan_term if loan_term > 0 else 0.0
        cumulative_infl = 1.0

        for year in range(0, project_lifetime):
            cumulative_infl *= (1 + inflation_rate[year]/100.0)
            operating_cf = annual_energy_savings * electricity_prices[year] - annual_maintenace_cost * cumulative_infl
            loan_payment = 0.0
            
            if year <= loan_term and loan_amount > 0:
                interest_payment = outstanding * (loan_interest_rate[year - 1] / 100.0)
                loan_payment = constant_principal_payment + interest_payment
                outstanding -= constant_principal_payment  
            
            flows.append(operating_cf - loan_payment)
        
        return flows
    except Exception:
        # Absolute safety net
        return [np.nan]

def cash_flows(
    capex: float,
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    electricity_prices: list[float],
    inflation_rate: list[float],
) -> list[float]:
    """Compute yearly net cash-flows for an **equity-only** project.

    This variant omits any debt-service considerations and is therefore a
    simplified special-case of :func:`cash_flows_with_loan`.

    Parameters
    ----------
    capex, annual_energy_savings, annual_maintenace_cost, project_lifetime,
    electricity_prices, inflation_rate : see :func:`cash_flows_with_loan`.

    Returns
    -------
    list[float]
        Cash-flow sequence (first entry negative).
    """
    try:
        flows = [-capex] # t = 0 equity investment
        cumulative_infl = 1.0
        for k in range(0, project_lifetime):
            cumulative_infl *= (1 + inflation_rate[k]/100.0)
            flow_k = annual_energy_savings * electricity_prices[k] - annual_maintenace_cost * cumulative_infl
            flows.append(flow_k)
        return flows
    except Exception:
        # Absolute safety net
        return [np.nan]

def IRR(flows: list[float]) -> float:
    """Internal Rate of Return (IRR).

    A wrapper around :pyfunc:`numpy_financial.irr`. IRR is the discount rate that
    forces the NPV of a series of cash-flows to **zero**.

    Parameters
    ----------
    flows : list[float]
        Net cash-flows.

    Returns
    -------
    float
        Annualised IRR expressed as a *fraction* (e.g. ``0.15`` for 15 %). May
        return *NaN* if IRR cannot be solved (e.g. multiple sign changes).
    """
    try:
        return npf.irr(flows)
    except Exception:
            return np.nan

def NPV(d_r: float, flows: list[float]) -> float:
    """Net Present Value given a constant discount rate.

    A wrapper around :pyfunc:`numpy_financial.npv`. 

    Parameters
    ----------
    d_r : float
        Discount rate expressed as a fraction (``0.08`` → 8 %). Must be > -1.
    flows : list[float]
        Sequence of net cash-flows.

    Returns
    -------
    float
        Present value of cash-flows.
    """
    try:
        return npf.npv(d_r, flows)
    except Exception:
            return np.nan


def PBP(flows: list[float], loan: bool = False, loan_term: int = 0) -> float:
    """Simple (undiscounted) *PayBack Period*.

    The payback period is the time required for cumulative **undiscounted** cash
    inflows to match the original investment outflow.  If a loan is involved we
    optionally enforce that PBP cannot be shorter than the loan tenor.

    Parameters
    ----------
    flows : list[float]
        Net cash-flows (index 0 negative).
    loan : bool, default ``False``
        If *True*, PBP is floored at `loan_term`.
    loan_term : int, default ``0``
        Length of the loan in years.

    Returns
    -------
    float
        Years to break-even, resolved to fractional years via linear
        interpolation. *NaN* if the project never breaks even.
    """
    try:
        investment = flows[0] * -1

        flow = flows[1:]

        total, years, cumulative = 0.0, 0, []
        if sum(flow) < investment:
            # print("insufficient cashflows  --- no break even point")
            pbp = np.nan
        else:

            for fl in flow:
                total += fl
                cumulative.append(total)
                if total < investment:
                    years += 1
                else:
                    break

            A = years
            B = investment - cumulative[years - 1]
            C = cumulative[years] - cumulative[years - 1]

            try:
                pbp = float(A) + (float(B) / float(C))
            except ZeroDivisionError:
                pbp = 1

        # Constraint removed: PBP now reflects true equity payback, not loan maturity
        return pbp
    except Exception:
        return np.nan

def DPP(
    d_r: float,
    n: int,
    flows: list[float],
    loan: bool = False,
    loan_term: int = 0,
) -> float:
    """*Discounted* PayBack Period.

    Equivalent to :func:`PBP` but each cash-flow is first discounted to its
    present value using a constant rate `d_r`.

    Parameters
    ----------
    d_r : float
        Discount rate (fraction).
    n : int
        Number of periods (typically equal to project life).
    flows : list[float]
        Cash-flow sequence (index 0 negative).
    loan, loan_term : see :func:`PBP`.

    Returns
    -------
    float
        Discounted payback period (years). *NaN* if never breaks even.
    """
    try:
        discounted_flows = []
        discounted_flows.append(flows[0])

        for i in range(1, n+1):
            flow_k = flows[i] * np.power(float(1 + d_r), -i)
            discounted_flows.append(flow_k)

        dpp = PBP(discounted_flows)
        # Constraint removed: DPP now reflects true discounted equity payback
        return dpp
    except Exception:
        return np.nan

def ROI(flows: list[float]) -> float:
    """Return on Investment (simple fraction).

    Parameters
    ----------
    flows : list[float]
        Cash-flow sequence where ``flows[0]`` is negative.

    Returns
    -------
    float
        Dimensionless fraction. Positive == profitable. *NaN* if initial
        investment is zero.
    """
    initial_investment = -flows[0]  
    net_profit = sum(flows[1:])     
    if initial_investment == 0:
        return np.nan
    return (net_profit - initial_investment) / initial_investment

# ────────────────────────────────────────────────────────────────────────────────
# Create distribution helpers (80% confidence intervals)
# ────────────────────────────────────────────────────────────────────────────────

Z90 = 1.2815515655446004  # Φ^{-1}(0.90)


def pad_to_length(lst, length):
        """Extend the list to the desired length by repeating the last value."""
        return lst + [lst[-1]] * (length - len(lst)) if len(lst) < length else lst[:length]

def _mu_sigma_from_p10_p50_p90(p10, p50, p90):
    """Assume Normal on the linear scale; return arrays (mu, sigma)."""
    p10 = np.asarray(p10, dtype=float)
    p50 = np.asarray(p50, dtype=float)
    p90 = np.asarray(p90, dtype=float)
    mu = p50
    sigma = (p90 - p10) / (2.0 * Z90)
    # guard against zero/negative spreads
    sigma = np.maximum(sigma, 1e-12)
    return mu, sigma

def _log_mu_sigma_from_p10_p50_p90_prices(p10, p50, p90):
    """
    Electricity prices: use Lognormal ⇒ Normal in log-space.
    optimistic ≈ P90, moderate ≈ P50 (median), pessimistic ≈ P10.
    Returns (mu_ln, sigma_ln).
    """
    eps = 1e-9
    p10 = np.maximum(np.asarray(p10, dtype=float), eps)
    p50 = np.maximum(np.asarray(p50, dtype=float), eps)
    p90 = np.maximum(np.asarray(p90, dtype=float), eps)
    mu_ln = np.log(p50)                      
    sigma_ln = (np.log(p90) - np.log(p10)) / (2.0 * Z90)
    sigma_ln = np.maximum(sigma_ln, 1e-12)
    return mu_ln, sigma_ln


def build_market_distributions(
    inflation_rate_data: dict,
    electricity_prices_data: dict,
    interest_rate_data: dict,
    discount_rate_data: dict,
    project_lifetime: int,
):
    """
    Derive per-year distribution parameters from the 3 scenario paths provided.
    - Inflation, loan interest, discount: Normal(μ, σ) on linear scale.
    - Electricity price: Lognormal via (μ_ln, σ_ln) for stability (keeps > 0).
    Returns a dict with arrays of length == project_lifetime.
    """
    T = min(project_lifetime, 30)

    # pad to project lifetime
    P10_infl = pad_to_length(inflation_rate_data["pessimistic"], T)
    P50_infl = pad_to_length(inflation_rate_data["moderate"], T)
    P90_infl = pad_to_length(inflation_rate_data["optimistic"], T)
    infl_mu, infl_sigma = _mu_sigma_from_p10_p50_p90(P10_infl, P50_infl, P90_infl)

    P10_rate = pad_to_length(interest_rate_data["pessimistic"], T)
    P50_rate = pad_to_length(interest_rate_data["moderate"], T)
    P90_rate = pad_to_length(interest_rate_data["optimistic"], T)
    rate_mu, rate_sigma = _mu_sigma_from_p10_p50_p90(P10_rate, P50_rate, P90_rate)

    # expand discount rate to T
    P10_disc = np.full(T, discount_rate_data["pessimistic"][0], dtype=float)
    P50_disc = np.full(T, discount_rate_data["moderate"][0], dtype=float)
    P90_disc = np.full(T, discount_rate_data["optimistic"][0], dtype=float)
    disc_mu, disc_sigma = _mu_sigma_from_p10_p50_p90(P10_disc, P50_disc, P90_disc)

    P10_elec = pad_to_length(electricity_prices_data["pessimistic"], T)
    P50_elec = pad_to_length(electricity_prices_data["moderate"], T)
    P90_elec = pad_to_length(electricity_prices_data["optimistic"], T)
    elec_mu_ln, elec_sigma_ln = _log_mu_sigma_from_p10_p50_p90_prices(P10_elec, P50_elec, P90_elec)

    return {
        'inflation':  {'mu': infl_mu,  'sigma': infl_sigma,               'dist': 'normal',   'unit': '% y/y'},
        'loan_rate':  {'mu': rate_mu,  'sigma': rate_sigma,               'dist': 'normal',   'unit': '% y/y'},
        'discount':   {'mu': disc_mu,  'sigma': disc_sigma,               'dist': 'normal',   'unit': 'fraction'},
        'elec_price': {'mu_ln': elec_mu_ln, 'sigma_ln': elec_sigma_ln,    'dist': 'lognormal','unit': '€/kWh'},
        'T': T
    }

# ────────────────────────────────────────────────────────────────────────────────
# Scenario analysis function
# ────────────────────────────────────────────────────────────────────────────────

def get_kpi_results(
    capex: float,
    annual_maintenace_cost: float,
    annual_energy_savings: float,
    project_lifetime: int,
    loan_amount: float = 0.0,
    loan_term: int = 0,
    n_sims: int = 10000,
    seed: int = 42,
):
    """Enumerate KPI values over Cartesian product of macro-economic scenarios.

    The function uses distributions for **inflation**, **electricity prices**, **interest rates** and a
    scalar **discount rate**, in order to simulate the future cash-flows and economic indicators using a Monte Carlo approach. 

    Parameters
    ----------
    capex : float
        Up-front capital cost.
    annual_maintenace_cost : float
        O&M cost per year.
    annual_energy_savings : float
        Anticipated annual energy savings (kWh).
    project_lifetime : int
        Simulation horizon in years.
    loan_amount : float, default ``0.0``
        Principal borrowed. If ``0`` the analysis is *all-equity*.
    loan_term : int, default ``0``
        Repayment tenor (ignored if `loan_amount == 0`).
    n_sims : int, default ``10000``
        Number of Monte Carlo simulations.
    seed : int, default ``42``
        Random seed.

    Returns
    -------
    list[dict[str, Any]]
        One dictionary per scenario combination with raw cash-flows and all KPI
        values-probabilities calculated.
    """

    # ────────────────────────────────────────────────────────────────────────────
    # Input validation
    # ────────────────────────────────────────────────────────────────────────────

    # Validate capex
    if capex < 0:
        raise ValueError(f"capex must be non-negative, got: {capex}")

    # Validate annual_maintenace_cost
    if annual_maintenace_cost < 0:
        raise ValueError(f"annual_maintenace_cost must be non-negative, got: {annual_maintenace_cost}")

    # Validate annual_energy_savings
    if annual_energy_savings < 0:
        raise ValueError(f"annual_energy_savings must be non-negative, got: {annual_energy_savings}")

    # Validate project_lifetime
    if project_lifetime <= 0:
        raise ValueError(f"project_lifetime must be positive, got: {project_lifetime}")
    if project_lifetime > 30:
        raise ValueError(f"project_lifetime cannot exceed 30 years, got: {project_lifetime}")

    # Validate loan_amount
    if loan_amount < 0:
        raise ValueError(f"loan_amount must be non-negative, got: {loan_amount}")
    if loan_amount > capex:
        raise ValueError(f"loan_amount ({loan_amount}) cannot exceed capex ({capex})")

    # Validate loan_term
    if loan_term <= 0:
        raise ValueError(f"loan_term must be non-negative, got: {loan_term}")
    if loan_amount > 0 and loan_term == 0:
        raise ValueError(f"loan_term must be positive when loan_amount > 0, got loan_amount={loan_amount}, loan_term={loan_term}")
    if loan_term > project_lifetime:
        raise ValueError(f"loan_term ({loan_term}) cannot exceed project_lifetime ({project_lifetime})")

    # Validate n_sims
    if n_sims <= 0:
        raise ValueError(f"n_sims must be positive, got: {n_sims}")
    if n_sims > 1000000:
        raise ValueError(f"n_sims is too large (max 1,000,000), got: {n_sims}")

    # Validate seed
    if not isinstance(seed, int):
        raise ValueError(f"seed must be an integer, got: {type(seed).__name__}")

    # Check for invalid values

    project_lifetime = min(project_lifetime, 30)  # Cap at 30
    if project_lifetime < 0 or loan_term < 0 or n_sims <= 0:
        return {
            "percentiles": {
                "IRR": np.nan,
                "NPV": np.nan,
                "PBP": np.nan,
                "DPP": np.nan,
                "ROI": np.nan,
            },
            "probabilities": {
                "Pr(NPV > 0)": np.nan, # probability of investment being successfull (positive NPV)
                f"Pr(PBP < {project_lifetime}y)": np.nan, # probability of viable payback period
                f"Pr(DPP < {project_lifetime}y)": np.nan, # probability of viable discounted payback period
            },
            "disc_target_used": np.nan,
            "n_sims": 0,
        }
    
    # These values have been computed by ML models and are static (30 years ahead forecasts)
    #inflation_rate_data = {
    #    'optimistic': pad_to_length([4.70, 5.51, 4.77, 3.88, 4.29, 4.14, 3.44, 3.49, 3.54, 3.08, 2.92, 2.98, 2.71, 2.49, 2.48, 2.32, 2.11, 2.04, 1.94, 1.76, 1.65, 1.56, 1.41, 1.29, 1.20, 1.08, 0.95, 0.85, 0.74, 0.62], project_lifetime),
    #    'moderate': pad_to_length([6.11, 7.40, 6.96, 6.45, 7.20, 7.30, 6.87, 7.19, 7.48, 7.24, 7.33, 7.60, 7.54, 7.54, 7.74, 7.79, 7.77, 7.90, 7.99, 8.01, 8.09, 8.19, 8.23, 8.29, 8.39, 8.45, 8.50, 8.58, 8.65, 8.71], project_lifetime),
    #    'pessimistic': pad_to_length([7.515, 9.293, 9.162, 9.021, 10.11, 10.46, 10.29, 10.90, 11.41, 11.40, 11.73, 12.23, 12.38, 12.59, 13.00, 13.25, 13.44, 13.77, 14.05, 14.26, 14.53, 14.82, 15.05, 15.30, 15.57, 15.82, 16.05, 16.32, 16.56, 16.80], project_lifetime)
    #}

    inflation_rate_data = {
    'optimistic': pad_to_length([
        2.8, 2.4, 2.2, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0,  # Years 1-10
        2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0,  # Years 11-20
        2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0   # Years 21-30
    ], project_lifetime),
    
    'moderate': pad_to_length([
        3.0, 2.7, 2.5, 2.4, 2.3, 2.3, 2.4, 2.4, 2.5, 2.5,  # Years 1-10
        2.4, 2.4, 2.3, 2.3, 2.3, 2.3, 2.3, 2.3, 2.3, 2.3,  # Years 11-20
        2.2, 2.2, 2.2, 2.2, 2.2, 2.2, 2.2, 2.2, 2.2, 2.2   # Years 21-30
    ], project_lifetime),
    
    'pessimistic': pad_to_length([
        3.5, 3.3, 3.2, 3.0, 2.9, 2.8, 2.9, 3.0, 3.1, 3.2,  # Years 1-10
        3.2, 3.2, 3.1, 3.1, 3.0, 3.0, 3.0, 3.0, 2.9, 2.9,  # Years 11-20
        2.8, 2.8, 2.7, 2.7, 2.7, 2.6, 2.6, 2.6, 2.5, 2.5   # Years 21-30
    ], project_lifetime)
}

    electricity_prices_data = {
        'optimistic': pad_to_length([0.221, 0.229, 0.237, 0.245, 0.253, 0.261, 0.269, 0.277, 0.285, 0.293, 0.301, 0.310, 0.318, 0.326, 0.334, 0.342, 0.350, 0.358], project_lifetime),
        'moderate': pad_to_length([0.246, 0.254, 0.262, 0.270, 0.278, 0.286, 0.294, 0.302, 0.310, 0.318, 0.326, 0.335, 0.343, 0.351, 0.359, 0.367, 0.375, 0.383], project_lifetime),
        'pessimistic': pad_to_length([0.271, 0.279, 0.287, 0.295, 0.303, 0.311, 0.319, 0.327, 0.335, 0.343, 0.351, 0.360, 0.368, 0.376, 0.384, 0.392, 0.400, 0.408], project_lifetime)
    }

    #interest_rate_data = {
    #    'optimistic': pad_to_length([1.470, 0.145, -1.17, -2.29, -2.29, -2.29, -2.29, -2.29, -2.29, -2.29, -2.29, -2.29, -2.29, -2.29, -2.29, -2.29], project_lifetime),
    #    'moderate': pad_to_length([3.272, 1.947, 0.622, -0.49, -0.49, -0.49, -0.49, -0.49, -0.49, -0.49, -0.49, -0.49, -0.49, -0.49, -0.49, -0.49], project_lifetime),
    #    'pessimistic': pad_to_length([5.075, 3.750, 2.425, 1.312, 1.312, 1.312, 1.312, 1.312, 1.312, 1.312, 1.312, 1.312, 1.312, 1.312, 1.312, 1.00], project_lifetime)
    #}

    interest_rate_data = {
    'optimistic': pad_to_length([
        2.5, 2.8, 3.0, 3.0, 2.9, 2.8, 2.8, 2.7, 2.7, 2.7,  # Years 1-10
        2.6, 2.6, 2.6, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5,  # Years 11-20
        2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5   # Years 21-30
    ], project_lifetime),
    
    'moderate': pad_to_length([
        3.5, 3.8, 4.0, 4.0, 3.9, 3.8, 3.8, 3.7, 3.7, 3.7,  # Years 1-10
        3.6, 3.6, 3.6, 3.5, 3.5, 3.5, 3.5, 3.5, 3.5, 3.5,  # Years 11-20
        3.5, 3.5, 3.5, 3.5, 3.5, 3.5, 3.5, 3.5, 3.5, 3.5   # Years 21-30
    ], project_lifetime),
    
    'pessimistic': pad_to_length([
        5.0, 5.3, 5.5, 5.5, 5.4, 5.3, 5.3, 5.2, 5.2, 5.2,  # Years 1-10
        5.1, 5.1, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0,  # Years 11-20
        5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0   # Years 21-30
    ], project_lifetime)
}

    discount_rate_data = {
        "optimistic": [0.03],
        "moderate": [0.05],
        "pessimistic": [0.07],
    }

    dist_params = build_market_distributions(
        inflation_rate_data=inflation_rate_data,
        electricity_prices_data=electricity_prices_data,
        interest_rate_data=interest_rate_data,
        discount_rate_data=discount_rate_data,
        project_lifetime=project_lifetime,
    )
    get_kpi_results._market_distributions = dist_params

    # ────────────────────────────────────────────────────────────────────────────
    # Monte Carlo start
    # ────────────────────────────────────────────────────────────────────────────
    rng = np.random.default_rng(seed)
    T = project_lifetime
    
    # Draw samples from distributions (shape: n_sims × T)
    infl = rng.normal(dist_params['inflation']['mu'], dist_params['inflation']['sigma'], size=(n_sims, T))
    rate = rng.normal(dist_params['loan_rate']['mu'], dist_params['loan_rate']['sigma'], size=(n_sims, T))
    disc = rng.normal(dist_params['discount']['mu'], dist_params['discount']['sigma'], size=(n_sims, T))
    elec = np.exp(rng.normal(dist_params['elec_price']['mu_ln'], dist_params['elec_price']['sigma_ln'], size=(n_sims, T)))

    # safety guards for distribution samples
    infl = np.maximum(infl, -50.0)   
    rate = np.maximum(rate, -50.0)
    disc = np.maximum(disc, -0.99)   
    elec = np.maximum(elec, 1e-9)  

    # KPIs per simulation
    irr = np.full(n_sims, np.nan)
    npv = np.full(n_sims, np.nan)
    pbp = np.full(n_sims, np.nan)
    dpp = np.full(n_sims, np.nan)
    roi = np.full(n_sims, np.nan)

    for i in range(n_sims):
        elec_i = elec[i, :].tolist()
        infl_i = infl[i, :].tolist()
        rate_i = rate[i, :].tolist()
        disc_i = float(disc[i, 0])

        if loan_amount > 0 and loan_term > 0:
            flows = cash_flows_with_loan(
                capex, annual_energy_savings, annual_maintenace_cost, T,
                elec_i, infl_i, loan_amount, rate_i, loan_term
            )
            pbp_i = PBP(flows, loan=True, loan_term=loan_term)
            dpp_i = DPP(disc_i, T, flows, loan=True, loan_term=loan_term)
        else:
            flows = cash_flows(
                capex, annual_energy_savings, annual_maintenace_cost, T,
                elec_i, infl_i
            )
            pbp_i = PBP(flows)
            dpp_i = DPP(disc_i, T, flows)

        irr[i] = IRR(flows)
        npv[i] = NPV(disc_i, flows)
        pbp[i] = pbp_i
        dpp[i] = dpp_i
        roi[i] = ROI(flows)

    # ────────────────────────────────────────────────────────────────────────────
    # Payback periods: Keep NaN for scenarios with no payback within project lifetime
    # ────────────────────────────────────────────────────────────────────────────
    
    pbp_censored = pbp.copy()
    dpp_censored = dpp.copy()

    # summary (percentiles + event probabilities)
    def pct(a, qs=(5, 10, 25, 50, 75, 90, 95)):
        a = np.asarray(a, dtype=float)
        return {f"P{q}": np.nanpercentile(a, q) for q in qs}

    disc_target = float(np.nanmedian(disc[:, 0]))

    def pr(mask):
        m = np.asarray(mask, dtype=bool)
        return float(np.nanmean(m))

    summary = {
        "percentiles": {
            "IRR": pct(irr),
            "NPV": pct(npv),
            "PBP": pct(pbp_censored),  # NaN values excluded from percentiles
            "DPP": pct(dpp_censored),  # NaN values excluded from percentiles
            "ROI": pct(roi),
        },
        "probabilities": {
            "Pr(NPV > 0)": pr(npv > 0), # probability of investment being successfull (positive NPV)
            f"Pr(PBP ≤ {T}y)": pr((pbp <= T) & ~np.isnan(pbp)), # probability of viable payback period
            f"Pr(DPP ≤ {T}y)": pr((dpp <= T) & ~np.isnan(dpp)), # probability of viable discounted payback period
        },
        "disc_target_used": disc_target,
        "n_sims": n_sims,
    }
    print("Monte Carlo summary:", summary)

    # --------- Histograms with P10–P90 band and P50 line ----------
    fig, axs = plt.subplots(2, 3, figsize=(14, 8))
    axs = axs.ravel()

    data = [
        ("IRR", irr),
        ("NPV", npv),
        ("PBP", pbp_censored),
        ("DPP", dpp_censored),
        ("ROI", roi),
    ]

    for ax, (name, arr) in zip(axs, data):
        a = np.asarray(arr, dtype=float)
        a = a[np.isfinite(a)]

        if name in ("PBP", "DPP"):
            # Any payback > project lifetime is infeasible (including NaN)
            infeasible_mask = (a > T) | np.isnan(a)
        elif name in ("NPV", "IRR", "ROI"):
            # negative performance = infeasible / undesirable
            infeasible_mask = (a < 0)
        else:
            infeasible_mask = np.zeros_like(a, dtype=bool)

        feasible = a[~infeasible_mask]
        infeasible = a[infeasible_mask]

        if feasible.size > 0:
            ax.hist(feasible, bins=30, alpha=0.7, label="Feasible")

        if infeasible.size > 0:
            ax.hist(infeasible, bins=30, alpha=0.7, color="red", label="Infeasible")
        # percentiles (P10, P50, P90) on the full (censored) data
        if a.size > 0:
            p10, p50, p90 = np.percentile(a, [10, 50, 90])

            ax.axvspan(p10, p90, alpha=0.15, label="P10–P90")
            ax.axvline(p10, linestyle="--", linewidth=1, label=f"P10={p10:.3g}")
            ax.axvline(p50, linestyle="-", linewidth=1.5, label=f"P50={p50:.3g}")
            ax.axvline(p90, linestyle="--", linewidth=1, label=f"P90={p90:.3g}")

        # Mark project lifetime boundary for payback periods
        if name in ("PBP", "DPP"):
            ax.axvline(
                T,
                linestyle="-",
                linewidth=2,
                color="black",
                label=f"Project lifetime ({T}y)",
            )
        ax.set_title(f"{name} (P10–P90 band, P50)")
        ax.set_xlabel(name)
        ax.set_ylabel("Frequency")
        ax.grid(True, axis="y", linestyle="--", alpha=0.4)
        ax.legend(loc="best", frameon=False)

    ax = axs[5]   # last subplot

    labels = [
        "Pr(NPV > 0)",
        f"Pr(PBP < {T}y)",
        f"Pr(DPP < {T}y)",
    ]
    values = [
        summary["probabilities"]["Pr(NPV > 0)"],
        summary["probabilities"][f"Pr(PBP < {T}y)"],
        summary["probabilities"][f"Pr(DPP < {T}y)"]
    ]

    ax.bar(labels, values, color=["royalblue", "blue", "navy"], alpha=0.8)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Probability")
    ax.set_title("Success Probabilities")
    ax.grid(True, axis="y", linestyle="--", alpha=0.4)

    for i, v in enumerate(values):
        ax.text(i, v + 0.02, f"{v:.2f}", ha="center", fontsize=9)


    plt.tight_layout()
    plt.show()

    return {
        "irr": irr,
        "npv": npv,
        "pbp": pbp,
        "dpp": dpp,
        "roi": roi,
        "summary": summary,
    }


# ────────────────────────────────────────────────────────────────────────────────
# Example usage
# ────────────────────────────────────────────────────────────────────────────────

capex = 60000
annual_energy_savings = 27400
annual_maintenace_cost = 2000
project_lifetime = 20
loan_amount = 25000
loan_term = 15

# With loan
kpis_with_loan = get_kpi_results(
    capex,
    annual_maintenace_cost,
    annual_energy_savings,
    project_lifetime,
    loan_amount,
    loan_term,
)
print("KPI results with loan:", kpis_with_loan)

