"""
Disabled Homeowners' Exemption rule (S2R017)
"""

from __future__ import annotations

from src.rules.base_rule import BaseRule
from src.rules.registry import register_rule
from src.models.enums import IncomeType
from src.rules.thresholds import scalar_limit


@register_rule
class DisabledHomeownersExemption(BaseRule):
    program = "S2R017"
    description = "Disabled Homeowners' Exemption (DHE) (DOF) - Property tax exemption for disabled homeowners"

    @classmethod
    def evaluate(cls, request) -> bool:
        """
        Eligibility requires:
        1. Household owns their home
        2. Total yearly income of all owners at or below maximum (see thresholds.yaml for this program rule)
        3. At least one owner is either:
           - Disabled
           - Blind
           - Receiving SSI or SS Disability benefits
        """
        household = request.household[0]
        persons = request.person
        
        # Check home ownership
        if not household.living_owner:
            return False
        
        maximum = scalar_limit("S2R017", "maximum")
        if maximum is None or request.income_owners_total_yearly > maximum:
            return False
        
        # Check for disabled or blind owner on deed
        has_disabled_or_blind_owner = any(
            p.living_owner_on_deed and (p.disabled or p.blind)
            for p in persons
        )
        
        if has_disabled_or_blind_owner:
            return True
        
        # Check if any owner has SSI or SS Disability income
        for person in persons:
            if person.living_owner_on_deed:
                for income in person.incomes:
                    if income.type in [IncomeType.SSI, IncomeType.SS_DISABILITY]:
                        return True
        
        return False