"""
Unit tests for per-program rule logic.
Threshold comparison tests are covered by test_thresholds.py.

Run maintained rule logic tests:
    uv run pytest tests/unit/rules/program_rule_test.py

Run a single program:
    uv run pytest tests/unit/rules/program_rule_test.py -k S2R034
"""

from __future__ import annotations

import pytest

from src.models.enums import ExpenseType, Frequency, HouseholdMemberType, IncomeType, LivingRentalType
from src.models.schemas import Income
from src.rules.registry import get_rules
from src.rules.thresholds import limits_for, pathway_limit, scalar_limit
from tests.helpers.request_factory import _default_household, _default_person, make_aggregate_request, make_computed_aggregate_request

RULES = {rule_cls.program: rule_cls for rule_cls in get_rules()}


def get_threshold_limit(program: str, household_size: int = 1) -> float:
    limit = limits_for(program).get(household_size)
    return limit


def get_hoh_with_income(income_type: IncomeType, amount: float = 100.0) -> list:
    return [
        _default_person(
            incomes=[
                Income(amount=amount, type=income_type, frequency=Frequency.MONTHLY)
            ]
        )
    ]


class TestS2R001:
    ADULT = _default_person(age=30)
    CHILD = _default_person(age=10, household_member_type=HouseholdMemberType.CHILD)
    DISABLED = _default_person(
        age=20,
        disabled=True,
        household_member_type=HouseholdMemberType.SPOUSE,
    )
    BLIND = _default_person(
        age=20,
        blind=True,
        household_member_type=HouseholdMemberType.SPOUSE,
    )

    @pytest.mark.parametrize(
        "persons, has_care_expense, expected",
        [
            pytest.param([ADULT, CHILD], True, True, id="eligible_with_child_under_13"),
            pytest.param([ADULT, DISABLED], True, True, id="eligible_with_disabled_dependent"),
            pytest.param([ADULT, BLIND], True, True, id="eligible_with_blind_dependent"),
            pytest.param([ADULT], True, False, id="ineligible_without_eligible_dependent"),
            pytest.param([ADULT, CHILD], False, False, id="ineligible_without_care_expense"),
        ],
    )
    def test_eligibility(self, persons, has_care_expense, expected):
        request = make_aggregate_request(
            persons=persons,
            expense_household_has_child_or_dependent_care=has_care_expense,
            income_hoh_and_spouse_earned_yearly=5000.0,
        )

        assert RULES["S2R001"].evaluate(request) is expected


class TestS2R003:
    def test_eligible_with_young_child_and_income_within_limit(self):
        request = make_aggregate_request(
            persons=[
                _default_person(age=30),
                _default_person(age=4, household_member_type=HouseholdMemberType.CHILD),
            ],
            income_adults_children_total_monthly=get_threshold_limit("S2R003", 2),
        )

        assert RULES["S2R003"].evaluate(request) is True

    def test_ineligible_without_child_age_five_or_younger(self):
        request = make_aggregate_request(
            persons=[_default_person(age=30)],
            income_adults_children_total_monthly=0.0,
        )

        assert RULES["S2R003"].evaluate(request) is False


class TestS2R004:
    ADULT = _default_person(age=30)
    CHILD = _default_person(age=10, household_member_type=HouseholdMemberType.CHILD)
    MINIMUM = float(scalar_limit("S2R004", "minimum"))
    SINGLE_CAP = float(scalar_limit("S2R004", "single"))
    MARRIED_CAP = float(scalar_limit("S2R004", "married"))

    @pytest.mark.parametrize(
        "persons, married, income, expected",
        [
            pytest.param([ADULT, CHILD], False, MINIMUM, True, id="single_eligible_at_minimum_income"),
            pytest.param([ADULT, CHILD], False, SINGLE_CAP, True, id="single_eligible_at_income_cap"),
            pytest.param([ADULT, CHILD], False, SINGLE_CAP + 1, False, id="single_ineligible_over_income_cap"),
            pytest.param([ADULT, CHILD], True, MARRIED_CAP, True, id="married_eligible_at_income_cap"),
            pytest.param(
                [ADULT, CHILD],
                True,
                SINGLE_CAP + 1,
                True,
                id="married_eligible_above_single_income_cap",
            ),
            pytest.param([ADULT, CHILD], True, MARRIED_CAP + 1, False, id="married_ineligible_over_income_cap"),
            pytest.param([ADULT], False, MINIMUM, False, id="ineligible_without_child_under_17"),
            pytest.param([ADULT, CHILD], False, MINIMUM - 1, False, id="ineligible_below_minimum_income"),
        ],
    )
    def test_eligibility(self, persons, married, income, expected):
        request = make_aggregate_request(
            persons=persons,
            income_household_total_yearly=income,
            head_of_household_married=married,
        )

        assert RULES["S2R004"].evaluate(request) is expected


class TestS2R005:
    def test_eligible_with_qualifying_rental_and_disability_income(self):
        maximum = scalar_limit("S2R005", "maximum")
        request = make_computed_aggregate_request(
            household=_default_household(
                living_renting=True,
                living_rental_type=LivingRentalType.RENT_CONTROLLED,
            ),
            persons=[
                _default_person(
                    age=30,
                    living_rental_on_lease=True,
                    incomes=[
                        Income(
                            amount=100.0,
                            type=IncomeType.SSI,
                            frequency=Frequency.MONTHLY,
                        )
                    ],
                )
            ],
        )
        request.income_household_total_yearly = float(maximum)

        assert RULES["S2R005"].evaluate(request) is True

    def test_ineligible_non_qualifying_rental_type(self):
        request = make_computed_aggregate_request(
            household=_default_household(
                living_renting=True,
                living_rental_type=LivingRentalType.MARKET_RATE,
            ),
            persons=get_hoh_with_income(IncomeType.SSI),
        )

        assert RULES["S2R005"].evaluate(request) is False

    def test_ineligible_non_qualifying_income_type(self):
        maximum = scalar_limit("S2R005", "maximum")
        request = make_computed_aggregate_request(
            household=_default_household(
                living_renting=True,
                living_rental_type=LivingRentalType.RENT_CONTROLLED,
            ),
            persons=[
                _default_person(
                    age=30,
                    living_rental_on_lease=True,
                    incomes=[
                        Income(
                            amount=100.0,
                            type=IncomeType.WAGES,
                            frequency=Frequency.MONTHLY,
                        )
                    ],
                )
            ],
        )
        request.income_household_total_yearly = float(maximum)

        assert RULES["S2R005"].evaluate(request) is False


class TestS2R006:
    HOH = _default_person(age=30)
    YOUNG_HOH = _default_person(age=24)
    SPOUSE = _default_person(age=28, household_member_type=HouseholdMemberType.SPOUSE)
    QUALIFYING_CHILD = _default_person(age=8, household_member_type=HouseholdMemberType.CHILD)
    NON_QUALIFYING_CHILD = _default_person(age=20, household_member_type=HouseholdMemberType.CHILD)
    OTHER_MEMBER = _default_person(age=30, household_member_type=HouseholdMemberType.UNRELATED)

    INVESTMENT_LIMIT = float(scalar_limit("S2R006", "investment_limit"))
    SINGLE_NO_CHILDREN = float(scalar_limit("S2R006", "single_no_children"))
    MARRIED_NO_CHILDREN = float(scalar_limit("S2R006", "married_no_children"))
    SINGLE_WITH_CHILDREN = float(pathway_limit("S2R006", "single_with_children", 1))
    MARRIED_WITH_CHILDREN = float(pathway_limit("S2R006", "married_with_children", 1))
    OTHER_MEMBER_LIMIT = float(scalar_limit("S2R006", "other_member"))

    def _request(self, persons, **fields):
        request = make_computed_aggregate_request(persons=persons)
        for key, value in fields.items():
            setattr(request, key, value)
        return request

    def test_eligible_unmarried_with_qualifying_child(self):
        request = self._request(
            [self.HOH, self.QUALIFYING_CHILD],
            income_hoh_earned_yearly=self.SINGLE_WITH_CHILDREN,
        )

        assert RULES["S2R006"].evaluate(request) is True

    def test_eligible_unmarried_without_qualifying_children(self):
        request = self._request(
            [self.HOH],
            income_hoh_earned_yearly=self.SINGLE_NO_CHILDREN,
        )

        assert RULES["S2R006"].evaluate(request) is True

    def test_eligible_unmarried_with_non_qualifying_child(self):
        request = self._request(
            [self.HOH, self.NON_QUALIFYING_CHILD],
            income_hoh_earned_yearly=self.SINGLE_NO_CHILDREN,
        )

        assert RULES["S2R006"].evaluate(request) is True

    def test_eligible_married_with_qualifying_child(self):
        request = self._request(
            [self.HOH, self.SPOUSE, self.QUALIFYING_CHILD],
            head_of_household_married=True,
            income_hoh_and_spouse_earned_yearly=self.MARRIED_WITH_CHILDREN,
        )

        assert RULES["S2R006"].evaluate(request) is True

    def test_eligible_married_without_qualifying_children(self):
        request = self._request(
            [self.HOH, self.SPOUSE],
            head_of_household_married=True,
            income_hoh_and_spouse_earned_yearly=self.MARRIED_NO_CHILDREN,
        )

        assert RULES["S2R006"].evaluate(request) is True

    def test_eligible_other_household_member(self):
        request = self._request(
            [self.HOH, self.OTHER_MEMBER],
            income_person_earned_yearly={1: self.OTHER_MEMBER_LIMIT},
        )

        assert RULES["S2R006"].evaluate(request) is True

    def test_ineligible_without_earned_income(self):
        request = self._request(
            [self.HOH, self.QUALIFYING_CHILD],
            income_hoh_earned_yearly=0.0,
        )

        assert RULES["S2R006"].evaluate(request) is False

    def test_ineligible_over_earned_limit_with_qualifying_child(self):
        request = self._request(
            [self.HOH, self.QUALIFYING_CHILD],
            income_hoh_earned_yearly=self.SINGLE_WITH_CHILDREN + 1,
        )

        assert RULES["S2R006"].evaluate(request) is False

    def test_ineligible_over_investment_limit_with_qualifying_child(self):
        request = self._request(
            [self.HOH, self.QUALIFYING_CHILD],
            income_hoh_earned_yearly=self.SINGLE_WITH_CHILDREN,
            income_person_investment_yearly={0: self.INVESTMENT_LIMIT + 1},
        )

        assert RULES["S2R006"].evaluate(request) is False

    def test_ineligible_hoh_too_young_without_qualifying_children(self):
        request = self._request(
            [self.YOUNG_HOH],
            income_hoh_earned_yearly=self.SINGLE_NO_CHILDREN,
        )

        assert RULES["S2R006"].evaluate(request) is False


