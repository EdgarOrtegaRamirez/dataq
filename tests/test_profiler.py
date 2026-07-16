"""Tests for DataQ profiler engine."""

import csv
import json
import os
import tempfile
from pathlib import Path

import pytest

from dataq.models import ColumnType, Severity
from dataq.profiler import DataProfiler, _is_null_value


@pytest.fixture
def profiler():
    return DataProfiler()


@pytest.fixture
def clean_csv(profiler):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(['name', 'age', 'city'])
        writer.writerow(['Alice', '30', 'NYC'])
        writer.writerow(['Bob', '25', 'LA'])
        writer.writerow(['Carol', '35', 'CHI'])
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def dirty_csv(profiler):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(['name', 'age', 'salary'])
        writer.writerow(['Alice', '30', '50000'])
        writer.writerow(['Bob', '', '60000'])
        writer.writerow(['Carol', '35', '70000'])
        writer.writerow(['Dave', 'not_a_number', '80000'])
        writer.writerow(['Alice', '30', '50000'])  # duplicate
        writer.writerow(['Eve', '28', '45000'])
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def empty_column_csv(profiler):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(['name', 'empty_col'])
        writer.writerow(['Alice', ''])
        writer.writerow(['Bob', ''])
        writer.writerow(['Carol', ''])
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def json_data(profiler):
    data = [
        {"id": 1, "name": "Alice", "score": 95.5},
        {"id": 2, "name": "Bob", "score": 87.3},
        {"id": 3, "name": "Carol", "score": None},
    ]
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(data, f)
        path = f.name
    yield path
    os.unlink(path)


class TestIsNotNull:
    def test_none_is_null(self):
        assert _is_null_value(None) is True

    def test_empty_string_is_null(self):
        assert _is_null_value("") is True

    def test_null_string_is_null(self):
        assert _is_null_value("null") is True

    def test_none_string_is_null(self):
        assert _is_null_value("None") is True

    def test_na_string_is_null(self):
        assert _is_null_value("N/A") is True

    def test_nan_string_is_null(self):
        assert _is_null_value("nan") is True

    def test_whitespace_string_is_null(self):
        assert _is_null_value("   ") is True

    def test_valid_string_is_not_null(self):
        assert _is_null_value("hello") is False

    def test_number_is_not_null(self):
        assert _is_null_value(42) is False
        assert _is_null_value(3.14) is False

    def test_bool_is_not_null(self):
        assert _is_null_value(True) is False


class TestCleanDataset:
    def test_clean_csv_profiles(self, profiler, clean_csv):
        data = profiler.load_file(Path(clean_csv))
        profile = profiler.profile(data, file_path=clean_csv)

        assert profile.total_rows == 3
        assert profile.total_columns == 3
        assert profile.overall_score == 100.0
        assert profile.completeness_score == 100.0
        assert len(profile.issues) == 0
        assert len(profile.column_stats) == 3

    def test_age_column_detected_as_integer(self, profiler, clean_csv):
        data = profiler.load_file(Path(clean_csv))
        profile = profiler.profile(data, file_path=clean_csv)

        age_col = [cs for cs in profile.column_stats if cs.name == 'age'][0]
        assert age_col.column_type == ColumnType.INTEGER

    def test_name_column_detected_as_string(self, profiler, clean_csv):
        data = profiler.load_file(Path(clean_csv))
        profile = profiler.profile(data, file_path=clean_csv)

        name_col = [cs for cs in profile.column_stats if cs.name == 'name'][0]
        assert name_col.column_type == ColumnType.STRING


class TestDirtyDataset:
    def test_dirty_csv_has_issues(self, profiler, dirty_csv):
        data = profiler.load_file(Path(dirty_csv))
        profile = profiler.profile(data, file_path=dirty_csv)

        assert profile.total_rows == 6
        assert len(profile.issues) > 0
        assert profile.overall_score < 100.0

    def test_missing_age_issue(self, profiler, dirty_csv):
        data = profiler.load_file(Path(dirty_csv))
        profile = profiler.profile(data, file_path=dirty_csv)

        age_col = [cs for cs in profile.column_stats if cs.name == 'age'][0]
        assert age_col.missing_count == 1  # Bob's age is empty

    def test_duplicate_row_detected(self, profiler, dirty_csv):
        data = profiler.load_file(Path(dirty_csv))
        profile = profiler.profile(data, file_path=dirty_csv)

        duplicate_issues = [i for i in profile.issues if 'duplicate' in i.message.lower()]
        assert len(duplicate_issues) >= 1


