"""
Lifeline phone service discount eligibility rule (S2R043)
"""

from __future__ import annotations

from src.rules.base_rule import BaseRule
from src.rules.registry import register_rule
from src.models.enums import LivingRentalType
from src.rules.thresholds import income_at_or_below


@register_rule
class Lifeline(BaseRule):
    program = "S2R043"
    description = "Lifeline (MOCTO) - Discounted phone service for low-income households"

    @classmethod
    def evaluate(cls, request) -> bool:
        """
        Eligibility requires ANY of:
        1. At least one person has Medicaid benefits
        2. Household has certain government benefits (Veteran, SSI, SS benefits)
        3. Living in NYCHA housing
        4. Household income below thresholds based on household size
        """
        household = request.household[0]
        persons = request.person
        household_size = len(persons)
        
        # Check condition 1: Medicaid benefits
        has_medicaid = any(
            p.benefits_medicaid or p.benefits_medicaid_disability
            for p in persons
        )
        if has_medicaid:
            return True
        
        # Check condition 2: Has government benefits (Veteran, SSI, SS)
        if request.income_household_has_benefit:
            return True
        
        # Check condition 3: NYCHA resident
        if household.living_renting and household.living_rental_type == LivingRentalType.NYCHA:
            return True

        return income_at_or_below(request, cls.program, household_size)
