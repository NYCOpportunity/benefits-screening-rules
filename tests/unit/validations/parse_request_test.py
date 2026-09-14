import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.validation.parse_request import INVALID_PAYLOAD_MESSAGE, parse_request


current_dir = Path(__file__).parent
data_payloads_dir = current_dir.parent.parent / "data" / "payloads"


def test_parse_valid_payload():
    file_path = data_payloads_dir / "eligibility-program-test-payload.json"
    with open(file_path) as f:
        data = json.load(f)

    request = parse_request(data)
    assert request.person[0].age == 23
    assert request.withhold_payload is True


def test_parse_invalid_payload():
    file_path = data_payloads_dir / "invalid-eligibility-payload.json"
    with open(file_path) as f:
        data = json.load(f)

    with pytest.raises(ValidationError):
        parse_request(data)

    assert INVALID_PAYLOAD_MESSAGE == 'Invalid eligibility request payload'


def test_parse_requires_household_member_type():
    payload = {
        'household': [{}],
        'person': [
            {'age': 25, 'householdMemberType': 'HeadOfHousehold'},
            {'age': 11},
        ],
    }

    with pytest.raises(ValidationError) as exc_info:
        parse_request(payload)

    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert errors[0]['type'] == 'missing'
    assert errors[0]['loc'] == ('person', 1, 'householdMemberType')
    assert errors[0]['msg'] == 'Field required'
