"""
Validate that every data field referenced in the Visualization Guide
(RISK_ASSESSMENT_API_FRONTEND_CHANGELOG.md) is present and correctly
structured in the API response.
"""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "relife_financial" / "Indicator Modules"))

from relife_financial.models.risk_assessment import RiskAssessmentRequest
from relife_financial.services.risk_assessment import perform_risk_assessment

PASS = []
FAIL = []
T = 15  # project_lifetime used in requests


def check(label: str, condition: bool, detail: str = ""):
    if condition:
        PASS.append(label)
    else:
        FAIL.append(f"{label}  {detail}")


async def run():
    private_resp = await perform_risk_assessment(
        RiskAssessmentRequest.model_validate({
            "capex": 60000,
            "annual_energy_savings": 27400,
            "annual_maintenance_cost": 2000,
            "project_lifetime": T,
            "output_level": "private",
            "schemes": [{"scheme_type": "equity"}],
            "indicators": ["NPV", "IRR", "PBP", "ROI"],
        })
    )
    prof_resp = await perform_risk_assessment(
        RiskAssessmentRequest.model_validate({
            "capex": 60000,
            "annual_energy_savings": 27400,
            "annual_maintenance_cost": 2000,
            "project_lifetime": T,
            "output_level": "professional",
            "schemes": [
                {"scheme_type": "equity"},
                {"scheme_type": "bank_loan", "loan_amount": 25000, "term_years": 10},
                {"scheme_type": "epc_shared_savings", "p_ESCO": 0.30, "term_years": 8},
            ],
            "indicators": ["NPV", "IRR", "PBP", "ROI"],
        })
    )
    return private_resp, prof_resp


private_resp, prof_resp = asyncio.run(run())

# ══════════════════════════════════════════════════════════════════
# PRIVATE — bar chart data
# ══════════════════════════════════════════════════════════════════
eq = private_resp.results["equity"]
cf = eq["cashflow_distributions"]
summary = eq["summary"]

check("private: cashflow_distributions present", cf is not None)
check("private: years array correct length", len(cf["years"]) == T + 1, f"got {len(cf['years'])}")
check("private: years[0] == 0", cf["years"][0] == 0)
check("private: years[-1] == project_lifetime", cf["years"][-1] == T)
check("private: cash_flows.P50 correct length", len(cf["cash_flows"]["P50"]) == T + 1)
check("private: Year 0 is negative (investment outlay)", cf["cash_flows"]["P50"][0] < 0)
check("private: inflows present", "inflows" in cf)
check("private: outflows present", "outflows" in cf)
check("private: inflows.P50 correct length", len(cf["inflows"]["P50"]) == T + 1)
check("private: outflows.P50 correct length", len(cf["outflows"]["P50"]) == T + 1)

# PRIVATE — summary card P50 values
percs = summary["percentiles"]
for kpi in ["NPV", "IRR", "PBP", "ROI"]:
    check(f"private: {kpi}.P50 present", "P50" in percs.get(kpi, {}))

# PRIVATE — probabilities for plain-language sentence
probs = summary.get("probabilities", {})
check("private: Pr(NPV > 0) present", "Pr(NPV > 0)" in probs)
pbp_key = f"Pr(PBP < {T}y)"
check(f"private: {pbp_key} present", pbp_key in probs)
check("private: Pr(NPV > 0) is 0–1 float", isinstance(probs.get("Pr(NPV > 0)"), float)
      and 0 <= probs["Pr(NPV > 0)"] <= 1)

# PRIVATE — no histograms
check("private: kpi_histograms absent (correct for private)", "kpi_histograms" not in eq)

# PRIVATE — scheme metadata for card
check("private: scheme_family present", "scheme_family" in eq)
check("private: scheme_id present", "scheme_id" in eq)

# ══════════════════════════════════════════════════════════════════
# PROFESSIONAL — fan chart (all 5 percentile bands)
# ══════════════════════════════════════════════════════════════════
eq_p = prof_resp.results["equity"]
cf_p = eq_p["cashflow_distributions"]

for band in ["P5", "P10", "P50", "P90", "P95"]:
    check(f"prof: cash_flows.{band} present", band in cf_p["cash_flows"])
    check(f"prof: inflows.{band} present", band in cf_p["inflows"])
    check(f"prof: outflows.{band} present", band in cf_p["outflows"])
    check(
        f"prof: cash_flows.{band} correct length",
        len(cf_p["cash_flows"][band]) == T + 1,
        f"got {len(cf_p['cash_flows'][band])}",
    )

