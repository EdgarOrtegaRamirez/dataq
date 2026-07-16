"""Data profiler engine — analyze CSV/JSON datasets for quality metrics."""

from __future__ import annotations

import csv
import json
import io
import math
from datetime import datetime, date
from typing import Any, Optional
from pathlib import Path

import numpy as np

from dataq.models import (
    ColumnStats,
    ColumnType,
    DatasetProfile,
    Issue,
    QualityRule,
    Severity,
)


def _is_null_value(value: Any) -> bool:
    """Check if a value is null/missing."""
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        return stripped == "" or stripped.lower() in ("null", "none", "na", "n/a", "nan", "none")
    if isinstance(value, float) and math.isnan(value):
        return True
    return False


def _detect_column_type(values: list[Any]) -> ColumnType:
    """Detect the dominant type of a column."""
    non_null = [v for v in values if not _is_null_value(v)]
    if not non_null:
        return ColumnType.UNKNOWN

    int_count = 0
    float_count = 0
    bool_count = 0
    date_count = 0

    for v in non_null:
        if isinstance(v, bool):
            bool_count += 1
        elif isinstance(v, int):
            int_count += 1
        elif isinstance(v, float):
            float_count += 1
        elif isinstance(v, str):
            try:
                float(v)
                if "." in v:
                    float_count += 1
                else:
                    int_count += 1
            except ValueError:
                pass
                try:
                    datetime.fromisoformat(v)
                    date_count += 1
                except (ValueError, TypeError):
                    pass

    total = len(non_null)
    if bool_count > total * 0.5:
        return ColumnType.BOOLEAN
    if date_count > total * 0.5:
        return ColumnType.DATE
    if int_count > total * 0.5:
        return ColumnType.INTEGER
    if float_count > total * 0.5:
        return ColumnType.FLOAT
    return ColumnType.STRING


def _parse_numeric(value: Any) -> Optional[float]:
    """Try to parse a value as a number."""
    if _is_null_value(value):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _calculate_outliers(q1: float, q3: float, iqr: float) -> int:
    """Count outliers using IQR method."""
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    return 0  # Placeholder — actual counting done in profiler


