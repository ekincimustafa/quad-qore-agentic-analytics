import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_CASES_PATH = PROJECT_ROOT / "evals" / "golden_cases.json"

REQUIRED_FIELDS = {
    "id",
    "category",
    "user_question",
    "expected_tools",
    "required_data",
    "required_behaviors",
    "forbidden_behaviors",
    "notes",
}


def load_golden_data() -> dict:
    with GOLDEN_CASES_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def test_golden_file_has_supported_schema():
    data = load_golden_data()

    assert data["schema_version"] == "1.0"
    assert data["status"] == "draft"
    assert isinstance(data["cases"], list)


def test_golden_file_contains_at_least_eight_cases():
    data = load_golden_data()

    assert len(data["cases"]) >= 8


def test_case_ids_are_unique_and_well_formed():
    data = load_golden_data()
    case_ids = [case["id"] for case in data["cases"]]

    assert len(case_ids) == len(set(case_ids))

    for case_id in case_ids:
        prefix, separator, number = case_id.partition("-")

        assert prefix == "EVAL"
        assert separator == "-"
        assert number.isdigit()


def test_every_case_has_required_fields():
    data = load_golden_data()

    for case in data["cases"]:
        missing_fields = REQUIRED_FIELDS - case.keys()

        assert not missing_fields, (
            f"{case.get('id', 'unknown')} eksik alanlar içeriyor: "
            f"{sorted(missing_fields)}"
        )

        assert isinstance(case["category"], str)
        assert case["category"].strip()

        assert isinstance(case["user_question"], str)
        assert case["user_question"].strip()

        assert isinstance(case["notes"], str)
        assert case["notes"].strip()


def test_every_case_has_valid_evaluation_rules():
    data = load_golden_data()

    list_fields = (
        "expected_tools",
        "required_data",
        "required_behaviors",
        "forbidden_behaviors",
    )

    for case in data["cases"]:
        for field in list_fields:
            assert isinstance(case[field], list)
            assert all(
                isinstance(item, str) and item.strip()
                for item in case[field]
            )

        assert case["required_data"]
        assert case["required_behaviors"]
        assert case["forbidden_behaviors"]