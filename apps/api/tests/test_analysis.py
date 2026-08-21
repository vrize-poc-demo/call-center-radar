import pytest

from app.analysis import parse_model_output


def test_parses_structured_analysis_output() -> None:
    analysis = parse_model_output(
        '{"intent":"Support","mood":"negative","resolution":"unresolved",'
        '"summary":"A summary","manager_brief":"A brief",'
        '"recommended_action":"Follow up","claims":[],"model_version":"test-v1"}'
    )

    assert analysis.resolution == "unresolved"
    assert analysis.model_version == "test-v1"


def test_rejects_malformed_structured_analysis_output() -> None:
    with pytest.raises(ValueError):
        parse_model_output('{"intent":"Support"}')
