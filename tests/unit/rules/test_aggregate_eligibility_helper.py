"""Unit tests for src/rules/aggregate_eligibility_helper.py."""

import pytest

from src.models.enums import ExpenseType, Frequency, HouseholdMemberType, IncomeType
from src.models.schemas import AggregateEligibilityRequest, Person
from src.rules.aggregate_eligibility_helper import compute_aggregates, to_monthly, to_yearly
from tests.helpers.request_factory import _default_person, make_eligibility_request


@pytest.mark.parametrize(
    ("amount", "frequency", "expected_monthly"),
    [
        (12000.0, Frequency.YEARLY, 1000.0),
        (1000.0, Frequency.MONTHLY, 1000.0),
        (500.0, Frequency.WEEKLY, 500.0 * 52 / 12),
        (1000.0, Frequency.BIWEEKLY, 1000.0 * 26 / 12),
        (800.0, Frequency.SEMIMONTHLY, 1600.0),
    ],
)
def test_to_monthly_converts_by_frequency(amount, frequency, expected_monthly):
    assert to_monthly(amount, frequency) == pytest.approx(expected_monthly)


@pytest.mark.parametrize(
    ("amount", "frequency", "expected_yearly"),
    [
        (1000.0, Frequency.MONTHLY, 12000.0),
        (12000.0, Frequency.YEARLY, 12000.0),
    ],
)
def test_to_yearly_converts_by_frequency(amount, frequency, expected_yearly):
    assert to_yearly(amount, frequency) == pytest.approx(expected_yearly)


def test_compute_aggregates_when_no_incomes():
    aggregates = compute_aggregates(make_eligibility_request())

    assert aggregates["income_person_monthly"][0] == 0.0
    assert aggregates["income_person_yearly"][0] == 0.0
    assert aggregates["income_person_wage_self_employment_boarder_monthly"][0] == 0.0


def test_compute_aggregates_with_wages_and_gifts_income_types():
    wages_yearly = 50000.0
    gifts_monthly = 100.0

    request = make_eligibility_request(
        persons=[
            _default_person(
                incomes=[
                    {"amount": wages_yearly, "type": IncomeType.WAGES, "frequency": Frequency.YEARLY},
                    {"amount": gifts_monthly, "type": IncomeType.GIFTS, "frequency": Frequency.MONTHLY},
                ]
            )
        ]
    )

    aggregates = compute_aggregates(request)

    assert aggregates["income_household_total_yearly"] == pytest.approx(wages_yearly + gifts_monthly * 12)
    assert aggregates["income_household_total_monthly"] == pytest.approx(wages_yearly / 12 + gifts_monthly)
    assert aggregates["income_household_total_monthly_less_gifts"] == pytest.approx(wages_yearly / 12)
    assert aggregates["income_person_wage_self_employment_monthly"][0] == pytest.approx(wages_yearly / 12)
    assert aggregates["income_person_earned_yearly"][0] == pytest.approx(wages_yearly)
    assert aggregates["income_person_gifts_monthly"][0] == pytest.approx(gifts_monthly)
    assert aggregates["income_person_yearly"][0] == pytest.approx(wages_yearly + gifts_monthly * 12)
    assert aggregates["income_person_isy_yearly"][0] == pytest.approx(wages_yearly + gifts_monthly * 12)


def test_compute_aggregates_sums_income_across_multiple_persons():
    hoh_wages_monthly = 1000.0
    spouse_wages_monthly = 500.0

    request = make_eligibility_request(
        persons=[
            _default_person(
                incomes=[
                    {"amount": hoh_wages_monthly, "type": IncomeType.WAGES, "frequency": Frequency.MONTHLY}
                ]
            ),
            _default_person(
                household_member_type=HouseholdMemberType.SPOUSE,
                incomes=[
                    {"amount": spouse_wages_monthly, "type": IncomeType.WAGES, "frequency": Frequency.MONTHLY}
                ],
            ),
        ]
    )

    aggregates = compute_aggregates(request)

    assert aggregates["income_household_total_monthly"] == pytest.approx(
        hoh_wages_monthly + spouse_wages_monthly
    )
    assert aggregates["income_household_total_yearly"] == pytest.approx(
        (hoh_wages_monthly + spouse_wages_monthly) * 12
    )
    assert aggregates["income_person_monthly"][1] == pytest.approx(spouse_wages_monthly)


