import json
from pathlib import Path

import pytest

from app.ingestion.loaders import UnsupportedFormatError, load_csv_records, load_json_records, load_records


def test_load_json_records_from_array(tmp_path: Path):
    path = tmp_path / "records.json"
    path.write_text(json.dumps([{"a": 1}, {"a": 2}]))
    assert load_json_records(path) == [{"a": 1}, {"a": 2}]


def test_load_json_records_wraps_single_object(tmp_path: Path):
    path = tmp_path / "record.json"
    path.write_text(json.dumps({"a": 1}))
    assert load_json_records(path) == [{"a": 1}]


def test_load_json_records_rejects_non_list_shape(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps("not a record"))
    with pytest.raises(UnsupportedFormatError):
        load_json_records(path)


def test_load_csv_records(tmp_path: Path):
    path = tmp_path / "records.csv"
    path.write_text("comp_id,sf\nc_1,1000\nc_2,2000\n")
    rows = load_csv_records(path)
    assert rows == [{"comp_id": "c_1", "sf": "1000"}, {"comp_id": "c_2", "sf": "2000"}]


def test_load_records_dispatches_by_extension(tmp_path: Path):
    json_path = tmp_path / "records.json"
    json_path.write_text(json.dumps([{"a": 1}]))
    assert load_records(json_path) == [{"a": 1}]

    csv_path = tmp_path / "records.csv"
    csv_path.write_text("a\n1\n")
    assert load_records(csv_path) == [{"a": "1"}]


def test_load_records_raises_for_unsupported_extension(tmp_path: Path):
    path = tmp_path / "records.xml"
    path.write_text("<a/>")
    with pytest.raises(UnsupportedFormatError):
        load_records(path)
