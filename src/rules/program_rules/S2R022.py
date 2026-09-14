"""
Women, Infants and Children program eligibility rule (S2R022)
"""

from __future__ import annotations

from src.rules.base_rule import BaseRule
from src.rules.registry import register_rule
from src.models.enums import IncomeType
from src.rules.thresholds import income_at_or_below


@register_rule
class WomenInfantsChildren(BaseRule):
    program = "S2R022"
    description = "Women, Infants and Children (WIC) (NYS DOH) - Nutrition assistance for pregnant women and young children"

    @classmethod
    def evaluate(cls, request) -> bool:
        """
        Eligibility requires:
        1. At least one person who is pregnant or under age 5
        2. Either:
           a. Household income below thresholds based on household size
           b. At least one person has Medicaid, Disability Medicaid, or Cash Assistance (medicaid, disability medicaid, or cash assistance)
        """
        persons = request.person
        household_size = len(persons)
        
        # Check for pregnant person or child under 5
        has_eligible_person = any(
            p.pregnant or p.age < 5
            for p in persons
        )
        
        if not has_eligible_person:
            return False
        
        if cls._has_medicaid_or_cash_assistance(persons):
            return True

        return income_at_or_below(request, cls.program, household_size)

    @classmethod
    def _has_medicaid_or_cash_assistance(cls, persons) -> bool:
        """
        Check if any person has Medicaid, Disability Medicaid, or Cash Assistance.
        """
        for person in persons:
            # Check for Medicaid or Disability Medicaid benefits
            if person.benefits_medicaid or person.benefits_medicaid_disability:
                return True
            
            # Check for Cash Assistance income
            for income in person.incomes:
                if income.type == IncomeType.CASH_ASSISTANCE:
                    return True
        
        return False