@pytest.mark.parametrize(
    ("married", "nuclear_count"),
    [(False, 1), (True, 2)],
)
def test_compute_household_composition_marital_status(married, nuclear_count):
    persons = [_default_person()]
    if married:
        persons.append(_default_person(household_member_type=HouseholdMemberType.SPOUSE))

    aggregates = compute_aggregates(make_eligibility_request(persons=persons))

    assert aggregates["head_of_household_married"] is married
    assert aggregates["members_nuclear_only"] == nuclear_count


def test_compute_household_composition_with_pregnancy_and_foster_child():
    request = make_eligibility_request(
        persons=[
            _default_person(pregnant=True),
            _default_person(household_member_type=HouseholdMemberType.FOSTER_CHILD, age=20, pregnant=True),
        ]
    )

    aggregates = compute_aggregates(request)

    assert aggregates["foster_children"] == 1
    assert aggregates["members_pregnant"] == 2
    assert aggregates["members_pregnant_not_foster"] == 1
    assert aggregates["members_plus_pregnant"] == 4
    assert aggregates["members_plus_pregnant_minus_foster"] == 3


def test_compute_household_composition_with_all_adults():
    adults_only = make_eligibility_request(persons=[_default_person(age=30)])
    with_child = make_eligibility_request(
        persons=[
            _default_person(age=35),
            _default_person(household_member_type=HouseholdMemberType.CHILD, age=10),
        ]
    )

    assert compute_aggregates(adults_only)["household_all_adults"] is True
    assert compute_aggregates(with_child)["household_all_adults"] is False


def test_compute_household_composition_with_child_care_voucher_household_members():
    request = make_eligibility_request(
        persons=[
            _default_person(age=35),
            _default_person(household_member_type=HouseholdMemberType.CHILD, age=10),
            _default_person(household_member_type=HouseholdMemberType.OTHER, age=19, blind=True),
        ]
    )

    assert compute_aggregates(request)["child_care_voucher_household_members"] == 3


@pytest.mark.parametrize(
    ("persons", "expected"),
    [
        (
            [
                _default_person(age=40),
                _default_person(household_member_type=HouseholdMemberType.CHILD, age=10),
            ],
            1,
        ),
        (
            [
                _default_person(age=45),
                _default_person(
                    household_member_type=HouseholdMemberType.CHILD,
                    age=22,
                    student_fulltime=True,
                ),
            ],
            1,
        ),
        (
            [
                _default_person(age=50),
                _default_person(
                    household_member_type=HouseholdMemberType.CHILD,
                    age=23,
                    blind=True,
                ),
            ],
            1,
        ),
        (
            [
                _default_person(age=40),
                _default_person(household_member_type=HouseholdMemberType.PARENT, age=60),
            ],
            0,
        ),
        (
            [
                _default_person(age=50),
                _default_person(household_member_type=HouseholdMemberType.CHILD, age=20),
            ],
            0,
        ),
    ],
)
def test_compute_household_composition_with_eitc_qualifying_children(persons: list[Person], expected: int):
    assert compute_aggregates(make_eligibility_request(persons=persons))[
        "children_student_blind_disabled_eitc"
    ] == expected


def test_person_income_self_employment():
    self_employment_monthly = 900.0

    aggregates = compute_aggregates(
        make_eligibility_request(
            persons=[
                _default_person(
                    incomes=[
                        {
                            "amount": self_employment_monthly,
                            "type": IncomeType.SELF_EMPLOYMENT,
                            "frequency": Frequency.MONTHLY,
                        }
                    ]
                )
            ]
        )
    )

    assert aggregates["income_person_wage_self_employment_monthly"][0] == pytest.approx(
        self_employment_monthly
    )


