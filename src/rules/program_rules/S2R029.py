"""
Nurse-Family Partnership eligibility rule (S2R029)
"""

from __future__ import annotations

from src.rules.base_rule import BaseRule
from src.rules.registry import register_rule
from src.rules.thresholds import income_at_or_below


@register_rule
class NurseFamilyPartnership(BaseRule):
    program = "S2R029"
    description = "Nurse-Family Partnership (DOHMH) - Prenatal and postnatal support for first-time mothers"

    @classmethod
    def evaluate(cls, request) -> bool:
        """
        Eligibility requires at least one pregnant person and either:
        1. That pregnant person receives Medicaid or disability-related Medicaid, or
        2. Household yearly income at or below thresholds based on members plus pregnant
        """
        persons = request.person

        for person in persons:
            if person.pregnant and (
                person.benefits_medicaid or person.benefits_medicaid_disability
            ):
                return True

        has_pregnant = any(p.pregnant for p in persons)
        if not has_pregnant:
            return False

        return income_at_or_below(request, cls.program, request.members_plus_pregnant)
