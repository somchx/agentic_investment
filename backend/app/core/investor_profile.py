"""Investor Context Layer, part 1: the profile data model (PROPOSAL.md
Contribution 4). Deliberately not backed by a real portfolio database or
market data feed -- these are synthetic, structured inputs for the
personalization experiment, not a portfolio management system.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class InvestorProfile:
    name: str  # human-readable label for reporting, e.g. "Aggressive, small position"
    risk_tolerance: str  # "low" | "medium" | "high"
    investment_horizon: str  # "<1y" | "1-5y" | ">5y"
    position_size_pct: float  # this holding as % of the investor's total portfolio
    objective: str  # "growth" | "income" | "preservation"


# Four synthetic profiles spanning the interaction the experiment is meant to
# surface: severity of the same evidence should matter more to B than to A.
PROFILE_A = InvestorProfile(
    name="Aggressive, long horizon, small position",
    risk_tolerance="high", investment_horizon=">5y",
    position_size_pct=3.0, objective="growth",
)
PROFILE_B = InvestorProfile(
    name="Conservative, short horizon, large position",
    risk_tolerance="low", investment_horizon="<1y",
    position_size_pct=25.0, objective="preservation",
)
PROFILE_C = InvestorProfile(
    name="Moderate, medium horizon, medium position",
    risk_tolerance="medium", investment_horizon="1-5y",
    position_size_pct=10.0, objective="income",
)
PROFILE_D = InvestorProfile(
    name="Conservative, long horizon, large position",
    risk_tolerance="low", investment_horizon=">5y",
    position_size_pct=20.0, objective="preservation",
)

ALL_PROFILES = [PROFILE_A, PROFILE_B, PROFILE_C, PROFILE_D]