def test_person_income_wages_and_boarder():
    wages_monthly = 600.0
    boarder_monthly = 200.0

    aggregates = compute_aggregates(
        make_eligibility_request(
            persons=[
                _default_person(
                    incomes=[
                        {"amount": wages_monthly, "type": IncomeType.WAGES, "frequency": Frequency.MONTHLY},
                        {"amount": boarder_monthly, "type": IncomeType.BOARDER, "frequency": Frequency.MONTHLY},
                    ]
                )
            ]
        )
    )

    assert aggregates["income_person_wage_self_employment_monthly"][0] == pytest.approx(wages_monthly)
    assert aggregates["income_person_wage_self_employment_boarder_monthly"][0] == pytest.approx(
        wages_monthly + boarder_monthly
    )


def test_person_income_investment_and_rental_yearly():
    investment_yearly = 1200.0
    rental_yearly = 600.0

    aggregates = compute_aggregates(
        make_eligibility_request(
            persons=[
                _default_person(
                    incomes=[
                        {
                            "amount": investment_yearly,
                            "type": IncomeType.INVESTMENT,
                            "frequency": Frequency.YEARLY,
                        },
                        {"amount": rental_yearly, "type": IncomeType.RENTAL, "frequency": Frequency.YEARLY},
                    ]
                )
            ]
        )
    )

    assert aggregates["income_person_investment_yearly"][0] == pytest.approx(
        investment_yearly + rental_yearly
    )


def test_household_income_excludes_foster_child_income_from_total_monthly_less_foster():
    hoh_wages_monthly = 1000.0
    foster_wages_monthly = 400.0

    request = make_eligibility_request(
        persons=[
            _default_person(
                incomes=[
                    {"amount": hoh_wages_monthly, "type": IncomeType.WAGES, "frequency": Frequency.MONTHLY}
                ]
            ),
            _default_person(
                household_member_type=HouseholdMemberType.FOSTER_CHILD,
                age=10,
                incomes=[
                    {"amount": foster_wages_monthly, "type": IncomeType.WAGES, "frequency": Frequency.MONTHLY}
                ],
            ),
        ]
    )

    aggregates = compute_aggregates(request)

    assert aggregates["income_household_total_monthly"] == pytest.approx(
        hoh_wages_monthly + foster_wages_monthly
    )
    assert aggregates["income_household_total_monthly_less_foster"] == pytest.approx(hoh_wages_monthly)


def test_household_income_by_type():
    wages_monthly = 1000.0
    additional_wages_monthly = 200.0
    ssi_monthly = 800.0
    boarder_monthly = 200.0

    request = make_eligibility_request(
        persons=[
            _default_person(
                incomes=[
                    {"amount": wages_monthly, "type": IncomeType.WAGES, "frequency": Frequency.MONTHLY},
                    {"amount": ssi_monthly, "type": IncomeType.SSI, "frequency": Frequency.MONTHLY},
                    {"amount": additional_wages_monthly, "type": IncomeType.WAGES, "frequency": Frequency.MONTHLY},
                    {"amount": boarder_monthly, "type": IncomeType.BOARDER, "frequency": Frequency.MONTHLY},
                ]
            )
        ]
    )

    aggregates = compute_aggregates(request)

    assert aggregates["income_household_wage_self_employment_monthly"] == pytest.approx(
        wages_monthly + additional_wages_monthly
    )
    assert aggregates["income_household_unearned_monthly"] == pytest.approx(ssi_monthly)
    assert aggregates["income_household_boarder_monthly"] == pytest.approx(boarder_monthly)
    assert aggregates["income_person_isy_monthly"][0] == pytest.approx(
        wages_monthly + additional_wages_monthly + boarder_monthly
    )


def test_household_nuclear_isy_yearly():
    hoh_wages_monthly = 1000.0
    spouse_wages_monthly = 500.0
    parent_wages_monthly = 700.0

    request = make_eligibility_request(
        persons=[
            _default_person(
                incomes=[
                    {"amount": hoh_wages_monthly, "type": IncomeType.WAGES, "frequency": Frequency.MONTHLY}
                ]
            ),
            _default_person(
                household_member_type=HouseholdMemberType.SPOUSE,
                incomes=[
                    {"amount": spouse_wages_monthly, "type": IncomeType.WAGES, "frequency": Frequency.MONTHLY}
                ],
            ),
            _default_person(
                household_member_type=HouseholdMemberType.PARENT,
                incomes=[
                    {"amount": parent_wages_monthly, "type": IncomeType.WAGES, "frequency": Frequency.MONTHLY}
                ],
            ),
        ]
    )

    assert compute_aggregates(request)["income_household_nuclear_isy_yearly"] == pytest.approx(
        (hoh_wages_monthly + spouse_wages_monthly) * 12
    )


