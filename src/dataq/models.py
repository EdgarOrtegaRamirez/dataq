"""Pydantic data models for data quality analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel


class ColumnType(str, Enum):
    """Detected column data type."""
    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"
    BOOLEAN = "boolean"
    DATE = "date"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    """Issue severity level."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class QualityRule(str, Enum):
    """Quality check rule identifier."""
    MISSING_VALUES = "missing_values"
    DUPLICATE_ROWS = "duplicate_rows"
    INVALID_VALUES = "invalid_values"
    EMPTY_COLUMNS = "empty_columns"
    OUTLIERS = "outliers"
    LOW_COMPLETENESS = "low_completeness"
    TYPE_MISMATCH = "type_mismatch"


@dataclass
class ColumnStats:
    """Statistics for a single column."""
    name: str
    column_type: ColumnType
    total_rows: int
    missing_count: int = 0
    duplicate_count: int = 0
    unique_count: int = 0
    null_percentage: float = 0.0
    completion_percentage: float = 100.0
    # Numeric stats
    mean: Optional[float] = None
    std_dev: Optional[float] = None
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    median: Optional[float] = None
    q1: Optional[float] = None
    q3: Optional[float] = None
    # String stats
    longest_value: int = 0
    shortest_value: int = 0
    most_common_value: str = ""
    most_common_count: int = 0
    outliers: int = 0
    issues: list[Issue] = field(default_factory=list)


@dataclass
class Issue:
    """A data quality issue found during analysis."""
    rule_id: QualityRule
    severity: Severity
    message: str
    column: Optional[str] = None
    row: Optional[int] = None
    detail: Optional[str] = None


@dataclass
class DatasetProfile:
    """Overall quality profile for a dataset."""
    file_path: str
    total_rows: int
    total_columns: int
    column_stats: list[ColumnStats] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    overall_score: float = 100.0
    completeness_score: float = 100.0
    validity_score: float = 100.0
    consistency_score: float = 100.0


class ProfileResult(BaseModel):
    """JSON-serializable profile result."""
    file_path: str
    total_rows: int
    total_columns: int
    overall_score: float
    completeness_score: float
    validity_score: float
    consistency_score: float
    columns: list[dict[str, Any]]
    issues: list[dict[str, Any]]