class TestS2R007:
    def test_eligible_categorical_eligibility(self):
        request = make_computed_aggregate_request(
            persons=[
                _default_person(
                    age=30,
                    incomes=[
                        Income(
                            amount=1,
                            type=IncomeType.SSI,
                            frequency=Frequency.MONTHLY,
                        )
                    ],
                )
            ],
        )

        assert RULES["S2R007"].evaluate(request) is True

    def test_ineligible_categorical_eligibility(self):
        request = make_computed_aggregate_request(
            persons=[
                _default_person(
                    incomes=[
                        Income(
                            amount=100.0,
                            type=IncomeType.SSI,
                            frequency=Frequency.MONTHLY,
                        )
                    ],
                ),
                _default_person(
                    household_member_type=HouseholdMemberType.SPOUSE,
                    incomes=[
                        Income(
                            amount=9999.0,
                            type=IncomeType.WAGES,
                            frequency=Frequency.MONTHLY,
                        )
                    ],
                ),
            ],
        )

        assert RULES["S2R007"].evaluate(request) is False

    def test_eligible_under_130_fpl_pathway_by_default(self):
        limit = pathway_limit("S2R007", "fpl_130", 1)
        request = make_aggregate_request(income_household_total_monthly=float(limit))

        assert RULES["S2R007"].evaluate(request) is True

    def test_eligible_under_200_fpl_pathway_for_elderly_household(self):
        limit = pathway_limit("S2R007", "fpl_200", 1)
        request = make_aggregate_request(
            persons=[_default_person(age=65)],
            income_household_total_monthly=float(limit),
        )

        assert RULES["S2R007"].evaluate(request) is True

    def test_eligible_under_150_fpl_pathway_with_earned_income(self):
        limit = pathway_limit("S2R007", "fpl_150", 1)
        request = make_computed_aggregate_request(
            persons=[
                _default_person(
                    incomes=[
                        Income(
                            amount=1,
                            type=IncomeType.WAGES,
                            frequency=Frequency.MONTHLY,
                        )
                    ],
                )
            ],
        )
        request.income_household_total_monthly = float(limit)

        assert RULES["S2R007"].evaluate(request) is True

    def test_eligible_withchild_support_deduction(self):
        limit = pathway_limit("S2R007", "fpl_130", 1)
        child_support = 100.0
        request = make_computed_aggregate_request(
            persons=[
                _default_person(
                    incomes=[
                        Income(
                            amount=float(limit) + child_support,
                            type=IncomeType.WAGES,
                            frequency=Frequency.MONTHLY,
                        )
                    ],
                    expenses=[
                        {
                            "amount": child_support,
                            "type": ExpenseType.CHILD_SUPPORT,
                            "frequency": Frequency.MONTHLY,
                        }
                    ],
                )
            ],
        )

        assert RULES["S2R007"].evaluate(request) is True


class TestS2R008:
    YOUNG_CHILD = _default_person(age=4)
    INCOME_LIMIT_FOR_HOUSEHOLD_SIZE_1 = float(get_threshold_limit("S2R008", 1))
    OVER_LIMIT_INCOME = INCOME_LIMIT_FOR_HOUSEHOLD_SIZE_1 + 1

    def test_eligible_with_young_child_and_income_within_limit(self):
        request = make_aggregate_request(
            persons=[self.YOUNG_CHILD],
            income_household_total_yearly=self.INCOME_LIMIT_FOR_HOUSEHOLD_SIZE_1,
        )

        assert RULES["S2R008"].evaluate(request) is True

    def test_eligible_with_young_child_and_cash_assistance(self):
        request = make_aggregate_request(
            persons=[self.YOUNG_CHILD],
            income_household_has_cash_assistance=True,
            income_household_total_yearly=self.OVER_LIMIT_INCOME,
        )

        assert RULES["S2R008"].evaluate(request) is True

    def test_eligible_with_young_child_and_foster_child(self):
        request = make_computed_aggregate_request(
            persons=[
                _default_person(age=30),
                _default_person(
                    age=4,
                    household_member_type=HouseholdMemberType.FOSTER_CHILD,
                ),
            ],
        )
        request.income_household_total_yearly = self.OVER_LIMIT_INCOME

        assert RULES["S2R008"].evaluate(request) is True

    def test_ineligible_without_child_age_five_or_younger(self):
        request = make_aggregate_request(
            persons=[_default_person(age=30)],
            income_household_total_yearly=0.0,
        )

        assert RULES["S2R008"].evaluate(request) is False

    def test_ineligible_young_child_over_income_without_cash_assistance_or_foster(self):
        request = make_aggregate_request(
            persons=[self.YOUNG_CHILD],
            income_household_total_yearly=self.OVER_LIMIT_INCOME,
            income_household_has_cash_assistance=False,
            income_household_has_ssi=False,
        )

        assert RULES["S2R008"].evaluate(request) is False

    def test_ineligible_young_child_over_income_without_foster_child(self):
        household_size = 2
        over_limit = float(get_threshold_limit("S2R008", household_size)) + 1
        request = make_computed_aggregate_request(
            persons=[
                _default_person(age=30),
                _default_person(
                    age=4,
                    household_member_type=HouseholdMemberType.CHILD,
                ),
            ],
        )
        request.income_household_total_yearly = over_limit

        assert request.foster_children == 0
        assert RULES["S2R008"].evaluate(request) is False


class TestS2R009:
    @pytest.mark.parametrize(
        "age, expected",
        [
            pytest.param(10, True, id="eligible_student_age_10"),
            pytest.param(4, False, id="ineligible_student_under_5"),
            pytest.param(22, False, id="ineligible_student_over_21"),
        ],
    )
    def test_student_age_eligibility(self, age, expected):
        request = make_aggregate_request(persons=[_default_person(age=age, student=True)])

        assert RULES["S2R009"].evaluate(request) is expected


