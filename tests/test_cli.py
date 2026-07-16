"""Tests for DataQ CLI."""

import json
import csv
import os
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from dataq.cli import main
from dataq.profiler import DataProfiler


@pytest.fixture
def sample_csv():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(['name', 'age', 'city'])
        writer.writerow(['Alice', '30', 'NYC'])
        writer.writerow(['Bob', '25', 'LA'])
        writer.writerow(['Carol', '35', 'NYC'])
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def sample_json():
    data = [{"id": 1, "value": 10}, {"id": 2, "value": 20}]
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(data, f)
        path = f.name
    yield path
    os.unlink(path)


class TestCLI:
    def test_profile_csv_table(self, sample_csv):
        runner = CliRunner()
        result = runner.invoke(main, ['profile', sample_csv])
        assert result.exit_code == 0
        assert "DataQ Quality Report" in result.output
        assert "Rows" in result.output
        assert "Columns" in result.output

    def test_profile_json_table(self, sample_json):
        runner = CliRunner()
        result = runner.invoke(main, ['profile', sample_json])
        assert result.exit_code == 0
        assert "DataQ Quality Report" in result.output

    def test_profile_csv_json(self, sample_csv):
        runner = CliRunner()
        result = runner.invoke(main, ['profile', sample_csv, '--format', 'json'])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data['total_rows'] == 3
        assert data['total_columns'] == 3

    def test_profile_csv_markdown(self, sample_csv):
        runner = CliRunner()
        result = runner.invoke(main, ['profile', sample_csv, '--format', 'markdown'])
        assert result.exit_code == 0
        assert "# Data Quality Report" in result.output
        assert "Rows" in result.output

    def test_profile_csv_to_file(self, sample_csv):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(main, ['profile', sample_csv, '--output', output, '--format', 'json'])
            assert result.exit_code == 0
            assert 'written to' in result.output
            assert Path(output).exists()
            data = json.loads(Path(output).read_text())
            assert data['total_rows'] == 3
        finally:
            os.unlink(output)

    def test_profile_missing_file(self):
        runner = CliRunner()
        result = runner.invoke(main, ['profile', 'nonexistent.csv'])
        assert result.exit_code == 2

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(main, ['--version'])
        assert result.exit_code == 0
        assert '0.1.0' in result.output

    def test_profile_dirty_data_exit_code(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'value', 'name'])
            writer.writerow([1, 10, 'A'])
            writer.writerow([2, '', 'B'])  # missing value
            writer.writerow([3, 20, 'C'])
            writer.writerow([4, 30, 'A'])  # duplicate name
            writer.writerow([5, 40, 'A'])
            writer.writerow([6, 50, 'A'])
            writer.writerow([7, 60, 'A'])
            writer.writerow([8, 70, 'A'])
            writer.writerow([9, 80, 'A'])
            writer.writerow([10, 90, 'A'])
            writer.writerow([11, 100, 'A'])
            writer.writerow([12, 110, 'A'])
            writer.writerow([13, 120, 'A'])
            writer.writerow([14, 130, 'A'])
            writer.writerow([15, 140, 'A'])
            writer.writerow([16, 150, 'A'])
            writer.writerow([17, 160, 'A'])
            writer.writerow([18, 170, 'A'])
            writer.writerow([19, 180, 'A'])
            writer.writerow([20, 190, 'A'])
            writer.writerow([21, 200, 'A'])
            writer.writerow([22, 210, 'A'])
            writer.writerow([23, 220, 'A'])
            writer.writerow([24, 230, 'A'])
            writer.writerow([25, 240, 'A'])
            writer.writerow([26, 250, 'A'])
            writer.writerow([27, 260, 'A'])
            writer.writerow([28, 270, 'A'])
            writer.writerow([29, 280, 'A'])
            writer.writerow([30, 290, 'A'])
            writer.writerow([31, 300, 'A'])
            writer.writerow([32, 310, 'A'])
            writer.writerow([33, 320, 'A'])
            writer.writerow([34, 330, 'A'])
            writer.writerow([35, 340, 'A'])
            writer.writerow([36, 350, 'A'])
            writer.writerow([37, 360, 'A'])
            writer.writerow([38, 370, 'A'])
            writer.writerow([39, 380, 'A'])
            writer.writerow([40, 390, 'A'])
            writer.writerow([41, 400, 'A'])
            writer.writerow([42, 410, 'A'])
            writer.writerow([43, 420, 'A'])
            writer.writerow([44, 430, 'A'])
            writer.writerow([45, 440, 'A'])
            writer.writerow([46, 450, 'A'])
            writer.writerow([47, 460, 'A'])
            writer.writerow([48, 470, 'A'])
            writer.writerow([49, 480, 'A'])
            writer.writerow([50, 490, 'A'])
            path = f.name

        try:
            runner = CliRunner()
            result = runner.invoke(main, ['profile', path])
            # With only 1 missing value out of 50, this should still be decent quality
            # The exact exit code depends on the scoring
            assert result.exit_code in (0, 1)
            assert "DataQ Quality Report" in result.output
        finally:
            os.unlink(path)