class TestEmptyColumn:
    def test_empty_column_detected(self, profiler, empty_column_csv):
        data = profiler.load_file(Path(empty_column_csv))
        profile = profiler.profile(data, file_path=empty_column_csv)

        empty_issues = [i for i in profile.issues if 'empty' in i.message.lower()]
        assert len(empty_issues) >= 1

    def test_empty_column_has_critical_severity(self, profiler, empty_column_csv):
        data = profiler.load_file(Path(empty_column_csv))
        profile = profiler.profile(data, file_path=empty_column_csv)

        empty_issues = [i for i in profile.issues if 'empty' in i.message.lower()]
        assert any(i.severity == Severity.CRITICAL for i in empty_issues)


class TestJsonDataset:
    def test_json_loads_and_profiles(self, profiler, json_data):
        data = profiler.load_file(Path(json_data))
        profile = profiler.profile(data, file_path=json_data)

        assert profile.total_rows == 3
        assert profile.total_columns == 3

    def test_null_score_in_json(self, profiler, json_data):
        data = profiler.load_file(Path(json_data))
        profile = profiler.profile(data, file_path=json_data)

        score_col = [cs for cs in profile.column_stats if cs.name == 'score'][0]
        assert score_col.missing_count == 1


class TestNumericStats:
    def test_numeric_column_stats(self, profiler, clean_csv):
        data = profiler.load_file(Path(clean_csv))
        profile = profiler.profile(data, file_path=clean_csv)

        age_col = [cs for cs in profile.column_stats if cs.name == 'age'][0]
        assert age_col.mean == 30.0
        assert age_col.min_val == 25.0
        assert age_col.max_val == 35.0
        assert age_col.median == 30.0

    def test_numeric_stats_have_std_dev(self, profiler, clean_csv):
        data = profiler.load_file(Path(clean_csv))
        profile = profiler.profile(data, file_path=clean_csv)

        age_col = [cs for cs in profile.column_stats if cs.name == 'age'][0]
        assert age_col.std_dev is not None


class TestEmptyDataset:
    def test_empty_list_profiles(self, profiler):
        profile = profiler.profile([], file_path="empty.csv")

        assert profile.total_rows == 0
        assert profile.total_columns == 0
        assert profile.overall_score == 0.0


class TestOutlierDetection:
    def test_outliers_detected_in_data_with_extreme_value(self, profiler):
        # Create CSV with outlier
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'value'])
            writer.writerow([1, 10])
            writer.writerow([2, 11])
            writer.writerow([3, 10])
            writer.writerow([4, 12])
            writer.writerow([5, 11])
            writer.writerow([6, 10])
            writer.writerow([7, 11])
            writer.writerow([8, 10])
            writer.writerow([9, 11])
            writer.writerow([10, 9999])  # outlier
            path = f.name

        try:
            data = profiler.load_file(Path(path))
            profile = profiler.profile(data, file_path=path)

            value_col = [cs for cs in profile.column_stats if cs.name == 'value'][0]
            assert value_col.outliers > 0
        finally:
            os.unlink(path)


class TestFileTypeDetection:
    def test_jsonl_load(self, profiler):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('{"id": 1, "val": 100}\n')
            f.write('{"id": 2, "val": 200}\n')
            f.write('{"id": 3, "val": 300}\n')
            path = f.name

        try:
            data = profiler.load_file(Path(path))
            assert len(data) == 3
            assert data[0]["id"] == 1
        finally:
            os.unlink(path)

    def test_unsupported_extension(self, profiler):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlsx', delete=False) as f:
            f.write("not supported")
            path = f.name

        try:
            with pytest.raises(ValueError, match="Unsupported file format"):
                profiler.load_file(Path(path))
        finally:
            os.unlink(path)
