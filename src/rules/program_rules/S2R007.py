"""
Supplemental Nutrition Assistance Program eligibility rule (S2R007)
"""

from __future__ import annotations

from src.rules.base_rule import BaseRule
from src.rules.registry import register_rule
from src.models.enums import IncomeType
from src.rules.thresholds import pathway_limit


@register_rule
class SupplementalNutritionAssistanceProgram(BaseRule):
    program = "S2R007"
    description = "Supplemental Nutrition Assistance Program (SNAP/Food Stamps) (HRA) - Food assistance program"

    @classmethod
    def evaluate(cls, request) -> bool:
        """
        SNAP eligibility has multiple pathways:
        1. All household members receive SSI or Cash Assistance (categorical eligibility)
        2. Income under 200% FPL with special circumstances (elderly/disabled/child care expenses)
        3. Income under 150% FPL with earned income
        4. Income under 130% FPL for all others
        """
        persons = request.person
        household_size = len(persons)
        
        # Check categorical eligibility (all members have SSI or Cash Assistance)
        if cls._check_categorical_eligibility(request, persons):
            return True
        
        # Calculate SNAP budget
        snap_income = request.income_household_total_monthly - request.expense_household_child_support_monthly

        # 200% FPL threshold
        if cls._200_fpl_pathway(request, persons):
            threshold = pathway_limit("S2R007", "fpl_200", household_size)
            if threshold is not None and snap_income <= threshold:
                return True
        # 150% FPL threshold
        elif cls._150_fpl_pathway(request):
            threshold = pathway_limit("S2R007", "fpl_150", household_size)
            if threshold is not None and snap_income <= threshold:
                return True
        # 130% FPL threshold (all others)
        else:
            threshold = pathway_limit("S2R007", "fpl_130", household_size)
            if threshold is not None and snap_income <= threshold:
                return True
            
        return False

    @classmethod
    def _check_categorical_eligibility(cls, request, persons) -> bool:
        """Check if all household members have SSI or Cash Assistance"""
        if len(persons) == 0:
            return False
            
        # Check if all persons have either SSI or Cash Assistance
        for person in persons:
            has_ssi = False
            has_cash_assistance = False
            
            for income in person.incomes:
                if income.type == IncomeType.SSI:
                    has_ssi = True
                elif income.type == IncomeType.CASH_ASSISTANCE:
                    has_cash_assistance = True
            
            if not (has_ssi or has_cash_assistance):
                return False

        return True

    @classmethod
    def _200_fpl_pathway(cls, request, persons):
        # Any elderly/disabled/child care dependent
        has_child_care_expenses = request.expense_household_has_child_or_dependent_care
        has_elderly = any(p.age >= 60 for p in persons)
        has_disabled_or_blind = any(p.disabled or p.blind for p in persons)
        return has_child_care_expenses or has_elderly or has_disabled_or_blind

    @classmethod
    def _150_fpl_pathway(cls, request):
        # Earned income present
        return (request.income_household_wage_self_employment_monthly > 0 or
                request.income_household_boarder_monthly > 0)