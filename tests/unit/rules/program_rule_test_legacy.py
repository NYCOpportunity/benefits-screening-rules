"""
Run legacy program rule tests converted from Postman payloads.

Run all legacy tests:
    uv run pytest tests/unit/rules/program_rule_test_legacy.py

To run tests for a single program, e.g. S2R062 (filter by program code directory):
    uv run pytest tests/unit/rules/program_rule_test_legacy.py -k S2R062
"""

import json
import pathlib
import pytest

from src.models.schemas import AggregateEligibilityRequest
from src.rules.registry import get_rules
from src.validation.parse_request import parse_request

PAYLOADS_DIR = pathlib.Path(__file__).parents[2] / "data" / "payloads"


def get_test_cases():
    rules_by_program = {rule_cls.program: rule_cls for rule_cls in get_rules()}
    test_cases = []

    for payload_folder in sorted(PAYLOADS_DIR.iterdir()):
        if not payload_folder.is_dir():
            continue

        program_code = payload_folder.name.split("_")[0]
        cls = rules_by_program[program_code]

        for label in ("true", "false"):
            folder = payload_folder / label
            if not folder.exists():
                continue

            for json_file in sorted(folder.rglob("*.json")):
                expected = label == "true"
                test_id = f"{program_code}-{json_file.relative_to(payload_folder).as_posix()}"
                test_cases.append(
                    pytest.param(
                        program_code,
                        cls,
                        json_file,
                        expected,
                        id=test_id,
                    )
                )

    return test_cases


@pytest.mark.parametrize(
    "program_code,cls,json_file,expected",
    get_test_cases(),
)
def test_legacy_program_rule_parity(program_code, cls, json_file, expected):
    with open(json_file) as f:
        payload = json.load(f)

    eligibility_request = parse_request(payload)

    aggregate_eligibility_request = AggregateEligibilityRequest.from_eligibility_request(
        eligibility_request
    )
    result = cls.evaluate(aggregate_eligibility_request)

    assert result is expected, (
        f"Benefit {program_code} ({json_file.name}): expected {expected}, got {result}"
    )
