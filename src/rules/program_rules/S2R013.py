"""
Section 8 Housing eligibility rule (S2R013)
"""

from __future__ import annotations

from src.models.enums import HouseholdMemberType
from src.rules.base_rule import BaseRule
from src.rules.registry import register_rule
from src.rules.thresholds import income_at_or_below


@register_rule
class Section8Housing(BaseRule):
    program = "S2R013"
    description = "Section 8 Housing (NYCHA) - Housing assistance voucher program"

    @classmethod
    def evaluate(cls, request) -> bool:
        """
        Eligibility requires:
        1. Head of household is 18 or older
        2. Household income below thresholds based on household size
        """
        persons = request.person
        household_size = len(persons)

        has_adult_head = any(
            p.household_member_type == HouseholdMemberType.HEAD_OF_HOUSEHOLD and p.age >= 18
            for p in persons
        )
        
        if not has_adult_head:
            return False

        return income_at_or_below(request, cls.program, household_size)
