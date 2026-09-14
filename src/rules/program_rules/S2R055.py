"""
NYC Housing Connect eligibility rule (S2R055)
"""

from __future__ import annotations

from src.rules.base_rule import BaseRule
from src.rules.registry import register_rule
from src.rules.thresholds import income_at_or_below, scalar_limit


@register_rule
class NYCHousingConnect(BaseRule):
    program = "S2R055"
    description = "NYC Housing Connect (HPD) - Affordable housing lottery and application portal"

    @classmethod
    def evaluate(cls, request) -> bool:
        """
        Eligibility requires:
        1. At least one person aged 18 or older
        2. Household cash on hand at or below cash_on_hand_maximum
           (see thresholds.yaml for this program rule)
        3. Household yearly income below thresholds based on household size
        """
        household = request.household[0]
        persons = request.person
        household_size = len(persons)
        
        # Check for adult (18+)
        has_adult = any(p.age >= 18 for p in persons)
        
        if not has_adult:
            return False
        
        cash_on_hand_maximum = scalar_limit("S2R055", "cash_on_hand_maximum")
        if cash_on_hand_maximum is None:
            return False

        if (
            household.cash_on_hand is not None
            and household.cash_on_hand > cash_on_hand_maximum
        ):
            return False

        return income_at_or_below(request, cls.program, household_size)
