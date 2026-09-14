"""
Child Tax Credit eligibility rule (S2R004)
"""

from __future__ import annotations

from src.rules.base_rule import BaseRule
from src.rules.registry import register_rule
from src.rules.thresholds import scalar_limit


@register_rule
class ChildTaxCredit(BaseRule):
    program = "S2R004"
    description = "Child Tax Credit (DCA/IRS) - Tax credit for households with children under 17"

    @classmethod
    def evaluate(cls, request) -> bool:
        """
        Eligibility requires:
        1. At least one child under 17 in household
        2. Household yearly income at or above the minimum and at or below the
           marital-status cap (see thresholds.yaml for this program rule)
        """
        persons = request.person
        
        # Check if any child under 17
        has_eligible_child = any(p.age < 17 for p in persons)
        if not has_eligible_child:
            return False
        
        # Check income range
        yearly_income = request.income_household_total_yearly
        minimum = scalar_limit("S2R004", "minimum")
        if minimum is None or yearly_income < minimum:
            return False

        threshold_key = "married" if request.head_of_household_married else "single"
        threshold = scalar_limit("S2R004", threshold_key)
        if threshold is None:
            return False

        return yearly_income <= threshold
