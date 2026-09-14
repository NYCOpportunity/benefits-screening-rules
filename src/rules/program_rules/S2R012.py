"""
School Tax Relief program eligibility rule (S2R012)
"""

from __future__ import annotations

from src.rules.base_rule import BaseRule
from src.rules.registry import register_rule
from src.rules.thresholds import scalar_limit


@register_rule
class SchoolTaxRelief(BaseRule):
    program = "S2R012"
    description = "School Tax Relief (STAR) (DOF) - Property tax relief for homeowners"

    @classmethod
    def evaluate(cls, request) -> bool:
        """
        Eligibility requires:
        1. Household owns their home
        2. Total yearly income of all owners at or below maximum (see thresholds.yaml for this program rule)
        """
        household = request.household[0]
        
        # Check home ownership
        if not household.living_owner:
            return False

        # Check owners' income threshold
        maximum = scalar_limit("S2R012", "maximum")
        if maximum is None:
            return False
        return request.income_owners_total_yearly <= maximum