class TestS2R010:
    ADULT = _default_person(age=30)
    CHILD = _default_person(age=10, household_member_type=HouseholdMemberType.CHILD)
    PERSON_AGE_18 = _default_person(age=18)
    PERSON_AGE_19 = _default_person(age=19)
    PREGNANT_ADULT = _default_person(age=30, pregnant=True)

    def test_uses_higher_with_child_threshold_when_child_in_household(self):
        net_income = float(pathway_limit("S2R010", "general", 1)) + 1
        adult_only = make_aggregate_request(
            persons=[self.ADULT],
            income_household_monthly_ca_minus_work_expense=net_income,
        )
        with_child = make_aggregate_request(
            persons=[self.ADULT, self.CHILD],
            income_household_monthly_ca_minus_work_expense=net_income,
        )

        assert RULES["S2R010"].evaluate(adult_only) is False
        assert RULES["S2R010"].evaluate(with_child) is True

    def test_uses_higher_with_child_threshold_when_person_is_age_18(self):
        net_income = float(pathway_limit("S2R010", "general", 1)) + 1
        age_18 = make_aggregate_request(
            persons=[self.PERSON_AGE_18],
            income_household_monthly_ca_minus_work_expense=net_income,
        )
        age_19 = make_aggregate_request(
            persons=[self.PERSON_AGE_19],
            income_household_monthly_ca_minus_work_expense=net_income,
        )

        assert RULES["S2R010"].evaluate(age_18) is True
        assert RULES["S2R010"].evaluate(age_19) is False

    def test_uses_higher_with_pregnant_member_threshold_when_pregnant(self):
        net_income = float(pathway_limit("S2R010", "general", 1)) + 1
        pregnant = make_aggregate_request(
            persons=[self.PREGNANT_ADULT],
            income_household_monthly_ca_minus_work_expense=net_income,
        )
        not_pregnant = make_aggregate_request(
            persons=[self.ADULT],
            income_household_monthly_ca_minus_work_expense=net_income,
        )

        assert RULES["S2R010"].evaluate(pregnant) is True
        assert RULES["S2R010"].evaluate(not_pregnant) is False

    @pytest.mark.parametrize("household_size", [1, 2, 3, 4, 5, 6, 7, 8])
    def test_eligible_under_general_threshold_by_household_size(self, household_size):
        limit = float(pathway_limit("S2R010", "general", household_size))
        persons = [_default_person() for _ in range(household_size)]
        request = make_aggregate_request(
            persons=persons,
            income_household_monthly_ca_minus_work_expense=limit - 1,
        )

        assert RULES["S2R010"].evaluate(request) is True

    @pytest.mark.parametrize("household_size", [1, 2, 3, 4, 5, 6, 7, 8])
    def test_ineligible_over_general_threshold_by_household_size(self, household_size):
        limit = float(pathway_limit("S2R010", "general", household_size))
        persons = [_default_person() for _ in range(household_size)]
        request = make_aggregate_request(
            persons=persons,
            income_household_monthly_ca_minus_work_expense=limit + 1,
        )

        assert RULES["S2R010"].evaluate(request) is False

    @pytest.mark.parametrize("household_size", [1, 2, 3, 4, 5, 6, 7, 8])
    def test_eligible_under_with_child_or_pregnant_threshold_by_household_size(
        self, household_size
    ):
        limit = float(pathway_limit("S2R010", "with_child_or_pregnant", household_size))
        persons = [
            self.CHILD,
            *[_default_person() for _ in range(household_size - 1)],
        ]
        request = make_aggregate_request(
            persons=persons,
            income_household_monthly_ca_minus_work_expense=limit - 1,
        )

        assert RULES["S2R010"].evaluate(request) is True

    @pytest.mark.parametrize("household_size", [1, 2, 3, 4, 5, 6, 7, 8])
    def test_ineligible_above_with_child_or_pregnant_threshold_by_household_size(
        self, household_size
    ):
        limit = float(pathway_limit("S2R010", "with_child_or_pregnant", household_size))
        persons = [
            self.CHILD,
            *[_default_person() for _ in range(household_size - 1)],
        ]
        request = make_aggregate_request(
            persons=persons,
            income_household_monthly_ca_minus_work_expense=limit + 1,
        )

        assert RULES["S2R010"].evaluate(request) is False


class TestS2R011:
    def test_always_eligible(self):
        assert RULES["S2R011"].evaluate(make_aggregate_request()) is True


class TestS2R012:
    def test_eligible_homeowner_within_income_limit(self):
        maximum = scalar_limit("S2R012", "maximum")
        request = make_aggregate_request(
            household=_default_household(living_owner=True),
            income_owners_total_yearly=float(maximum),
        )

        assert RULES["S2R012"].evaluate(request) is True

    def test_ineligible_non_owner(self):
        request = make_aggregate_request(income_owners_total_yearly=0.0)

        assert RULES["S2R012"].evaluate(request) is False


class TestS2R013:
    ADULT_HOH = _default_person(
        age=30,
        household_member_type=HouseholdMemberType.HEAD_OF_HOUSEHOLD,
    )
    MINOR_HOH = _default_person(
        age=17,
        household_member_type=HouseholdMemberType.HEAD_OF_HOUSEHOLD,
    )

    @pytest.mark.parametrize(
        "persons, income_key, expected",
        [
            pytest.param([MINOR_HOH], "any", False, id="ineligible_hoh_under_18"),
            pytest.param([ADULT_HOH], "at_limit", True, id="eligible_at_income_limit"),
            pytest.param([ADULT_HOH], "over_limit", False, id="ineligible_over_income_limit"),
        ],
    )
    def test_eligibility(self, persons, income_key, expected):
        limit = get_threshold_limit("S2R013")
        if income_key == "at_limit":
            income = float(limit)
        elif income_key == "over_limit":
            income = float(limit) + 1
        else:
            income = 0.0

        request = make_aggregate_request(
            persons=persons,
            income_household_total_yearly=income,
        )

        assert RULES["S2R013"].evaluate(request) is expected


class TestS2R014:
    def test_eligible_senior_owner_within_income_limit(self):
        maximum = scalar_limit("S2R014", "maximum")
        request = make_aggregate_request(
            household=_default_household(living_owner=True),
            persons=[_default_person(age=67, living_owner_on_deed=True)],
            income_owners_total_yearly=float(maximum),
        )

        assert RULES["S2R014"].evaluate(request) is True

    def test_ineligible_without_senior_owner_on_deed(self):
        request = make_aggregate_request(
            household=_default_household(living_owner=True),
            persons=[_default_person(age=50, living_owner_on_deed=True)],
            income_owners_total_yearly=0.0,
        )

        assert RULES["S2R014"].evaluate(request) is False


class TestS2R015:
    SENIOR_ON_LEASE = _default_person(age=65, living_rental_on_lease=True)
    MAXIMUM = float(scalar_limit("S2R015", "maximum"))
    INCOME_AT_MAXIMUM_MONTHLY = MAXIMUM / 12

    def test_eligible_senior_renter_within_income_limit(self):
        request = make_aggregate_request(
            household=_default_household(
                living_renting=True,
                living_rental_type=LivingRentalType.RENT_CONTROLLED,
            ),
            persons=[self.SENIOR_ON_LEASE],
            income_household_total_monthly_less_gifts=self.INCOME_AT_MAXIMUM_MONTHLY,
        )

        assert RULES["S2R015"].evaluate(request) is True

    def test_ineligible_non_qualifying_rental_type(self):
        request = make_aggregate_request(
            household=_default_household(
                living_renting=True,
                living_rental_type=LivingRentalType.MARKET_RATE,
            ),
            persons=[self.SENIOR_ON_LEASE],
            income_household_total_monthly_less_gifts=0.0,
        )

        assert RULES["S2R015"].evaluate(request) is False

    def test_ineligible_when_not_renting(self):
        request = make_aggregate_request(
            household=_default_household(living_renting=False),
            persons=[self.SENIOR_ON_LEASE],
            income_household_total_monthly_less_gifts=0.0,
        )

        assert RULES["S2R015"].evaluate(request) is False

    def test_ineligible_when_hoh_not_on_lease(self):
        request = make_aggregate_request(
            household=_default_household(
                living_renting=True,
                living_rental_type=LivingRentalType.RENT_CONTROLLED,
            ),
            persons=[_default_person(age=65, living_rental_on_lease=False)],
            income_household_total_monthly_less_gifts=0.0,
        )

        assert RULES["S2R015"].evaluate(request) is False

    def test_eligible_when_hoh_is_age_62(self):
        request = make_aggregate_request(
            household=_default_household(
                living_renting=True,
                living_rental_type=LivingRentalType.RENT_CONTROLLED,
            ),
            persons=[_default_person(age=62, living_rental_on_lease=True)],
            income_household_total_monthly_less_gifts=self.INCOME_AT_MAXIMUM_MONTHLY,
        )

        assert RULES["S2R015"].evaluate(request) is True

    def test_ineligible_hoh_under_age_62(self):
        request = make_aggregate_request(
            household=_default_household(
                living_renting=True,
                living_rental_type=LivingRentalType.RENT_CONTROLLED,
            ),
            persons=[_default_person(age=61, living_rental_on_lease=True)],
            income_household_total_monthly_less_gifts=0.0,
        )

        assert RULES["S2R015"].evaluate(request) is False

    def test_ineligible_over_income_limit(self):
        request = make_aggregate_request(
            household=_default_household(
                living_renting=True,
                living_rental_type=LivingRentalType.RENT_CONTROLLED,
            ),
            persons=[self.SENIOR_ON_LEASE],
            income_household_total_monthly_less_gifts=(self.MAXIMUM + 100) / 12,
        )

        assert RULES["S2R015"].evaluate(request) is False


class TestS2R016:
    @pytest.mark.parametrize(
        "age, expected",
        [
            pytest.param(3, True, id="eligible_age_3"),
            pytest.param(4, True, id="eligible_age_4"),
            pytest.param(5, False, id="ineligible_age_5"),
            pytest.param(2, False, id="ineligible_age_2"),
        ],
    )
    def test_pre_k_age_eligibility(self, age, expected):
        request = make_aggregate_request(persons=[_default_person(age=age)])

        assert RULES["S2R016"].evaluate(request) is expected


class TestS2R017:
    def test_eligible_disabled_owner_within_income_limit(self):
        maximum = scalar_limit("S2R017", "maximum")
        request = make_aggregate_request(
            household=_default_household(living_owner=True),
            persons=[_default_person(age=40, disabled=True, living_owner_on_deed=True)],
            income_owners_total_yearly=float(maximum),
        )

        assert RULES["S2R017"].evaluate(request) is True

    def test_eligible_owner_with_ssi_income(self):
        maximum = scalar_limit("S2R017", "maximum")
        request = make_computed_aggregate_request(
            household=_default_household(living_owner=True),
            persons=[
                _default_person(
                    age=40,
                    living_owner_on_deed=True,
                    incomes=[
                        Income(
                            amount=100.0,
                            type=IncomeType.SSI,
                            frequency=Frequency.MONTHLY,
                        )
                    ],
                )
            ],
        )
        request.income_owners_total_yearly = float(maximum)

        assert RULES["S2R017"].evaluate(request) is True

    def test_ineligible_non_owner(self):
        request = make_aggregate_request(
            persons=[_default_person(age=40, disabled=True)],
        )

        assert RULES["S2R017"].evaluate(request) is False