def test_household_ca_work_expense_deduction_for_multiple_employed_persons():
    hoh_wages_monthly = 2000.0
    spouse_self_employment_monthly = 1000.0
    employed_persons = 2

    request = make_eligibility_request(
        persons=[
            _default_person(
                incomes=[
                    {"amount": hoh_wages_monthly, "type": IncomeType.WAGES, "frequency": Frequency.MONTHLY}
                ]
            ),
            _default_person(
                household_member_type=HouseholdMemberType.SPOUSE,
                incomes=[
                    {
                        "amount": spouse_self_employment_monthly,
                        "type": IncomeType.SELF_EMPLOYMENT,
                        "frequency": Frequency.MONTHLY,
                    }
                ],
            ),
        ]
    )

    aggregates = compute_aggregates(request)

    assert aggregates["income_household_monthly_ca"] == pytest.approx(
        hoh_wages_monthly + spouse_self_employment_monthly
    )
    assert aggregates["income_household_monthly_ca_minus_work_expense"] == pytest.approx(
        hoh_wages_monthly + spouse_self_employment_monthly - 150.0 * employed_persons
    )


def test_head_and_spouse_earned_and_ses_incomes():
    hoh_wages_monthly = 2000.0
    spouse_ss_retirement_monthly = 1000.0

    request = make_eligibility_request(
        persons=[
            _default_person(
                incomes=[
                    {"amount": hoh_wages_monthly, "type": IncomeType.WAGES, "frequency": Frequency.MONTHLY}
                ]
            ),
            _default_person(
                household_member_type=HouseholdMemberType.SPOUSE,
                incomes=[
                    {
                        "amount": spouse_ss_retirement_monthly,
                        "type": IncomeType.SS_RETIREMENT,
                        "frequency": Frequency.MONTHLY,
                    }
                ],
            ),
        ]
    )

    aggregates = compute_aggregates(request)

    assert aggregates["income_head_earned_yearly"] == pytest.approx(hoh_wages_monthly * 12)
    assert aggregates["income_head_and_spouse_earned_yearly"] == pytest.approx(hoh_wages_monthly * 12)
    assert aggregates["income_head_and_spouse_ses_monthly"] == pytest.approx(
        hoh_wages_monthly + spouse_ss_retirement_monthly * 0.75
    )
    assert aggregates["income_person_ses_monthly"][0] == pytest.approx(hoh_wages_monthly)
    assert aggregates["income_person_ses_monthly"][1] == pytest.approx(spouse_ss_retirement_monthly * 0.75)


def test_income_owners_total_yearly():
    owner_wages_monthly = 3000.0

    request = make_eligibility_request(
        persons=[
            _default_person(
                living_owner_on_deed=True,
                incomes=[
                    {"amount": owner_wages_monthly, "type": IncomeType.WAGES, "frequency": Frequency.MONTHLY}
                ],
            )
        ]
    )

    assert compute_aggregates(request)["income_owners_total_yearly"] == pytest.approx(owner_wages_monthly * 12)


