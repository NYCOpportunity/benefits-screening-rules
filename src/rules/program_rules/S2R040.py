"""
Child Care Voucher program eligibility rule (S2R040)
"""

from __future__ import annotations

from src.rules.base_rule import BaseRule
from src.rules.registry import register_rule
from src.rules.thresholds import income_at_or_below


@register_rule
class ChildCareVoucher(BaseRule):
    program = "S2R040"
    description = "Child Care Voucher (ACS) - Financial assistance for child care expenses"

    @classmethod
    def evaluate(cls, request) -> bool:
        """
        Eligibility requires:
        1. At least one eligible dependent:
           - Child age 13 or under, OR
           - Blind or disabled person age 19 or under
        2. Either:
           - Child care voucher household income at or below thresholds by
             eligible household size (2-8 members), OR
           - Household receives Cash Assistance
        """
        persons = request.person

        has_eligible_dependent = any(
            person.age <= 13
            or (person.age <= 19 and (person.disabled or person.blind))
            for person in persons
        )
        if not has_eligible_dependent:
            return False

        if request.income_household_has_cash_assistance:
            return True

        return income_at_or_below(
            request, cls.program, request.child_care_voucher_household_members
        )
