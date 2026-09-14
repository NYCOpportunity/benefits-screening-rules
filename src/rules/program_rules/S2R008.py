"""
Head Start early childhood education program eligibility rule (S2R008)
"""

from __future__ import annotations

from src.rules.base_rule import BaseRule
from src.rules.registry import register_rule
from src.models.enums import HouseholdMemberType
from src.rules.thresholds import income_at_or_below


@register_rule
class HeadStart(BaseRule):
    program = "S2R008"
    description = "Head Start (DOE) - Free early childhood education for children aged 3-4"

    @classmethod
    def evaluate(cls, request) -> bool:
        """
        Eligibility follows:
        1. Child age 5 or younger and one of the following:
            a. Household has Cash Assistance or SSI household income OR
            b. Household's yearly income is within household-size limits OR
            c. Foster child of Head of Household (when income exceeds limits)
        """
        persons = request.person
        household_size = len(persons)

        if not cls._has_child_age_five_or_younger(persons):
            return False

        if cls._has_cash_assistance_or_ssi(request):
            return True

        if income_at_or_below(request, cls.program, household_size):
            return True

        return cls._has_foster_child_of_head(persons, request)

    @classmethod
    def _has_child_age_five_or_younger(cls, persons) -> bool:
        return any(person.age <= 5 for person in persons)

    @classmethod
    def _has_cash_assistance_or_ssi(cls, request) -> bool:
        return (
            request.income_household_has_cash_assistance
            or request.income_household_has_ssi
        )

    @classmethod
    def _has_foster_child_of_head(cls, persons, request) -> bool:
        has_head_of_household = any(
            person.household_member_type == HouseholdMemberType.HEAD_OF_HOUSEHOLD
            for person in persons
        )
        return has_head_of_household and request.foster_children > 0
