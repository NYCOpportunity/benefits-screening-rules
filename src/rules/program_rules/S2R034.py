"""
Fair Fares eligibility rule (S2R034)
"""

from __future__ import annotations

from src.rules.base_rule import BaseRule
from src.rules.registry import register_rule
from src.rules.thresholds import income_at_or_below


@register_rule
class FairFares(BaseRule):
    program = "S2R034"
    description = "Fair Fares (HRA) - Half-price MetroCards for low-income New Yorkers"

    @classmethod
    def evaluate(cls, request) -> bool:
        """
        Eligibility requires:
        1. At least one person aged 18-64
        2. Household yearly income below thresholds based on household size
        """
        persons = request.person
        household_size = len(persons)
        
        # Check for adult aged 18-64
        has_eligible_adult = any(
            18 <= p.age <= 64
            for p in persons
        )
        
        if not has_eligible_adult:
            return False

        return income_at_or_below(request, cls.program, household_size)