# PROFESSIONAL — KPI histograms
hist = eq_p.get("kpi_histograms", {})
check("prof: kpi_histograms present", bool(hist))
for kpi in ["NPV", "IRR", "ROI", "PBP", "DPP"]:
    check(f"prof: histogram {kpi} present", kpi in hist)
    if kpi in hist:
        h = hist[kpi]
        check(f"prof: histogram {kpi}.bin_edges non-empty", "bin_edges" in h and len(h["bin_edges"]) > 1)
        check(f"prof: histogram {kpi}.feasible_counts non-empty", "feasible_counts" in h and len(h["feasible_counts"]) > 0)
        check(f"prof: histogram {kpi}.infeasible_counts non-empty", "infeasible_counts" in h and len(h["infeasible_counts"]) > 0)
        n_bins = len(h["bin_edges"]) - 1
        check(f"prof: histogram {kpi} edges = counts + 1", len(h["feasible_counts"]) == n_bins)
        check(f"prof: histogram {kpi} infeasible same length", len(h["infeasible_counts"]) == n_bins)
        total = sum(h["feasible_counts"]) + sum(h["infeasible_counts"])
        # DPP/PBP: some scenarios never pay back — those are excluded from histogram bins
        # so total may be < 10000 for those KPIs; we allow down to 50%
        min_expected = 5000 if kpi in ("DPP", "PBP") else 9800
        check(f"prof: histogram {kpi} counts sum plausible",
              total >= min_expected, f"got sum={total}")
        check(f"prof: histogram {kpi}.p50 present", "p50" in h)
        check(f"prof: histogram {kpi}.p10 present", "p10" in h)
        check(f"prof: histogram {kpi}.p90 present", "p90" in h)

# PROFESSIONAL — probabilities for gauges
probs_p = eq_p["summary"].get("probabilities", {})
pbp_key_p = f"Pr(PBP < {T}y)"
dpp_key_p = f"Pr(DPP < {T}y)"
check("prof: Pr(NPV > 0) present", "Pr(NPV > 0)" in probs_p)
check(f"prof: {pbp_key_p} present", pbp_key_p in probs_p)
check(f"prof: {dpp_key_p} present", dpp_key_p in probs_p)
for key in ["Pr(NPV > 0)", pbp_key_p, dpp_key_p]:
    if key in probs_p:
        check(f"prof: {key} is 0–1 float",
              isinstance(probs_p[key], float) and 0 <= probs_p[key] <= 1)

# PROFESSIONAL — percentile table P10/P50/P90
for kpi in ["NPV", "IRR", "PBP", "ROI"]:
    for band in ["P10", "P50", "P90"]:
        check(f"prof: {kpi}.{band} present",
              band in eq_p["summary"]["percentiles"].get(kpi, {}))

# PROFESSIONAL — disc_target_used for NPV annotation
check("prof: disc_target_used present", "disc_target_used" in eq_p["summary"])
check("prof: disc_target_used > 0",
      isinstance(eq_p["summary"].get("disc_target_used"), (int, float))
      and eq_p["summary"]["disc_target_used"] > 0)

# PROFESSIONAL — multi-scheme comparison
check("prof: 3 schemes returned", len(prof_resp.results) == 3)
for st in ["equity", "bank_loan", "epc_shared_savings"]:
    check(f"prof: scheme {st} present", st in prof_resp.results)

# scheme_family for colour coding
expected_families = {
    "equity": "self_financed",
    "bank_loan": "debt_financed",
    "epc_shared_savings": "esco_zero_capex",
}
for st, expected in expected_families.items():
    actual = prof_resp.results.get(st, {}).get("scheme_family")
    check(f"prof: {st} scheme_family == {expected}", actual == expected, f"got {actual!r}")

# All 3 schemes have histograms and fan chart
for st in ["equity", "bank_loan", "epc_shared_savings"]:
    if st in prof_resp.results:
        s = prof_resp.results[st]
        check(f"prof: {st} has kpi_histograms", "kpi_histograms" in s)
        check(f"prof: {st} has all 5 cf bands",
              all(b in s["cashflow_distributions"]["cash_flows"] for b in ["P5","P10","P50","P90","P95"]))
        check(f"prof: {st} NPV.P50 present",
              "P50" in s["summary"]["percentiles"].get("NPV", {}))

# ══════════════════════════════════════════════════════════════════
print(f"\n{'='*60}")
print(f"  PASSED: {len(PASS)}/{len(PASS)+len(FAIL)}")
if FAIL:
    print(f"  FAILED: {len(FAIL)}")
    for f in FAIL:
        print(f"    ❌ {f}")
else:
    print("  ✅ All checks passed — visualization guide is fully doable.")
print(f"{'='*60}")
