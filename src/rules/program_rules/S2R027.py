"""
Commodity Supplemental Food Program eligibility rule (S2R027)
"""

from __future__ import annotations

from src.rules.base_rule import BaseRule
from src.rules.registry import register_rule
from src.rules.thresholds import income_at_or_below


@register_rule
class CommoditySupplementalFoodProgram(BaseRule):
    program = "S2R027"
    description = "Commodity Supplemental Food Program (CSFP) (NYS DOH) - Food assistance for seniors"

    @classmethod
    def evaluate(cls, request) -> bool:
        """
        Eligibility requires:
        1. At least one person aged 60 or older
        2. Household income below thresholds based on household size
        """
        persons = request.person
        household_size = len(persons)
        
        # Check for senior (60+)
        has_senior = any(p.age >= 60 for p in persons)
        
        if not has_senior:
            return False

        return income_at_or_below(request, cls.program, household_size)
