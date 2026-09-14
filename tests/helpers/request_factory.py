from __future__ import annotations

from src.models.enums import HouseholdMemberType
from src.models.schemas import AggregateEligibilityRequest, EligibilityRequest, Household, Person


def _default_household(**overrides) -> Household:
    defaults = {
        "living_renting": False,
        "living_rental_type": None,
    }
    defaults.update(overrides)
    return Household(**defaults)


def _default_person(**overrides) -> Person:
    defaults = {
        "age": 30,
        "household_member_type": HouseholdMemberType.HEAD_OF_HOUSEHOLD,
    }
    defaults.update(overrides)
    return Person(**defaults)


def make_eligibility_request(
    *,
    persons: list[Person] | None = None,
    household: Household | None = None,
) -> EligibilityRequest:
    if persons is None:
        persons = [_default_person()]

    if household is None:
        household = _default_household()

    return EligibilityRequest(household=[household], person=persons)


def make_computed_aggregate_request(
    *,
    persons: list[Person] | None = None,
    household: Household | None = None,
) -> AggregateEligibilityRequest:
    """Build an AggregateEligibilityRequest with aggregates computed from persons."""
    return AggregateEligibilityRequest.from_eligibility_request(
        make_eligibility_request(persons=persons, household=household)
    )


def make_aggregate_request(
    *,
    persons: list[Person] | None = None,
    household: Household | None = None,
    income_household_total_yearly: float = 0.0,
    income_household_total_monthly: float = 0.0,
    income_household_has_benefit: bool = False,
    income_household_has_cash_assistance: bool = False,
    income_household_has_ssi: bool = False,
    income_household_wage_self_employment_monthly: float = 0.0,
    expense_household_child_support_monthly: float = 0.0,
    **aggregate_overrides,
) -> AggregateEligibilityRequest:
    """Build a minimal AggregateEligibilityRequest for unit tests."""
    if persons is None:
        persons = [_default_person()]

    if household is None:
        household = _default_household()

    return AggregateEligibilityRequest(
        household=[household],
        person=persons,
        income_household_total_yearly=income_household_total_yearly,
        income_household_total_monthly=income_household_total_monthly,
        income_household_has_benefit=income_household_has_benefit,
        income_household_has_cash_assistance=income_household_has_cash_assistance,
        income_household_has_ssi=income_household_has_ssi,
        income_household_wage_self_employment_monthly=income_household_wage_self_employment_monthly,
        expense_household_child_support_monthly=expense_household_child_support_monthly,
        **aggregate_overrides,
    )
