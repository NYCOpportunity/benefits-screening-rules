"""
S2R058 eligibility rule
"""

from __future__ import annotations

from src.rules.base_rule import BaseRule
from src.rules.registry import register_rule
from src.rules.thresholds import income_at_or_below


@register_rule
class S2R058(BaseRule):
    program = "S2R058"
    description = (
        "Healthcare coverage for adults aged 19-64 without Medicaid, "
        "based on household income"
    )

    @classmethod
    def evaluate(cls, request) -> bool:
        """
        Eligibility requires:
        1. At least one person aged 19-64 without Medicaid benefits
        2. Household yearly income below thresholds based on household size
        """
        persons = request.person
        household_size = len(persons)

        has_eligible_adult = any(
            19 <= p.age <= 64
            and not p.benefits_medicaid
            and not p.benefits_medicaid_disability
            for p in persons
        )

        if not has_eligible_adult:
            return False

        return income_at_or_below(request, cls.program, household_size)