class TestS2R018:
    def test_eligible_veteran_owner(self):
        request = make_aggregate_request(
            household=_default_household(living_owner=True),
            persons=[_default_person(age=40, veteran=True, living_owner_on_deed=True)],
        )

        assert RULES["S2R018"].evaluate(request) is True

    def test_ineligible_veteran_not_on_deed(self):
        request = make_aggregate_request(
            household=_default_household(living_owner=True),
            persons=[_default_person(age=40, veteran=True)],
        )

        assert RULES["S2R018"].evaluate(request) is False


class TestS2R019:
    ADULT = _default_person(age=30)
    CHILD = _default_person(age=10, household_member_type=HouseholdMemberType.CHILD)
    HIGH_INCOME = 999999.0

    @pytest.mark.parametrize(
        "persons, cash_assistance, has_ssi, income_key, expected",
        [
            pytest.param(None, True, False, "high", True, id="household_eligible_with_cash_assistance"),
            pytest.param([ADULT], False, True, "high", True, id="single_member_household_eligible_with_ssi"),
            pytest.param([ADULT, CHILD], False, True, "high", False, id="bigger_household_with_ssi_and_no_ca_ineligible"),
            pytest.param(None, False, False, "at_limit", True, id="eligible_by_income"),
        ],
    )
    def test_eligibility(
        self,
        persons,
        cash_assistance,
        has_ssi,
        income_key,
        expected,
    ):
        if income_key == "high":
            income = self.HIGH_INCOME
        else:
            income = float(get_threshold_limit("S2R019"))

        request = make_aggregate_request(
            persons=persons,
            income_household_has_cash_assistance=cash_assistance,
            income_household_has_ssi=has_ssi,
            income_household_total_monthly=income,
        )

        assert RULES["S2R019"].evaluate(request) is expected


class TestS2R021:
    def test_eligible_unemployed_with_recent_work_history(self):
        request = make_aggregate_request(
            persons=[_default_person(age=30, unemployed=True, unemployed_worked_last_18_months=True)],
        )

        assert RULES["S2R021"].evaluate(request) is True

    def test_ineligible_unemployed_without_recent_work_history(self):
        request = make_aggregate_request(
            persons=[_default_person(age=30, unemployed=True, unemployed_worked_last_18_months=False)],
        )

        assert RULES["S2R021"].evaluate(request) is False


class TestS2R022:
    CHILD_UNDER_FIVE = _default_person(
        age=4,
        household_member_type=HouseholdMemberType.CHILD,
    )
    HIGH_INCOME = 999999.0

    def test_eligible_with_pregnant_member_and_medicaid_(self):
        request = make_aggregate_request(
            persons=[_default_person(age=30, pregnant=True, benefits_medicaid=True)],
            income_household_total_yearly=self.HIGH_INCOME,
        )

        assert RULES["S2R022"].evaluate(request) is True

    def test_eligible_with_child_under_5_and_medicaid_disability(self):
        request = make_aggregate_request(
            persons=[
                _default_person(
                    age=4,
                    household_member_type=HouseholdMemberType.CHILD,
                    benefits_medicaid_disability=True,
                )
            ],
            income_household_total_yearly=self.HIGH_INCOME,
        )

        assert RULES["S2R022"].evaluate(request) is True

    def test_eligible_with_child_under_5_and_cash_assistance(self):
        request = make_aggregate_request(
            persons=[
                _default_person(
                    age=4,
                    household_member_type=HouseholdMemberType.CHILD,
                    incomes=[
                        Income(
                            amount=100.0,
                            type=IncomeType.CASH_ASSISTANCE,
                            frequency=Frequency.MONTHLY,
                        )
                    ],
                )
            ],
            income_household_total_yearly=self.HIGH_INCOME,
        )

        assert RULES["S2R022"].evaluate(request) is True

    def test_eligible_by_income_for_pregnant_person(self):
        request = make_aggregate_request(
            persons=[_default_person(age=30, pregnant=True)],
            income_household_total_yearly=float(get_threshold_limit("S2R022", 1)),
        )

        assert RULES["S2R022"].evaluate(request) is True

    def test_eligible_by_income_for_child_under_five(self):
        request = make_aggregate_request(
            persons=[self.CHILD_UNDER_FIVE],
            income_household_total_yearly=float(get_threshold_limit("S2R022", 1)),
        )

        assert RULES["S2R022"].evaluate(request) is True

    def test_ineligible_over_income_without_categorical_eligibility(self):
        request = make_aggregate_request(
            persons=[_default_person(age=30, pregnant=True)],
            income_household_total_yearly=float(get_threshold_limit("S2R022", 1)) + 1,
        )

        assert RULES["S2R022"].evaluate(request) is False

    def test_ineligible_without_pregnant_person_or_young_child(self):
        request = make_aggregate_request(
            persons=[_default_person(age=30)],
            income_household_total_yearly=0.0,
        )

        assert RULES["S2R022"].evaluate(request) is False


class TestS2R023:
    def test_eligible_for_child_under_nineteen(self):
        request = make_aggregate_request(persons=[_default_person(age=10)])

        assert RULES["S2R023"].evaluate(request) is True

    def test_ineligible_without_child_under_nineteen(self):
        request = make_aggregate_request(persons=[_default_person(age=30)])

        assert RULES["S2R023"].evaluate(request) is False


class TestS2R024:
    NYCHA_HOUSEHOLD = _default_household(
        living_renting=True,
        living_rental_type=LivingRentalType.NYCHA,
    )
    NON_NYCHA_HOUSEHOLD = _default_household(living_renting=True)
    ADULT = [_default_person(age=30)]
    MINOR = [_default_person(age=17)]

    @pytest.mark.parametrize(
        "household, persons, expected",
        [
            pytest.param(NYCHA_HOUSEHOLD, ADULT, True, id="eligible_nycha_household_with_adult"),
            pytest.param(NYCHA_HOUSEHOLD, MINOR, False, id="ineligible_nycha_household_without_adult"),
            pytest.param(NON_NYCHA_HOUSEHOLD, ADULT, False, id="ineligible_non_nycha_household"),
        ],
    )
    def test_nycha_eligibility(self, household, persons, expected):
        request = make_aggregate_request(household=household, persons=persons)

        assert RULES["S2R024"].evaluate(request) is expected


class TestS2R025:
    def test_eligible_unemployed_senior_within_income_limit(self):
        request = make_aggregate_request(
            persons=[_default_person(age=60, unemployed=True)],
            income_household_total_yearly=get_threshold_limit("S2R025", 1),
        )

        assert RULES["S2R025"].evaluate(request) is True

    def test_ineligible_employed_senior(self):
        request = make_aggregate_request(
            persons=[_default_person(age=60, unemployed=False)],
            income_household_total_yearly=0.0,
        )

        assert RULES["S2R025"].evaluate(request) is False


class TestS2R026:
    @pytest.mark.parametrize(
        "age, expected",
        [
            pytest.param(30, True, id="eligible_with_adult"),
            pytest.param(17, False, id="ineligible_without_adult"),
        ],
    )
    def test_minimum_age_18(self, age, expected):
        request = make_aggregate_request(persons=[_default_person(age=age)])

        assert RULES["S2R026"].evaluate(request) is expected


class TestS2R027:
    def test_eligible_senior_within_income_limit(self):
        request = make_aggregate_request(
            persons=[_default_person(age=65)],
            income_household_total_yearly=get_threshold_limit("S2R027", 1),
        )

        assert RULES["S2R027"].evaluate(request) is True

    def test_ineligible_without_senior(self):
        request = make_aggregate_request(
            persons=[_default_person(age=30)],
            income_household_total_yearly=0.0,
        )

        assert RULES["S2R027"].evaluate(request) is False


