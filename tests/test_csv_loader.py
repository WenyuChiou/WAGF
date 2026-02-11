
import importlib
import importlib.util
import pandas as pd


def test_csv_loader_module_exists():
    spec = importlib.util.find_spec("broker.utils.csv_loader")
    assert spec is not None, "broker.utils.csv_loader must exist"


def test_load_csv_with_mapping_basic(tmp_path):
    from broker.utils.csv_loader import load_csv_with_mapping

    csv_path = tmp_path / "sample.csv"
    csv_path.write_text("""A,B,C
1,2,3
4,5,6
""", encoding="utf-8")

    column_mapping = {
        "field1": {"col": "A"},
        "field2": {"col": "B"}
    }
    df = load_csv_with_mapping(str(csv_path), column_mapping, required_fields=["field1", "field2"])

    assert list(df.columns) == ["field1", "field2"]
    assert df.iloc[0].to_dict() == {"field1": 1, "field2": 2}


def test_load_csv_with_mapping_missing_column(tmp_path):
    from broker.utils.csv_loader import load_csv_with_mapping

    csv_path = tmp_path / "sample.csv"
    csv_path.write_text("""A,B
1,2
""", encoding="utf-8")

    column_mapping = {
        "field1": {"col": "A"},
        "field2": {"col": "Z"}
    }

    try:
        load_csv_with_mapping(str(csv_path), column_mapping, required_fields=["field1", "field2"])
    except ValueError as exc:
        assert "missing" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for missing column")
