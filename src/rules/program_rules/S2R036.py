"""
Train & Earn eligibility rule (S2R036)
"""

from __future__ import annotations

from src.rules.base_rule import BaseRule
from src.rules.registry import register_rule
from src.models.enums import HouseholdMemberType
from src.rules.thresholds import income_at_or_below


@register_rule
class TrainEarn(BaseRule):
    program = "S2R036"
    description = "Train & Earn (DYCD) - Job training for unemployed youth not in school"

    @classmethod
    def evaluate(cls, request) -> bool:
        """
        Eligibility requires unemployed youth aged 16-24 not in school who meet ANY of:
        1. Lives in a shelter
        2. Is in foster care
        3. Is disabled or blind
        4. Is pregnant or a parent
        5. Household receives Cash Assistance or SSI
        6. Household income below thresholds based on household size
        """
        household = request.household[0]
        persons = request.person
        household_size = len(persons)
        
        # Find eligible youth (16-24, not student, unemployed)
        eligible_youth = [
            p for p in persons 
            if 16 <= p.age <= 24 and not p.student and p.unemployed
        ]
        
        if not eligible_youth:
            return False
        
        # Check condition 1: Lives in shelter
        if household.living_shelter:
            return True
        
        # Check condition 2: Foster care
        for youth in eligible_youth:
            if youth.household_member_type == HouseholdMemberType.FOSTER_CHILD:
                return True
            # Check if youth is head of household with foster parent
            if (youth.household_member_type == HouseholdMemberType.HEAD_OF_HOUSEHOLD and
                any(p.household_member_type == HouseholdMemberType.FOSTER_PARENT for p in persons)):
                return True
        
        # Check condition 3: Disabled or blind
        if any(youth.disabled or youth.blind for youth in eligible_youth):
            return True
        
        # Check condition 4: Pregnant or parent
        for youth in eligible_youth:
            if youth.pregnant:
                return True
            if youth.household_member_type == HouseholdMemberType.PARENT:
                return True
            if youth.household_member_type == HouseholdMemberType.HEAD_OF_HOUSEHOLD:
                if any(
                    p.household_member_type == HouseholdMemberType.CHILD
                    for p in persons
                ):
                    return True
        
        # Check condition 5: Cash Assistance or SSI
        if request.income_household_has_cash_assistance or request.income_household_has_ssi:
            return True

        return income_at_or_below(request, cls.program, household_size)