class TestS2R028:
    YOUTH = _default_person(age=16)
    HIGH_INCOME = 999999.0

    def test_ineligible_household_without_youth_aged_14_to_21(self):
        request = make_aggregate_request(
            persons=[_default_person(age=30)],
            income_household_total_yearly=0.0,
        )

        assert RULES["S2R028"].evaluate(request) is False

    @pytest.mark.parametrize("age", [13, 22], ids=["ineligible_age_13", "ineligible_age_22"])
    def test_ineligible_youth_outside_age_range(self, age):
        request = make_aggregate_request(
            persons=[_default_person(age=age, disabled=True)],
            income_household_total_yearly=0.0,
        )

        assert RULES["S2R028"].evaluate(request) is False

    def test_eligible_with_youth_and_living_shelter(self):
        request = make_aggregate_request(
            persons=[self.YOUTH],
            household=_default_household(living_shelter=True),
            income_household_total_yearly=self.HIGH_INCOME,
        )

        assert RULES["S2R028"].evaluate(request) is True

    def test_eligible_foster_child_youth(self):
        request = make_aggregate_request(
            persons=[
                _default_person(age=16, household_member_type=HouseholdMemberType.FOSTER_CHILD),
            ],
            income_household_total_yearly=self.HIGH_INCOME,
        )

        assert RULES["S2R028"].evaluate(request) is True

    def test_eligible_youth_hoh_with_foster_parent(self):
        request = make_aggregate_request(
            persons=[
                _default_person(age=18, household_member_type=HouseholdMemberType.HEAD_OF_HOUSEHOLD),
                _default_person(age=45, household_member_type=HouseholdMemberType.FOSTER_PARENT),
            ],
            income_household_total_yearly=self.HIGH_INCOME,
        )

        assert RULES["S2R028"].evaluate(request) is True

    def test_eligible_disabled_youth(self):
        request = make_aggregate_request(
            persons=[_default_person(age=16, disabled=True)],
            income_household_total_yearly=self.HIGH_INCOME,
        )

        assert RULES["S2R028"].evaluate(request) is True

    def test_eligible_blind_youth(self):
        request = make_aggregate_request(
            persons=[_default_person(age=16, blind=True)],
            income_household_total_yearly=self.HIGH_INCOME,
        )

        assert RULES["S2R028"].evaluate(request) is True

    def test_eligible_pregnant_youth(self):
        request = make_aggregate_request(
            persons=[_default_person(age=18, pregnant=True)],
            income_household_total_yearly=self.HIGH_INCOME,
        )

        assert RULES["S2R028"].evaluate(request) is True

    def test_eligible_parent_youth(self):
        request = make_aggregate_request(
            persons=[_default_person(age=19, household_member_type=HouseholdMemberType.PARENT)],
            income_household_total_yearly=self.HIGH_INCOME,
        )

        assert RULES["S2R028"].evaluate(request) is True

    def test_eligible_youth_hoh_with_child(self):
        request = make_aggregate_request(
            persons=[
                _default_person(age=20, household_member_type=HouseholdMemberType.HEAD_OF_HOUSEHOLD),
                _default_person(age=2, household_member_type=HouseholdMemberType.CHILD),
            ],
            income_household_total_yearly=self.HIGH_INCOME,
        )

        assert RULES["S2R028"].evaluate(request) is True

    def test_eligible_with_cash_assistance(self):
        request = make_aggregate_request(
            persons=[self.YOUTH],
            income_household_has_cash_assistance=True,
            income_household_total_yearly=self.HIGH_INCOME,
        )

        assert RULES["S2R028"].evaluate(request) is True

    def test_eligible_with_ssi(self):
        request = make_aggregate_request(
            persons=[self.YOUTH],
            income_household_has_ssi=True,
            income_household_total_yearly=self.HIGH_INCOME,
        )

        assert RULES["S2R028"].evaluate(request) is True

    def test_eligible_by_income(self):
        limit = get_threshold_limit("S2R028", 1)
        request = make_aggregate_request(
            persons=[self.YOUTH],
            income_household_total_yearly=float(limit),
        )

        assert RULES["S2R028"].evaluate(request) is True

    def test_ineligible_over_income_without_other_eligibility_rules_met(self):
        limit = float(get_threshold_limit("S2R028", 1))
        request = make_aggregate_request(
            persons=[self.YOUTH],
            income_household_total_yearly=limit + 1,
        )

        assert RULES["S2R028"].evaluate(request) is False


class TestS2R029:
    def test_eligible_with_pregnant_person_and_medicaid(self):
        request = make_computed_aggregate_request(
            persons=[_default_person(pregnant=True, benefits_medicaid=True)],
        )

        assert RULES["S2R029"].evaluate(request) is True

    def test_ineligible_household_without_pregnant_person(self):
        request = make_computed_aggregate_request(
            persons=[_default_person(age=30)],
        )

        assert RULES["S2R029"].evaluate(request) is False

    def test_eligible_by_income_using_members_plus_pregnant_size(self):
        household_size = 3
        request = make_computed_aggregate_request(
            persons=[
                _default_person(age=30),
                _default_person(
                    household_member_type=HouseholdMemberType.SPOUSE,
                    age=28,
                    pregnant=True,
                ),
            ],
        )
        request.income_household_total_yearly = get_threshold_limit("S2R029", household_size)

        assert request.members_plus_pregnant == household_size
        assert RULES["S2R029"].evaluate(request) is True


class TestS2R030:
    @pytest.mark.parametrize(
        "age, expected",
        [
            pytest.param(16, True, id="eligible_youth"),
            pytest.param(25, False, id="ineligible_youth_outside_age_range"),
        ],
    )
    def test_youth_age_eligibility(self, age, expected):
        request = make_aggregate_request(persons=[_default_person(age=age)])

        assert RULES["S2R030"].evaluate(request) is expected


class TestS2R031:
    def test_ineligible_when_all_members_have_medicaid(self):
        request = make_computed_aggregate_request(
            persons=[
                _default_person(benefits_medicaid=True),
                _default_person(
                    household_member_type=HouseholdMemberType.SPOUSE,
                    benefits_medicaid_disability=True,
                ),
            ],
        )

        assert RULES["S2R031"].evaluate(request) is False

    def test_eligible_with_uninsured_member_and_monthly_income_within_limit(self):
        limit = get_threshold_limit("S2R031", 1)
        request = make_computed_aggregate_request(
            persons=[
                _default_person(
                    benefits_medicaid=False,
                    incomes=[
                        Income(
                            amount=float(limit),
                            type=IncomeType.WAGES,
                            frequency=Frequency.MONTHLY,
                        )
                    ],
                )
            ],
        )

        assert RULES["S2R031"].evaluate(request) is True


class TestS2R032:
    @pytest.mark.parametrize(
        "age, expected",
        [
            pytest.param(10, True, id="eligible_age_10"),
            pytest.param(9, False, id="ineligible_under_10"),
        ],
    )
    def test_minimum_age_10(self, age, expected):
        request = make_aggregate_request(persons=[_default_person(age=age)])

        assert RULES["S2R032"].evaluate(request) is expected


class TestS2R033:
    ADULT = _default_person(age=30)
    CHILD = _default_person(age=10, household_member_type=HouseholdMemberType.CHILD)
    HIGH_INCOME = 999999.0

    @pytest.mark.parametrize(
        "persons, cash_assistance, has_ssi, income_key, expected",
        [
            pytest.param([ADULT], True, False, "high", True, id="eligible_household_receives_cash_assistance"),
            pytest.param([ADULT, CHILD], True, False, "high", True, id="eligible_multi_member_with_cash_assistance"),
            pytest.param([ADULT], False, True, "high", True, id="eligible_single_member_household_receives_ssi"),
            pytest.param([ADULT, CHILD], False, True, "high", False, id="ineligible_multi_family_household_with_ssi"),
            pytest.param([ADULT], False, False, "at_limit", True, id="eligible_by_income"),
            pytest.param([ADULT], False, False, "over_limit", False, id="ineligible_over_income_limit"),
            pytest.param([ADULT, CHILD], False, False, "over_limit", False, id="ineligible_multi_member_over_income"),
        ],
    )
    def test_eligibility(
        self,
        persons,
        cash_assistance,
        has_ssi,
        income_key,
        expected,
    ):
        household_size = len(persons)
        if income_key == "high":
            income = self.HIGH_INCOME
        else:
            limit = float(get_threshold_limit("S2R033", household_size))
            income = limit + 1 if income_key == "over_limit" else limit

        request = make_aggregate_request(
            persons=persons,
            income_household_has_cash_assistance=cash_assistance,
            income_household_has_ssi=has_ssi,
            income_household_total_monthly=income,
        )

        assert RULES["S2R033"].evaluate(request) is expected


class TestS2R034:
    ADULT = _default_person(age=30)
    MINOR = _default_person(age=17)

    @pytest.mark.parametrize(
        "persons, income_key, expected",
        [
            pytest.param([MINOR], "any", False, id="ineligible_without_adult_18_to_64"),
            pytest.param([ADULT], "at_limit", True, id="eligible_at_income_limit"),
            pytest.param([ADULT], "over_limit", False, id="ineligible_over_income_limit"),
        ],
    )
    def test_eligibility(self, persons, income_key, expected):
        limit = get_threshold_limit("S2R034")
        if income_key == "at_limit":
            income = float(limit)
        elif income_key == "over_limit":
            income = float(limit) + 1
        else:
            income = 0.0

        request = make_aggregate_request(
            persons=persons,
            income_household_total_yearly=income,
        )

        assert RULES["S2R034"].evaluate(request) is expected


