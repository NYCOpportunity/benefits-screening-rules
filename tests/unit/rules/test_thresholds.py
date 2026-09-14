import pytest

from src.models.schemas import AggregateEligibilityRequest
from src.rules import thresholds as thresholds_module
from src.rules.thresholds import _load_thresholds, income_at_or_below, limits_for, pathway_limit, scalar_limit
from tests.helpers.request_factory import make_aggregate_request

TEST_THRESHOLDS = {
    "TEST": {
        "field": "income_household_total_yearly",
        "by_size": {1: 100},
    }
}


PROGRAM_CODES = [
    key for key, config in _load_thresholds().items() if "by_size" in config
]


@pytest.fixture(autouse=True)
def clear_threshold_cache():
    thresholds_module._load_thresholds.cache_clear()
    yield
    thresholds_module._load_thresholds.cache_clear()


@pytest.fixture
def test_thresholds(monkeypatch):
    monkeypatch.setattr(thresholds_module, "_load_thresholds", lambda: TEST_THRESHOLDS)


@pytest.mark.parametrize("program_code", PROGRAM_CODES)
def test_threshold_config_is_valid(program_code):
    config = _load_thresholds()[program_code]
    by_size = limits_for(program_code)

    assert "field" in config
    field = config["field"]
    assert field in AggregateEligibilityRequest.model_fields
    assert by_size
    assert all(isinstance(size, int) and size >= 1 for size in by_size)
    assert all(isinstance(limit, (int, float)) and limit > 0 for limit in by_size.values())


def test_s2r007_fpl_pathways():
    snap_config = _load_thresholds()["S2R007"]

    assert set(snap_config) == {"fpl_130", "fpl_150", "fpl_200"}
    for pathway in snap_config.values():
        by_size = pathway["by_size"]
        assert by_size
        assert all(isinstance(size, int) and size >= 1 for size in by_size)
        assert all(isinstance(limit, (int, float)) and limit > 0 for limit in by_size.values())


@pytest.mark.parametrize(
    ("program", "pathways"),
    [
        ("S2R007", {"fpl_130", "fpl_150", "fpl_200"}),
        ("S2R010", {"with_child_or_pregnant", "general"}),
        ("S2R038", {"pregnant_and_infant", "young_adult", "youth", "default"}),
        ("S2R057", {"infant", "child"}),
    ],
)
def test_pathway_threshold_config(program, pathways):
    config = _load_thresholds()[program]

    assert set(config) == pathways
    for pathway in config.values():
        by_size = pathway["by_size"]
        assert by_size
        assert all(isinstance(size, int) and size >= 1 for size in by_size)
        assert all(isinstance(limit, (int, float)) and limit > 0 for limit in by_size.values())


def test_s2r006_threshold_config():
    config = _load_thresholds()["S2R006"]
    scalar_keys = (
        "investment_limit",
        "married_no_children",
        "single_no_children",
        "other_member",
    )
    pathway_keys = ("married_with_children", "single_with_children")

    for key in scalar_keys:
        limit = scalar_limit("S2R006", key)
        assert limit == config[key]
        assert limit > 0

    for pathway_key in pathway_keys:
        by_size = config[pathway_key]["by_size"]
        assert by_size
        assert all(isinstance(size, int) and size >= 1 for size in by_size)
        assert all(isinstance(limit, (int, float)) and limit > 0 for limit in by_size.values())
        for size, expected in by_size.items():
            assert pathway_limit("S2R006", pathway_key, size) == expected


@pytest.mark.parametrize(
    ("program", "keys"),
    [
        ("S2R004", ("minimum", "single", "married")),
        ("S2R005", ("maximum",)),
        ("S2R012", ("maximum",)),
        ("S2R014", ("maximum",)),
        ("S2R015", ("maximum",)),
        ("S2R017", ("maximum",)),
        ("S2R039", ("general", "with_dependent_child")),
        ("S2R055", ("cash_on_hand_maximum",)),
    ],
)
def test_scalar_threshold_config(program, keys):
    for key in keys:
        limit = scalar_limit(program, key)
        assert limit is not None
        assert limit > 0


def test_scalar_limit_unknown_key():
    assert scalar_limit("S2R005", "unknown_key") is None


def test_limits_for_unknown_household_size():
    assert limits_for("S2R035").get(99) is None


def test_pathway_limit_unknown_household_size():
    assert pathway_limit("S2R007", "fpl_130", 99) is None


def test_income_at_or_below_at_limit(test_thresholds):
    request = make_aggregate_request(income_household_total_yearly=100.0)

    assert income_at_or_below(request, "TEST", 1) is True


def test_income_at_or_below_one_dollar_over(test_thresholds):
    request = make_aggregate_request(income_household_total_yearly=101.0)

    assert income_at_or_below(request, "TEST", 1) is False


def test_income_at_or_below_unknown_household_size(test_thresholds):
    request = make_aggregate_request(income_household_total_yearly=50.0)

    assert income_at_or_below(request, "TEST", 99) is False
