"""
Earned Income Tax Credit eligibility rule (S2R006)
"""

from __future__ import annotations

from src.rules.base_rule import BaseRule
from src.rules.registry import register_rule
from src.models.enums import HouseholdMemberType
from src.rules.thresholds import pathway_limit, scalar_limit


@register_rule
class EarnedIncomeTaxCredit(BaseRule):
    program = "S2R006"
    description = "Earned Income Tax Credit (EITC) (DCA/IRS) - Tax credit based on marital status, children, and income"

    @classmethod
    def evaluate(cls, request) -> bool:
        """
        Eligibility follows five pathways based on marital status,
        qualifying children, investment income, earned income, and age.
        """
        persons = request.person
        head = cls._get_head_of_household(persons)
        spouse = cls._get_spouse(persons)
        is_married = request.head_of_household_married
        num_qualifying_children = request.children_student_blind_disabled_eitc

        if cls._head_or_spouse_has_earned_income(request, is_married):
            if num_qualifying_children > 0:
                if cls._eligible_with_qualifying_children(
                    request, is_married, num_qualifying_children
                ):
                    return True
            elif cls._eligible_without_qualifying_children(
                request, head, spouse, is_married
            ):
                return True

        return cls._eligible_other_household_member(request, persons)

    @classmethod
    def _head_or_spouse_has_earned_income(cls, request, is_married: bool) -> bool:
        if is_married:
            return request.income_head_and_spouse_earned_yearly > 0
        return request.income_head_earned_yearly > 0

    @classmethod
    def _eligible_with_qualifying_children(
        cls, request, is_married: bool, num_qualifying_children: int
    ) -> bool:
        if is_married:
            return cls._married_with_children_meets_income_limits(
                request, num_qualifying_children
            )
        return cls._unmarried_with_children_meets_income_limits(
            request, num_qualifying_children
        )

    @classmethod
    def _married_with_children_meets_income_limits(
        cls, request, num_qualifying_children: int
    ) -> bool:
        investment_limit = scalar_limit("S2R006", "investment_limit")
        if investment_limit is None or cls._head_and_spouse_investment(request) > investment_limit:
            return False

        earned_threshold = cls._with_children_earned_threshold(
            "married_with_children", num_qualifying_children
        )
        if earned_threshold is None:
            return False

        earned_income = request.income_head_and_spouse_earned_yearly
        return 0 < earned_income <= earned_threshold

    @classmethod
    def _unmarried_with_children_meets_income_limits(
        cls, request, num_qualifying_children: int
    ) -> bool:
        investment_limit = scalar_limit("S2R006", "investment_limit")
        if investment_limit is None or cls._head_investment(request) > investment_limit:
            return False

        earned_threshold = cls._with_children_earned_threshold(
            "single_with_children", num_qualifying_children
        )
        if earned_threshold is None:
            return False

        earned_income = request.income_head_earned_yearly
        return 0 < earned_income <= earned_threshold

    @classmethod
    def _eligible_without_qualifying_children(
        cls, request, head, spouse, is_married: bool
    ) -> bool:
        if is_married:
            return cls._married_without_children_meets_requirements(request, head, spouse)
        return cls._unmarried_without_children_meets_requirements(request, head)

    @classmethod
    def _married_without_children_meets_requirements(cls, request, head, spouse) -> bool:
        if not (
            (head and 25 <= head.age < 65) or (spouse and 25 <= spouse.age < 65)
        ):
            return False

        investment_limit = scalar_limit("S2R006", "investment_limit")
        earned_threshold = scalar_limit("S2R006", "married_no_children")
        if investment_limit is None or earned_threshold is None:
            return False
        if cls._head_and_spouse_investment(request) > investment_limit:
            return False

        earned_income = request.income_head_and_spouse_earned_yearly
        return 0 < earned_income <= earned_threshold

    @classmethod
    def _unmarried_without_children_meets_requirements(cls, request, head) -> bool:
        if not head or not (25 <= head.age < 65):
            return False

        investment_limit = scalar_limit("S2R006", "investment_limit")
        earned_threshold = scalar_limit("S2R006", "single_no_children")
        if investment_limit is None or earned_threshold is None:
            return False
        if cls._head_investment(request) > investment_limit:
            return False

        earned_income = request.income_head_earned_yearly
        return 0 < earned_income <= earned_threshold

    @classmethod
    def _eligible_other_household_member(cls, request, persons) -> bool:
        investment_limit = scalar_limit("S2R006", "investment_limit")
        earned_threshold = scalar_limit("S2R006", "other_member")
        if investment_limit is None or earned_threshold is None:
            return False

        for index, person in enumerate(persons):
            if person.household_member_type in (
                HouseholdMemberType.HEAD_OF_HOUSEHOLD,
                HouseholdMemberType.SPOUSE,
            ):
                continue

            if not (25 <= person.age < 65):
                continue

            if request.income_person_investment_yearly.get(index, 0.0) > investment_limit:
                continue

            earned_income = request.income_person_earned_yearly.get(index, 0.0)
            if 0 < earned_income <= earned_threshold:
                return True

        return False

    @classmethod
    def _get_head_of_household(cls, persons):
        return next(
            (
                person
                for person in persons
                if person.household_member_type == HouseholdMemberType.HEAD_OF_HOUSEHOLD
            ),
            None,
        )

    @classmethod
    def _get_spouse(cls, persons):
        return next(
            (
                person
                for person in persons
                if person.household_member_type == HouseholdMemberType.SPOUSE
            ),
            None,
        )

    @classmethod
    def _with_children_earned_threshold(
        cls, pathway: str, num_children: int
    ) -> float | None:
        children_count = min(num_children, 3)
        return pathway_limit("S2R006", pathway, children_count)

    @classmethod
    def _head_investment(cls, request) -> float:
        for index, person in enumerate(request.person):
            if person.household_member_type == HouseholdMemberType.HEAD_OF_HOUSEHOLD:
                return request.income_person_investment_yearly.get(index, 0.0)
        return 0.0

    @classmethod
    def _head_and_spouse_investment(cls, request) -> float:
        total = 0.0
        for index, person in enumerate(request.person):
            if person.household_member_type in (
                HouseholdMemberType.HEAD_OF_HOUSEHOLD,
                HouseholdMemberType.SPOUSE,
            ):
                total += request.income_person_investment_yearly.get(index, 0.0)
        return total
