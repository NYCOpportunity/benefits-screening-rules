"""
Disability Rent Increase Exemption eligibility rule (S2R005)
"""

from __future__ import annotations

from src.rules.base_rule import BaseRule
from src.rules.registry import register_rule
from src.models.enums import HouseholdMemberType, LivingRentalType, IncomeType
from src.rules.thresholds import scalar_limit


@register_rule
class DisabilityRentIncreaseExemption(BaseRule):
    program = "S2R005"
    description = "Disability Rent Increase Exemption (DRIE) (DOF) - Rent increase exemption for disabled tenants"

    @classmethod
    def evaluate(cls, request) -> bool:
        """
        Eligibility requires:
        1. Household is renting specific types (Rent Controlled, HDFC, Mitchell Lama, Section 213)
        2. Head of household is 18+ and on the lease
        3. Head of household has SSI, SSDisability, Veteran, or DisabilityMedicaid income
        4. Total yearly household income at or below maximum (see thresholds.yaml for this program rule)
        """
        household = request.household[0]
        persons = request.person
        
        # Check if renting
        if not household.living_renting:
            return False
        
        # Check rental type
        eligible_rental_types = [
            LivingRentalType.RENT_CONTROLLED,
            LivingRentalType.HDFC,
            LivingRentalType.MITCHELL_LAMA,
            LivingRentalType.SECTION_213
        ]
        
        if household.living_rental_type not in eligible_rental_types:
            return False
        
        # Find head of household
        head_of_household = next(
            (p for p in persons if p.household_member_type == HouseholdMemberType.HEAD_OF_HOUSEHOLD),
            None
        )
        
        if not head_of_household:
            return False
        
        # Check if head is 18+ and on lease
        if head_of_household.age < 18 or not head_of_household.living_rental_on_lease:
            return False
        
        # Check if head has qualifying income types (IncomeHeadHasS2R005Income in Drools)
        if not cls._head_has_qualifying_income(head_of_household):
            return False
        
        maximum = scalar_limit("S2R005", "maximum")
        if maximum is None:
            return False

        if request.income_household_total_yearly > maximum:
            return False

        return True
    
    @classmethod
    def _head_has_qualifying_income(cls, head_of_household) -> bool:
        """Match IncomeHeadHasS2R005Income in IncomeAggregates.drl."""
        qualifying_income_types = [
            IncomeType.SSI,
            IncomeType.SS_DISABILITY,
            IncomeType.VETERAN,
            IncomeType.DISABILITY_MEDICAID,
        ]

        return any(
            income.type in qualifying_income_types
            for income in head_of_household.incomes
        )