class TestS2R035:
    HOH = _default_person(age=21)
    CHILD = _default_person(age=1, household_member_type=HouseholdMemberType.CHILD)
    INDIVIDUAL_LIMIT = float(limits_for("S2R035").get(1))

    def test_eligible_family_relations_household_within_income_limit(self):
        request = make_aggregate_request(
            persons=[self.HOH, self.CHILD],
            income_household_total_yearly=get_threshold_limit("S2R035", 2),
        )

        assert RULES["S2R035"].evaluate(request) is True

    def test_ineligible_family_relations_household_over_income_limit(self):
        request = make_aggregate_request(
            persons=[self.HOH, self.CHILD],
            income_household_total_yearly=float(get_threshold_limit("S2R035", 2)) + 1,
        )

        assert RULES["S2R035"].evaluate(request) is False

    def test_ineligible_hoh_under_eighteen(self):
        request = make_aggregate_request(
            persons=[_default_person(age=17), self.CHILD],
            income_household_total_yearly=0.0,
        )

        assert RULES["S2R035"].evaluate(request) is False

    @pytest.mark.parametrize(
        "member_type",
        [HouseholdMemberType.SPOUSE, HouseholdMemberType.DOMESTIC_PARTNER],
        ids=["minor_spouse", "minor_domestic_partner"],
    )
    def test_ineligible_minor_spouse_or_partner(self, member_type):
        request = make_aggregate_request(
            persons=[
                self.HOH,
                _default_person(age=17, household_member_type=member_type),
            ],
            income_household_total_yearly=0.0,
        )

        assert RULES["S2R035"].evaluate(request) is False

    def test_unrelated_adult_path_uses_individual_income_limit(self):
        request = make_computed_aggregate_request(
            persons=[
                self.HOH,
                _default_person(
                    age=30,
                    household_member_type=HouseholdMemberType.UNRELATED,
                    incomes=[
                        Income(
                            amount=self.INDIVIDUAL_LIMIT,
                            type=IncomeType.WAGES,
                            frequency=Frequency.YEARLY,
                        )
                    ],
                ),
            ],
        )

        assert RULES["S2R035"].evaluate(request) is True

    def test_ineligible_unrelated_adults_when_individual_income_limits_not_met(self):
        over_limit = self.INDIVIDUAL_LIMIT + 1
        request = make_computed_aggregate_request(
            persons=[
                _default_person(
                    age=30,
                    incomes=[
                        Income(
                            amount=over_limit,
                            type=IncomeType.WAGES,
                            frequency=Frequency.YEARLY,
                        )
                    ],
                ),
                _default_person(
                    age=30,
                    household_member_type=HouseholdMemberType.UNRELATED,
                    incomes=[
                        Income(
                            amount=over_limit,
                            type=IncomeType.WAGES,
                            frequency=Frequency.YEARLY,
                        )
                    ],
                ),
            ],
        )

        assert RULES["S2R035"].evaluate(request) is False

    def test_ineligible_unrelated_household_with_fewer_than_two_adults(self):
        request = make_aggregate_request(
            persons=[
                self.HOH,
                _default_person(age=17, household_member_type=HouseholdMemberType.UNRELATED),
            ],
            income_household_total_yearly=0.0,
        )

        assert RULES["S2R035"].evaluate(request) is False


class TestS2R036:
    YOUTH = _default_person(age=20, student=False, unemployed=True)
    HIGH_INCOME = 999_999.0

    @pytest.mark.parametrize(
        "person_kwargs",
        [
            pytest.param({"age": 20, "student": True, "unemployed": True}, id="ineligible_student"),
            pytest.param({"age": 20, "student": False, "unemployed": False}, id="ineligible_not_unemployed"),
            pytest.param({"age": 15, "student": False, "unemployed": True, "disabled": True}, id="ineligible_age_lower_than_16"),
            pytest.param({"age": 25, "student": False, "unemployed": True, "disabled": True}, id="ineligible_age_over_24"),
        ],
    )
    def test_ineligible_youth(self, person_kwargs):
        request = make_aggregate_request(
            persons=[_default_person(**person_kwargs)],
            income_household_total_yearly=0.0,
        )

        assert RULES["S2R036"].evaluate(request) is False

    def test_eligible_household_living_shelter(self):
        request = make_aggregate_request(
            persons=[self.YOUTH],
            household=_default_household(living_shelter=True),
            income_household_total_yearly=self.HIGH_INCOME,
        )

        assert RULES["S2R036"].evaluate(request) is True

    def test_eligible_foster_child_youth(self):
        request = make_aggregate_request(
            persons=[
                _default_person(
                    age=18,
                    student=False,
                    unemployed=True,
                    household_member_type=HouseholdMemberType.FOSTER_CHILD,
                ),
            ],
            income_household_total_yearly=self.HIGH_INCOME,
        )

        assert RULES["S2R036"].evaluate(request) is True

    def test_eligible_youth_hoh_with_foster_parent(self):
        request = make_aggregate_request(
            persons=[
                _default_person(age=18, student=False, unemployed=True),
                _default_person(age=45, household_member_type=HouseholdMemberType.FOSTER_PARENT),
            ],
            income_household_total_yearly=self.HIGH_INCOME,
        )

        assert RULES["S2R036"].evaluate(request) is True

    def test_eligible_disabled_youth(self):
        request = make_aggregate_request(
            persons=[_default_person(age=20, student=False, unemployed=True, disabled=True)],
            income_household_total_yearly=self.HIGH_INCOME,
        )

        assert RULES["S2R036"].evaluate(request) is True

    def test_eligible_blind_youth(self):
        request = make_aggregate_request(
            persons=[_default_person(age=20, student=False, unemployed=True, blind=True)],
            income_household_total_yearly=self.HIGH_INCOME,
        )

        assert RULES["S2R036"].evaluate(request) is True

    def test_eligible_pregnant_youth(self):
        request = make_aggregate_request(
            persons=[_default_person(age=20, student=False, unemployed=True, pregnant=True)],
            income_household_total_yearly=self.HIGH_INCOME,
        )

        assert RULES["S2R036"].evaluate(request) is True

    def test_eligible_parent_youth(self):
        request = make_aggregate_request(
            persons=[
                _default_person(
                    age=22,
                    student=False,
                    unemployed=True,
                    household_member_type=HouseholdMemberType.PARENT,
                ),
            ],
            income_household_total_yearly=self.HIGH_INCOME,
        )

        assert RULES["S2R036"].evaluate(request) is True

    def test_eligible_youth_hoh_with_child(self):
        request = make_aggregate_request(
            persons=[
                _default_person(age=20, student=False, unemployed=True),
                _default_person(age=2, household_member_type=HouseholdMemberType.CHILD),
            ],
            income_household_total_yearly=self.HIGH_INCOME,
        )

        assert RULES["S2R036"].evaluate(request) is True

    def test_eligible_with_cash_assistance(self):
        request = make_aggregate_request(
            persons=[self.YOUTH],
            income_household_has_cash_assistance=True,
            income_household_total_yearly=self.HIGH_INCOME,
        )

        assert RULES["S2R036"].evaluate(request) is True

    def test_eligible_with_ssi(self):
        request = make_aggregate_request(
            persons=[self.YOUTH],
            income_household_has_ssi=True,
            income_household_total_yearly=self.HIGH_INCOME,
        )

        assert RULES["S2R036"].evaluate(request) is True

    def test_eligible_by_income(self):
        limit = get_threshold_limit("S2R036")
        request = make_aggregate_request(
            persons=[self.YOUTH],
            income_household_total_yearly=float(limit),
        )

        assert RULES["S2R036"].evaluate(request) is True

    def test_ineligible_over_income_limit(self):
        limit = float(get_threshold_limit("S2R036"))
        request = make_aggregate_request(
            persons=[self.YOUTH],
            income_household_total_yearly=limit + 1,
        )

        assert RULES["S2R036"].evaluate(request) is False


class TestS2R037:
    SENIOR = _default_person(age=70, disabled=True)
    INDIVIDUAL_LIMIT = float(limits_for("S2R037").get(1))
    HIGH_INCOME = 999_999.0

    def test_eligible_with_medicaid(self):
        request = make_aggregate_request(
            persons=[_default_person(age=70, benefits_medicaid=True)],
            income_household_total_yearly=self.HIGH_INCOME,
        )

        assert RULES["S2R037"].evaluate(request) is True

    def test_eligible_with_disability_medicaid(self):
        request = make_aggregate_request(
            persons=[_default_person(age=50, disabled=True, benefits_medicaid_disability=True)],
            income_household_total_yearly=self.HIGH_INCOME,
        )

        assert RULES["S2R037"].evaluate(request) is True

    def test_eligible_with_senior_by_household_income(self):
        request = make_aggregate_request(
            persons=[self.SENIOR],
            income_household_total_yearly=get_threshold_limit("S2R037", 1),
        )

        assert RULES["S2R037"].evaluate(request) is True

    def test_ineligible_over_household_income_limit(self):
        request = make_aggregate_request(
            persons=[self.SENIOR],
            income_household_total_yearly=float(get_threshold_limit("S2R037", 1)) + 1,
            income_person_earned_yearly={0: self.INDIVIDUAL_LIMIT + 1},
        )

        assert RULES["S2R037"].evaluate(request) is False

    def test_eligible_by_individual_earned_income_when_household_income_exceeds_limit(self):
        request = make_computed_aggregate_request(
            persons=[
                _default_person(
                    age=70,
                    disabled=True,
                    incomes=[
                        Income(
                            amount=self.INDIVIDUAL_LIMIT,
                            type=IncomeType.WAGES,
                            frequency=Frequency.YEARLY,
                        )
                    ],
                ),
                _default_person(
                    age=30,
                    household_member_type=HouseholdMemberType.SPOUSE,
                    incomes=[
                        Income(
                            amount=self.HIGH_INCOME,
                            type=IncomeType.WAGES,
                            frequency=Frequency.YEARLY,
                        )
                    ],
                ),
            ],
        )

        assert RULES["S2R037"].evaluate(request) is True

    def test_ineligible_without_disabled_senior_or_blind_person(self):
        request = make_aggregate_request(
            persons=[_default_person(age=30)],
            income_household_total_yearly=0.0,
        )

        assert RULES["S2R037"].evaluate(request) is False


