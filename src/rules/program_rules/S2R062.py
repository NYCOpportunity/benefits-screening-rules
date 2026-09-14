"""
Summer EBT eligibility rule (S2R062)
"""

from __future__ import annotations

from src.rules.base_rule import BaseRule
from src.rules.registry import register_rule
from src.models.enums import IncomeType
from src.rules.thresholds import income_at_or_below


@register_rule
class SummerEBT(BaseRule):
    program = "S2R062"
    description = "Summer EBT - Food benefits for eligible school-age children"

    @classmethod
    def evaluate(cls, request) -> bool:
        """
        Eligibility requires at least one child aged 6-16 and either:
        1. Medicaid, disability-related Medicaid, or Cash Assistance, or
        2. Total monthly household income at or below size-based thresholds
        """
        persons = request.person
        household_size = len(persons)

        if not any(6 <= person.age <= 16 for person in persons):
            return False

        if cls._has_categorical_eligibility(persons):
            return True

        return income_at_or_below(request, cls.program, household_size)

    @classmethod
    def _has_categorical_eligibility(cls, persons) -> bool:
        for person in persons:
            if person.benefits_medicaid or person.benefits_medicaid_disability:
                return True

            for income in person.incomes:
                if income.type == IncomeType.CASH_ASSISTANCE:
                    return True

        return False
