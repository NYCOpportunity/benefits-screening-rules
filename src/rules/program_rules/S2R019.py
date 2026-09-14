"""
Home Energy Assistance Program eligibility rule (S2R019)
"""

from __future__ import annotations

from src.rules.base_rule import BaseRule
from src.rules.registry import register_rule
from src.rules.thresholds import income_at_or_below


@register_rule
class HomeEnergyAssistanceProgram(BaseRule):
    program = "S2R019"
    description = "Home Energy Assistance Program (HEAP) (HRA) - Help with heating costs for vulnerable households"

    @classmethod
    def evaluate(cls, request) -> bool:
        """
        Eligibility requires any of:
        1. Household receives Cash Assistance (any household size)
        2. Household receives SSI (single-member households only)
        3. Total monthly household income at or below size-based thresholds
        """
        household_size = len(request.person)

        if request.income_household_has_cash_assistance:
            return True

        if household_size == 1 and request.income_household_has_ssi:
            return True

        return income_at_or_below(request, cls.program, household_size)