class TestS2R038:
    ADULT = _default_person(age=30)

    def test_eligible_pregnant_hoh_within_pathway_limit(self):
        limit = pathway_limit("S2R038", "pregnant_and_infant", 2)
        request = make_computed_aggregate_request(
            persons=[_default_person(age=30, pregnant=True)],
        )
        request.income_person_yearly = {0: float(limit)}

        assert RULES["S2R038"].evaluate(request) is True

    def test_eligible_pregnant_spouse_within_pathway_limit(self):
        limit = pathway_limit("S2R038", "pregnant_and_infant", 3)
        request = make_computed_aggregate_request(
            persons=[
                self.ADULT,
                _default_person(
                    age=28,
                    household_member_type=HouseholdMemberType.SPOUSE,
                    pregnant=True,
                ),
            ],
        )
        request.income_person_yearly = {0: float(limit)}

        assert RULES["S2R038"].evaluate(request) is True

    def test_eligible_infant_within_pathway_limit(self):
        limit = pathway_limit("S2R038", "pregnant_and_infant", 2)
        request = make_computed_aggregate_request(
            persons=[
                self.ADULT,
                _default_person(age=0, household_member_type=HouseholdMemberType.CHILD),
            ],
        )
        request.income_person_yearly = {0: float(limit)}

        assert RULES["S2R038"].evaluate(request) is True

    @pytest.mark.parametrize("age", [19, 20], ids=["age_19", "age_20"])
    def test_eligible_young_adult_with_qualifying_child_relationship(self, age):
        limit = pathway_limit("S2R038", "young_adult", 2)
        request = make_computed_aggregate_request(
            persons=[
                self.ADULT,
                _default_person(age=age, household_member_type=HouseholdMemberType.CHILD),
            ],
        )
        request.income_person_yearly = {0: float(limit)}

        assert RULES["S2R038"].evaluate(request) is True

    def test_eligible_youth_hoh_within_pathway_limit(self):
        limit = pathway_limit("S2R038", "youth", 1)
        request = make_computed_aggregate_request(
            persons=[_default_person(age=17)],
        )
        request.income_person_yearly = {0: float(limit)}

        assert RULES["S2R038"].evaluate(request) is True

    def test_eligible_youth_with_qualifying_relationship_within_pathway_limit(self):
        limit = pathway_limit("S2R038", "youth", 2)
        request = make_computed_aggregate_request(
            persons=[
                self.ADULT,
                _default_person(age=16, household_member_type=HouseholdMemberType.CHILD),
            ],
        )
        request.income_person_yearly = {0: float(limit)}

        assert RULES["S2R038"].evaluate(request) is True

    def test_eligible_default_pathway_within_limit(self):
        limit = pathway_limit("S2R038", "default", 1)
        request = make_computed_aggregate_request(
            persons=[self.ADULT],
        )
        request.income_person_yearly = {0: float(limit)}

        assert RULES["S2R038"].evaluate(request) is True

    def test_ineligible_when_income_exceeds_all_pathways(self):
        request = make_computed_aggregate_request(
            persons=[self.ADULT],
        )
        request.income_person_yearly = {0: 999999.0}

        assert RULES["S2R038"].evaluate(request) is False


class TestS2R039:
    ADULT = _default_person(age=30)
    CHILD = _default_person(age=10, household_member_type=HouseholdMemberType.CHILD)

    @pytest.mark.parametrize(
        "persons, limit_key, income_key, expected",
        [
            pytest.param([ADULT], "general", "at_limit", True, id="eligible_at_general_limit"),
            pytest.param(
                [ADULT, CHILD],
                "with_dependent_child",
                "at_limit",
                True,
                id="eligible_with_dependent_child_limit",
            ),
            pytest.param([ADULT], "general", "over_limit", False, id="ineligible_over_general_limit"),
        ],
    )
    def test_eligibility(self, persons, limit_key, income_key, expected):
        limit = scalar_limit("S2R039", limit_key)
        income = float(limit) if income_key == "at_limit" else float(limit) + 1

        request = make_aggregate_request(
            persons=persons,
            income_household_total_yearly=income,
        )

        assert RULES["S2R039"].evaluate(request) is expected


class TestS2R040:
    HOH = _default_person(age=30)
    CHILD = _default_person(age=10, household_member_type=HouseholdMemberType.CHILD)

    def test_ineligible_without_eligible_dependent(self):
        request = make_computed_aggregate_request(persons=[self.HOH])

        assert RULES["S2R040"].evaluate(request) is False

    def test_ineligible_teen_without_disability_or_blind(self):
        request = make_computed_aggregate_request(
            persons=[
                self.HOH,
                _default_person(age=15, household_member_type=HouseholdMemberType.CHILD),
            ],
        )

        assert RULES["S2R040"].evaluate(request) is False

    def test_ineligible_disabled_dependent_over_nineteen(self):
        request = make_computed_aggregate_request(
            persons=[
                self.HOH,
                _default_person(
                    age=20,
                    disabled=True,
                    household_member_type=HouseholdMemberType.CHILD,
                ),
            ],
        )

        assert RULES["S2R040"].evaluate(request) is False

    def test_eligible_with_child_and_cash_assistance(self):
        request = make_computed_aggregate_request(
            persons=[self.HOH, self.CHILD],
        )
        request.income_household_has_cash_assistance = True

        assert RULES["S2R040"].evaluate(request) is True

    def test_eligible_with_disabled_dependent_and_cash_assistance(self):
        request = make_computed_aggregate_request(
            persons=[
                self.HOH,
                _default_person(
                    age=17,
                    disabled=True,
                    household_member_type=HouseholdMemberType.CHILD,
                ),
            ],
        )
        request.income_household_has_cash_assistance = True

        assert RULES["S2R040"].evaluate(request) is True

    def test_eligible_with_dependent_and_income_within_limit(self):
        household_size = 2
        request = make_computed_aggregate_request(
            persons=[
                _default_person(
                    age=30,
                    incomes=[
                        Income(
                            amount=get_threshold_limit("S2R040", household_size),
                            type=IncomeType.WAGES,
                            frequency=Frequency.MONTHLY,
                        )
                    ],
                ),
                self.CHILD,
            ],
        )

        assert request.child_care_voucher_household_members == household_size
        assert RULES["S2R040"].evaluate(request) is True

    def test_eligible_with_disabled_dependent_and_income_within_limit(self):
        household_size = 2
        request = make_computed_aggregate_request(
            persons=[
                _default_person(
                    age=30,
                    incomes=[
                        Income(
                            amount=get_threshold_limit("S2R040", household_size),
                            type=IncomeType.WAGES,
                            frequency=Frequency.MONTHLY,
                        )
                    ],
                ),
                _default_person(
                    age=17,
                    disabled=True,
                    household_member_type=HouseholdMemberType.CHILD,
                ),
            ],
        )

        assert request.child_care_voucher_household_members == household_size
        assert RULES["S2R040"].evaluate(request) is True

    def test_eligible_with_blind_dependent_and_income_within_limit(self):
        household_size = 2
        request = make_computed_aggregate_request(
            persons=[
                _default_person(
                    age=30,
                    incomes=[
                        Income(
                            amount=get_threshold_limit("S2R040", household_size),
                            type=IncomeType.WAGES,
                            frequency=Frequency.MONTHLY,
                        )
                    ],
                ),
                _default_person(
                    age=18,
                    blind=True,
                    household_member_type=HouseholdMemberType.CHILD,
                ),
            ],
        )

        assert request.child_care_voucher_household_members == household_size
        assert RULES["S2R040"].evaluate(request) is True

    def test_ineligible_over_income_without_cash_assistance(self):
        household_size = 2
        limit = float(get_threshold_limit("S2R040", household_size))
        request = make_computed_aggregate_request(
            persons=[
                _default_person(
                    age=30,
                    incomes=[
                        Income(
                            amount=limit + 1,
                            type=IncomeType.WAGES,
                            frequency=Frequency.MONTHLY,
                        )
                    ],
                ),
                self.CHILD,
            ],
        )

        assert RULES["S2R040"].evaluate(request) is False


class TestS2R043:
    def test_eligible_with_medicaid(self):
        request = make_aggregate_request(
            persons=[_default_person(benefits_medicaid=True)],
            income_household_total_yearly=999999.0,
        )

        assert RULES["S2R043"].evaluate(request) is True

    def test_eligible_with_nycha(self):
        request = make_aggregate_request(
            household=_default_household(
                living_renting=True,
                living_rental_type=LivingRentalType.NYCHA,
            ),
            income_household_total_yearly=999999.0,
        )

        assert RULES["S2R043"].evaluate(request) is True

    def test_eligible_with_income_household_has_benefit(self):
        request = make_aggregate_request(
            income_household_has_benefit=True,
            income_household_total_yearly=999999.0,
        )

        assert RULES["S2R043"].evaluate(request) is True

    def test_eligible_by_income(self):
        limit = get_threshold_limit("S2R043")
        request = make_aggregate_request(income_household_total_yearly=float(limit))

        assert RULES["S2R043"].evaluate(request) is True

    def test_ineligible_over_income(self):
        limit = float(get_threshold_limit("S2R043"))
        request = make_aggregate_request(
            persons=[_default_person(age=30)],
            income_household_total_yearly=limit + 1,
        )

        assert RULES["S2R043"].evaluate(request) is False


