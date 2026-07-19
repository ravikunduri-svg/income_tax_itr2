from core.parsers._base import ParsedField, ParseResult, high, medium, low, missing


def test_parsedfield_dataclass():
    f = ParsedField(value=123.0, confidence="high", source_hint="label 'Gross Salary'")
    assert f.value == 123.0
    assert f.confidence == "high"
    assert f.source_hint == "label 'Gross Salary'"


def test_helper_high():
    f = high(42.0, "some label")
    assert f.confidence == "high"
    assert f.value == 42.0


def test_helper_medium():
    f = medium(42.0, "some label")
    assert f.confidence == "medium"


def test_helper_low():
    f = low(42.0, "some label")
    assert f.confidence == "low"


def test_helper_missing():
    f = missing("tds_inr")
    assert f.confidence == "missing"
    assert f.value is None
    assert "tds_inr" in f.source_hint


def test_parse_result_is_dict_of_parsedfield():
    result: ParseResult = {
        "gross_salary_inr": high(3500000.0, "hint"),
        "tds_inr": missing("tds_inr"),
    }
    assert result["gross_salary_inr"].value == 3500000.0
    assert result["tds_inr"].confidence == "missing"
