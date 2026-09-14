"""
NYC Free Tax Prep eligibility rule (S2R039)
"""

from __future__ import annotations

from src.rules.base_rule import BaseRule
from src.rules.registry import register_rule
from src.models.enums import HouseholdMemberType
from src.rules.thresholds import scalar_limit


@register_rule
class NYCFreeTaxPrep(BaseRule):
    program = "S2R039"
    description = "NYC Free Tax Prep (DCA) - Free tax preparation services for low-income households"

    DEPENDENT_CHILD_TYPES = {
        HouseholdMemberType.CHILD,
        HouseholdMemberType.STEP_CHILD,
        HouseholdMemberType.FOSTER_CHILD,
    }

    @classmethod
    def evaluate(cls, request) -> bool:
        """
        Eligibility requires either:
        1. Household yearly income at or below the general limit, or
        2. Multi-person household with a child, stepchild, or foster child
           and household yearly income at or below the with_dependent_child limit
        (see thresholds.yaml for this program rule)
        """
        yearly_income = request.income_household_total_yearly
        general_limit = scalar_limit("S2R039", "general")
        if general_limit is not None and yearly_income <= general_limit:
            return True

        dependent_limit = scalar_limit("S2R039", "with_dependent_child")
        if dependent_limit is None:
            return False

        persons = request.person
        if len(persons) > 1 and cls._has_dependent_child(persons):
            return yearly_income <= dependent_limit

        return False

    @classmethod
    def _has_dependent_child(cls, persons) -> bool:
        return any(
            person.household_member_type in cls.DEPENDENT_CHILD_TYPES
            for person in persons
        )
