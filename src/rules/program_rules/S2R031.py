"""
NYC Care health access program eligibility rule (S2R031)
"""

from __future__ import annotations

from src.rules.base_rule import BaseRule
from src.rules.registry import register_rule
from src.rules.thresholds import income_at_or_below


@register_rule
class NYCCare(BaseRule):
    program = "S2R031"
    description = "NYC Care - Low-cost healthcare for those without insurance"

    @classmethod
    def evaluate(cls, request) -> bool:
        """
        Eligibility requires:
        1. At least one person without Medicaid benefits
        2. Household monthly income below thresholds based on household size
        """
        persons = request.person
        household_size = len(persons)
        
        # Check for person without Medicaid
        has_uninsured = any(
            not p.benefits_medicaid and not p.benefits_medicaid_disability
            for p in persons
        )
        
        if not has_uninsured:
            return False

        return income_at_or_below(request, cls.program, household_size)
