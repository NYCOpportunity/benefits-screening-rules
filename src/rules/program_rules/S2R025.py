"""
Older Adult Employment Program eligibility rule (S2R025)
"""

from __future__ import annotations

from src.rules.base_rule import BaseRule
from src.rules.registry import register_rule
from src.rules.thresholds import income_at_or_below


@register_rule
class OlderAdultEmploymentProgram(BaseRule):
    program = "S2R025"
    description = "Older Adult Employment Program (DFTA) - Employment assistance for seniors aged 55+"

    @classmethod
    def evaluate(cls, request) -> bool:
        """
        Eligibility requires:
        1. At least one person aged 55+ who is unemployed
        2. Total yearly household income at or below the threshold for household size
        """
        persons = request.person
        household_size = len(persons)

        if not any(person.age >= 55 and person.unemployed for person in persons):
            return False

        return income_at_or_below(request, cls.program, household_size)