def test_income_adults_children_and_child_care_voucher():
    hoh_wages_monthly = 2000.0
    partner_wages_monthly = 800.0
    child_wages_monthly = 100.0

    request = make_eligibility_request(
        persons=[
            _default_person(
                incomes=[
                    {"amount": hoh_wages_monthly, "type": IncomeType.WAGES, "frequency": Frequency.MONTHLY}
                ]
            ),
            _default_person(
                household_member_type=HouseholdMemberType.DOMESTIC_PARTNER,
                incomes=[
                    {"amount": partner_wages_monthly, "type": IncomeType.WAGES, "frequency": Frequency.MONTHLY}
                ],
            ),
            _default_person(
                household_member_type=HouseholdMemberType.CHILD,
                age=12,
                incomes=[
                    {"amount": child_wages_monthly, "type": IncomeType.WAGES, "frequency": Frequency.MONTHLY}
                ],
            ),
        ]
    )

    aggregates = compute_aggregates(request)

    assert aggregates["income_adults_children_total_monthly"] == pytest.approx(
        hoh_wages_monthly + child_wages_monthly
    )
    assert aggregates["income_child_care_voucher_total_monthly"] == pytest.approx(
        hoh_wages_monthly + partner_wages_monthly
    )
    assert aggregates["income_adults_total_monthly"] == pytest.approx(
        hoh_wages_monthly + partner_wages_monthly
    )


@pytest.mark.parametrize(
    ("income_type", "flag_name"),
    [
        (IncomeType.CASH_ASSISTANCE, "income_household_has_cash_assistance"),
        (IncomeType.UNEMPLOYMENT, "income_household_has_ui"),
        (IncomeType.VETERAN, "income_household_has_benefit"),
        (IncomeType.SSI, "income_household_has_ssi"),
    ],
)
def test_household_income_type_flags(income_type, flag_name):
    aggregates = compute_aggregates(
        make_eligibility_request(
            persons=[
                _default_person(
                    incomes=[{"amount": 100.0, "type": income_type, "frequency": Frequency.MONTHLY}]
                )
            ]
        )
    )

    assert aggregates[flag_name] is True


def test_expenses_all_types():
    child_care_monthly = 100.0
    dependent_care_monthly = 50.0
    medical_monthly = 75.0
    rent_monthly = 1200.0
    mortgage_monthly = 900.0
    child_support_monthly = 200.0

    request = make_eligibility_request(
        persons=[
            _default_person(
                expenses=[
                    {"amount": child_care_monthly, "type": ExpenseType.CHILD_CARE, "frequency": Frequency.MONTHLY},
                    {"amount": dependent_care_monthly, "type": ExpenseType.DEPENDENT_CARE, "frequency": Frequency.MONTHLY},
                    {"amount": medical_monthly, "type": ExpenseType.MEDICAL, "frequency": Frequency.MONTHLY},
                    {"amount": rent_monthly, "type": ExpenseType.RENT, "frequency": Frequency.MONTHLY},
                    {"amount": mortgage_monthly, "type": ExpenseType.MORTGAGE, "frequency": Frequency.MONTHLY},
                    {"amount": child_support_monthly, "type": ExpenseType.CHILD_SUPPORT, "frequency": Frequency.MONTHLY},
                    {"amount": 1.0, "type": ExpenseType.HEATING, "frequency": Frequency.MONTHLY},
                ]
            )
        ]
    )

    aggregates = compute_aggregates(request)
    assert aggregates["expense_household_child_dependent_care_monthly"] == pytest.approx(child_care_monthly + dependent_care_monthly)
    assert aggregates["expense_household_medical_monthly"] == pytest.approx(medical_monthly)
    assert aggregates["expense_household_rent_mortgage_monthly"] == pytest.approx(rent_monthly + mortgage_monthly)
    assert aggregates["expense_household_rent_monthly"] == pytest.approx(rent_monthly)
    assert aggregates["expense_household_child_support_monthly"] == pytest.approx(child_support_monthly)
    assert aggregates["expense_household_has_heating"] is True
    assert aggregates["expense_household_has_dependent_care"] is True
    assert aggregates["expense_household_has_child_or_dependent_care"] is True


def test_from_eligibility_request_applies_compute_aggregates():
    wages_yearly = 24000.0

    request = make_eligibility_request(
        persons=[
            _default_person(
                incomes=[
                    {"amount": wages_yearly, "type": IncomeType.WAGES, "frequency": Frequency.YEARLY},
                ]
            )
        ]
    )

    aggregate_request = AggregateEligibilityRequest.from_eligibility_request(request)

    assert aggregate_request.income_household_total_yearly == pytest.approx(wages_yearly)
    assert aggregate_request.income_head_earned_yearly == pytest.approx(wages_yearly)