class TestS2R045:
    @pytest.mark.parametrize(
        "age, expected",
        [
            pytest.param(18, True, id="eligible_adult"),
            pytest.param(17, False, id="ineligible_without_adult"),
        ],
    )
    def test_minimum_age_18(self, age, expected):
        request = make_aggregate_request(persons=[_default_person(age=age)])

        assert RULES["S2R045"].evaluate(request) is expected


class TestS2R047:
    def test_eligible_disabled_person(self):
        request = make_aggregate_request(
            persons=[_default_person(age=30, disabled=True)],
        )

        assert RULES["S2R047"].evaluate(request) is True

    def test_eligible_disability_medicaid_income(self):
        request = make_computed_aggregate_request(
            persons=get_hoh_with_income(IncomeType.DISABILITY_MEDICAID),
        )

        assert RULES["S2R047"].evaluate(request) is True

    def test_ineligible_without_disability(self):
        request = make_aggregate_request(persons=[_default_person(age=30)])

        assert RULES["S2R047"].evaluate(request) is False


class TestS2R054:
    NYCHA = _default_household(
        living_renting=True,
        living_rental_type=LivingRentalType.NYCHA,
    )
    NON_NYCHA = _default_household(living_renting=True)

    @pytest.mark.parametrize(
        "household, expected",
        [
            pytest.param(NYCHA, True, id="eligible_with_nycha"),
            pytest.param(NON_NYCHA, False, id="ineligible_without_nycha"),
        ],
    )
    def test_nycha_eligibility(self, household, expected):
        request = make_aggregate_request(household=household)

        assert RULES["S2R054"].evaluate(request) is expected


class TestS2R055:
    def test_eligible_adult_within_income_and_cash_limits(self):
        cash_max = scalar_limit("S2R055", "cash_on_hand_maximum")
        request = make_aggregate_request(
            persons=[_default_person(age=30)],
            household=_default_household(cash_on_hand=float(cash_max)),
            income_household_total_yearly=get_threshold_limit("S2R055", 1),
        )

        assert RULES["S2R055"].evaluate(request) is True

    def test_ineligible_without_adult(self):
        request = make_aggregate_request(
            persons=[_default_person(age=17)],
            income_household_total_yearly=0.0,
        )

        assert RULES["S2R055"].evaluate(request) is False

    def test_ineligible_when_cash_on_hand_exceeds_maximum(self):
        cash_max = scalar_limit("S2R055", "cash_on_hand_maximum")
        request = make_aggregate_request(
            persons=[_default_person(age=30)],
            household=_default_household(cash_on_hand=float(cash_max) + 1),
            income_household_total_yearly=0.0,
        )

        assert RULES["S2R055"].evaluate(request) is False


class TestS2R056:
    def test_always_eligible(self):
        assert RULES["S2R056"].evaluate(make_aggregate_request()) is True


class TestS2R057:
    ADULT = _default_person(age=30)
    INFANT = _default_person(age=0, household_member_type=HouseholdMemberType.CHILD)
    CHILD = _default_person(age=10, household_member_type=HouseholdMemberType.CHILD)

    @pytest.mark.parametrize(
        "persons, pathway, income_key, expected",
        [
            pytest.param(
                [ADULT, INFANT],
                "infant",
                "above",
                True,
                id="eligible_infant_above_threshold",
            ),
            pytest.param(
                [ADULT, CHILD],
                "child",
                "at",
                False,
                id="ineligible_child_at_threshold",
            ),
            pytest.param(
                [ADULT],
                None,
                "high",
                False,
                id="ineligible_without_eligible_child",
            ),
        ],
    )
    def test_eligibility(self, persons, pathway, income_key, expected):
        if pathway is None:
            income = 999999.0
        else:
            threshold = pathway_limit("S2R057", pathway, len(persons))
            if income_key == "above":
                income = float(threshold) + 1
            else:
                income = float(threshold)

        request = make_aggregate_request(
            persons=persons,
            income_household_total_yearly=income,
        )

        assert RULES["S2R057"].evaluate(request) is expected


class TestS2R058:
    def test_eligible_uninsured_adult_within_income_limit(self):
        request = make_aggregate_request(
            persons=[_default_person(age=30, benefits_medicaid=False)],
            income_household_total_yearly=get_threshold_limit("S2R058", 1),
        )

        assert RULES["S2R058"].evaluate(request) is True

    def test_ineligible_when_adult_has_medicaid(self):
        request = make_aggregate_request(
            persons=[_default_person(age=30, benefits_medicaid=True)],
            income_household_total_yearly=0.0,
        )

        assert RULES["S2R058"].evaluate(request) is False

    def test_ineligible_when_adult_has_disability_medicaid(self):
        request = make_aggregate_request(
            persons=[_default_person(age=30, benefits_medicaid_disability=True)],
            income_household_total_yearly=0.0,
        )

        assert RULES["S2R058"].evaluate(request) is False

    def test_eligible_when_spouse_has_disability_medicaid_and_hoh_is_uninsured(self):
        request = make_aggregate_request(
            persons=[
                _default_person(age=30, benefits_medicaid=False),
                _default_person(
                    age=30,
                    household_member_type=HouseholdMemberType.SPOUSE,
                    benefits_medicaid_disability=True,
                ),
            ],
            income_household_total_yearly=get_threshold_limit("S2R058", 2),
        )

        assert RULES["S2R058"].evaluate(request) is True


class TestS2R059:
    def test_eligible_senior(self):
        request = make_aggregate_request(persons=[_default_person(age=65)])

        assert RULES["S2R059"].evaluate(request) is True

    def test_eligible_student_age_fourteen_to_eighteen(self):
        request = make_aggregate_request(persons=[_default_person(age=16, student=True)])

        assert RULES["S2R059"].evaluate(request) is True

    def test_eligible_blind_person(self):
        request = make_aggregate_request(persons=[_default_person(age=30, blind=True)])

        assert RULES["S2R059"].evaluate(request) is True

    def test_eligible_disabled_person(self):
        request = make_aggregate_request(persons=[_default_person(age=30, disabled=True)])

        assert RULES["S2R059"].evaluate(request) is True

    def test_ineligible_adult(self):
        request = make_aggregate_request(persons=[_default_person(age=30)])

        assert RULES["S2R059"].evaluate(request) is False


class TestS2R060:
    def test_eligible_with_medicaid(self):
        request = make_aggregate_request(
            persons=[_default_person(age=30, benefits_medicaid=True)],
        )

        assert RULES["S2R060"].evaluate(request) is True

    def test_eligible_with_disability_medicaid(self):
        request = make_aggregate_request(
            persons=[_default_person(age=30, benefits_medicaid_disability=True)],
        )

        assert RULES["S2R060"].evaluate(request) is True

    def test_ineligible_without_medicaid(self):
        request = make_aggregate_request(persons=[_default_person(age=30)])

        assert RULES["S2R060"].evaluate(request) is False


class TestS2R061:
    def test_eligible_senior(self):
        request = make_aggregate_request(persons=[_default_person(age=70)])

        assert RULES["S2R061"].evaluate(request) is True

    def test_eligible_disabled_person(self):
        request = make_aggregate_request(persons=[_default_person(age=30, disabled=True)])

        assert RULES["S2R061"].evaluate(request) is True

    def test_eligible_blind_person(self):
        request = make_aggregate_request(persons=[_default_person(age=30, blind=True)])

        assert RULES["S2R061"].evaluate(request) is True

    def test_eligible_disability_medicaid(self):
        request = make_aggregate_request(
            persons=[_default_person(age=30, benefits_medicaid_disability=True)],
        )

        assert RULES["S2R061"].evaluate(request) is True

    def test_eligible_ssi_income(self):
        request = make_computed_aggregate_request(
            persons=get_hoh_with_income(IncomeType.SSI),
        )

        assert RULES["S2R061"].evaluate(request) is True

    def test_ineligible_adult(self):
        request = make_aggregate_request(persons=[_default_person(age=30)])

        assert RULES["S2R061"].evaluate(request) is False


class TestS2R062:
    def test_eligible_with_child_and_medicaid(self):
        request = make_aggregate_request(
            persons=[_default_person(age=10, benefits_medicaid=True)],
            income_household_total_monthly=999999.0,
        )

        assert RULES["S2R062"].evaluate(request) is True

    def test_eligible_with_child_by_income(self):
        request = make_aggregate_request(
            persons=[_default_person(age=10)],
            income_household_total_monthly=get_threshold_limit("S2R062", 1),
        )

        assert RULES["S2R062"].evaluate(request) is True

    def test_ineligible_child_outside_age_range(self):
        request = make_aggregate_request(
            persons=[_default_person(age=5)],
            income_household_total_monthly=0.0,
        )

        assert RULES["S2R062"].evaluate(request) is False


class TestS2R085:
    @pytest.mark.parametrize(
        "age, expected",
        [
            pytest.param(3, True, id="eligible_age_3"),
            pytest.param(4, False, id="ineligible_age_4"),
            pytest.param(2, False, id="ineligible_age_2"),
        ],
    )
    def test_age_three_eligibility(self, age, expected):
        request = make_aggregate_request(persons=[_default_person(age=age)])

        assert RULES["S2R085"].evaluate(request) is expected
