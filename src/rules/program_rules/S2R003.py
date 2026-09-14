"""
Infants & Toddlers eligibility rule (S2R003)
"""

from __future__ import annotations

from src.rules.base_rule import BaseRule
from src.rules.registry import register_rule
from src.rules.thresholds import income_at_or_below


@register_rule
class InfantsToddlers(BaseRule):
    program = "S2R003"
    description = "Infants & Toddlers (DOE) - Early intervention services for children under 3 years old"

    @classmethod
    def evaluate(cls, request) -> bool:
        """
        Eligibility requires:
        1. At least one person age 5 or younger
        2. Adults-and-children monthly income at or below the threshold for household size
        """
        persons = request.person
        household_size = len(persons)

        if not any(person.age <= 5 for person in persons):
            return False

        return income_at_or_below(request, cls.program, household_size)
