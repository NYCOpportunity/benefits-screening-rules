"""
Cash Assistance eligibility rule (S2R010)
"""

from __future__ import annotations

from src.rules.base_rule import BaseRule
from src.rules.registry import register_rule
from src.rules.thresholds import pathway_limit


@register_rule
class CashAssistance(BaseRule):
    program = "S2R010"
    description = "Cash Assistance (HRA) - Financial assistance program with income-based eligibility"

    @classmethod
    def evaluate(cls, request) -> bool:
        """
        Eligibility based on income thresholds that vary by:
        1. Household size
        2. Whether any person is ≤18 or pregnant (higher thresholds)
        """
        persons = request.person
        household_size = len(persons)

        # Check if any person is ≤18 or pregnant
        has_child_or_pregnant = any(p.age <= 18 or p.pregnant for p in persons)

        # Get monthly income after work expense deduction
        monthly_income = request.income_household_monthly_ca_minus_work_expense

        pathway = "with_child_or_pregnant" if has_child_or_pregnant else "general"
        threshold = pathway_limit("S2R010", pathway, household_size)
        if threshold is None:
            return False

        return monthly_income < threshold