class DataProfiler:
    """Profiles datasets for quality metrics."""

    def __init__(self, outlier_method: str = "iqr", completeness_threshold: float = 80.0) -> None:
        self.outlier_method = outlier_method
        self.completeness_threshold = completeness_threshold

    def _load_csv(self, path: Path) -> list[dict[str, Any]]:
        """Load a CSV file into a list of dicts."""
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            return list(reader)

    def _load_json(self, path: Path) -> list[dict[str, Any]]:
        """Load a JSON file into a list of dicts."""
        data = json.load(path.open("r", encoding="utf-8"))
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
        raise ValueError("JSON must be an array or object")

    def load_file(self, path: Path) -> list[dict[str, Any]]:
        """Load a CSV or JSON file."""
        suffix = path.suffix.lower()
        if suffix == ".csv":
            return self._load_csv(path)
        elif suffix in (".json", ".jsonl"):
            if suffix == ".jsonl":
                with path.open("r", encoding="utf-8") as f:
                    return [json.loads(line) for line in f if line.strip()]
            return self._load_json(path)
        else:
            raise ValueError(f"Unsupported file format: {suffix}. Use .csv or .json")

    def _get_column_values(self, data: list[dict[str, Any]], column: str) -> list[Any]:
        """Extract all values for a column."""
        return [row.get(column, None) for row in data]

    def _analyze_column(
        self,
        column: str,
        values: list[Any],
        total_rows: int,
    ) -> ColumnStats:
        """Analyze a single column and return statistics."""
        non_null = [v for v in values if not _is_null_value(v)]
        missing_count = sum(1 for v in values if _is_null_value(v))
        null_percentage = (missing_count / total_rows * 100) if total_rows > 0 else 0.0
        completion_percentage = ((total_rows - missing_count) / total_rows * 100) if total_rows > 0 else 100.0
        unique_count = len(set(str(v) for v in non_null))

        col_type = _detect_column_type(values)

        stats = ColumnStats(
            name=column,
            column_type=col_type,
            total_rows=total_rows,
            missing_count=missing_count,
            duplicate_count=0,
            unique_count=unique_count,
            null_percentage=round(null_percentage, 2),
            completion_percentage=round(completion_percentage, 2),
        )

        # String stats
        if col_type == ColumnType.STRING:
            string_vals = [str(v) for v in non_null]
            stats.longest_value = max(len(s) for s in string_vals) if string_vals else 0
            stats.shortest_value = min(len(s) for s in string_vals) if string_vals else 0
            from collections import Counter
            most_common = Counter(string_vals).most_common(1)
            if most_common:
                stats.most_common_value = most_common[0][0]
                stats.most_common_count = most_common[0][1]
            stats.duplicate_count = total_rows - unique_count

        # Numeric stats
        if col_type in (ColumnType.INTEGER, ColumnType.FLOAT):
            numeric_vals = []
            for v in values:
                n = _parse_numeric(v)
                if n is not None:
                    numeric_vals.append(n)

            if numeric_vals:
                arr = np.array(numeric_vals, dtype=np.float64)
                stats.mean = round(float(np.mean(arr)), 4)
                stats.std_dev = round(float(np.std(arr)), 4)
                stats.min_val = round(float(np.min(arr)), 4)
                stats.max_val = round(float(np.max(arr)), 4)
                stats.median = round(float(np.median(arr)), 4)
                stats.q1 = round(float(np.percentile(arr, 25)), 4)
                stats.q3 = round(float(np.percentile(arr, 75)), 4)

                # Calculate outliers using IQR
                iqr = stats.q3 - stats.q1
                if iqr > 0:
                    lower = stats.q1 - 1.5 * iqr
                    upper = stats.q3 + 1.5 * iqr
                    stats.outliers = int(np.sum((arr < lower) | (arr > upper)))
                else:
                    stats.outliers = 0

        # Add completeness issue if below threshold
        if completion_percentage < self.completeness_threshold:
            severity = Severity.CRITICAL if completion_percentage < 50 else (
                Severity.HIGH if completion_percentage < 70 else Severity.MEDIUM
            )
            stats.issues.append(Issue(
                rule_id=QualityRule.LOW_COMPLETENESS,
                severity=severity,
                message=f"Column has {null_percentage:.1f}% missing values ({missing_count}/{total_rows} rows)",
                column=column,
                detail=f"completion: {completion_percentage:.1f}%",
            ))

        # Add duplicate issue
        if stats.duplicate_count > total_rows * 0.1:
            stats.issues.append(Issue(
                rule_id=QualityRule.DUPLICATE_ROWS,
                severity=Severity.MEDIUM,
                message=f"Column has {stats.duplicate_count} duplicate values ({stats.duplicate_count/total_rows*100:.1f}%)",
                column=column,
            ))

        # Add empty column issue
        if missing_count == total_rows:
            stats.issues.append(Issue(
                rule_id=QualityRule.EMPTY_COLUMNS,
                severity=Severity.CRITICAL,
                message="Column is entirely empty",
                column=column,
            ))

        # Add outlier issue for numeric columns
        if col_type in (ColumnType.INTEGER, ColumnType.FLOAT) and stats.outliers > 0:
            pct = stats.outliers / len(numeric_vals) * 100 if numeric_vals else 0
            if pct > 5:
                stats.issues.append(Issue(
                    rule_id=QualityRule.OUTLIERS,
                    severity=Severity.HIGH,
                    message=f"Column has {stats.outliers} outlier values ({pct:.1f}%)",
                    column=column,
                    detail=f"range: [{stats.min_val}, {stats.max_val}], mean: {stats.mean}",
                ))

        return stats

    def profile(self, data: list[dict[str, Any]], file_path: str = "") -> DatasetProfile:
        """Profile a dataset and return quality metrics."""
        if not data:
            return DatasetProfile(
                file_path=file_path,
                total_rows=0,
                total_columns=0,
                overall_score=0.0,
                completeness_score=0.0,
                validity_score=0.0,
                consistency_score=0.0,
            )

        total_rows = len(data)
        all_columns = list(data[0].keys())
        column_stats: list[ColumnStats] = []
        issues: list[Issue] = []

        for col in all_columns:
            values = self._get_column_values(data, col)
            stats = self._analyze_column(col, values, total_rows)
            column_stats.append(stats)
            issues.extend(stats.issues)

        # Check overall duplicate rows
        unique_rows = len(set(tuple(sorted(row.items())) for row in data))
        dup_rows = total_rows - unique_rows
        if dup_rows > 0:
            pct = dup_rows / total_rows * 100
            issues.append(Issue(
                rule_id=QualityRule.DUPLICATE_ROWS,
                severity=Severity.HIGH if pct > 10 else Severity.MEDIUM,
                message=f"Dataset has {dup_rows} duplicate rows ({pct:.1f}%)",
                detail=f"unique rows: {unique_rows}/{total_rows}",
            ))

        # Check for empty columns
        for col in all_columns:
            values = self._get_column_values(data, col)
            if all(_is_null_value(v) for v in values):
                issues.append(Issue(
                    rule_id=QualityRule.EMPTY_COLUMNS,
                    severity=Severity.CRITICAL,
                    message=f"Column '{col}' is entirely empty",
                    column=col,
                ))

        # Calculate quality scores
        # Completeness: average of all column completion percentages
        completion_scores = [s.completion_percentage for s in column_stats]
        completeness_score = sum(completion_scores) / len(completion_scores) if completion_scores else 100.0

        # Validity: penalize for issues
        critical_issues = sum(1 for i in issues if i.severity == Severity.CRITICAL)
        high_issues = sum(1 for i in issues if i.severity == Severity.HIGH)
        medium_issues = sum(1 for i in issues if i.severity == Severity.MEDIUM)
        low_issues = sum(1 for i in issues if i.severity == Severity.LOW)

        validity_penalty = (
            critical_issues * 15 +
            high_issues * 10 +
            medium_issues * 5 +
            low_issues * 2
        )
        validity_score = max(0.0, 100.0 - validity_penalty)

        # Consistency: penalize for type mismatches and outliers
        type_mismatch = sum(1 for s in column_stats if s.column_type == ColumnType.UNKNOWN and s.total_rows > 0)
        total_outliers = sum(s.outliers for s in column_stats)
        consistency_penalty = (
            type_mismatch * 10 +
            min(total_outliers * 0.5, 30)
        )
        consistency_score = max(0.0, 100.0 - consistency_penalty)

        # Overall: weighted average
        overall_score = (
            completeness_score * 0.4 +
            validity_score * 0.35 +
            consistency_score * 0.25
        )

        return DatasetProfile(
            file_path=file_path,
            total_rows=total_rows,
            total_columns=len(all_columns),
            column_stats=column_stats,
            issues=issues,
            overall_score=round(overall_score, 1),
            completeness_score=round(completeness_score, 1),
            validity_score=round(validity_score, 1),
            consistency_score=round(consistency_score, 1),
        )
