# DataQ — Data quality profiling and validation CLI

A CLI tool to analyze CSV and JSON datasets for data quality issues. Profile your data to detect missing values, outliers, duplicates, and more.

## Quick Start

```bash
pip install dataq
dataq profile data.csv
```

## Installation

```bash
pip install dataq
```

## Usage

### Profile a dataset

```bash
# Default table output
dataq profile data.csv

# JSON output
dataq profile data.csv --format json

# Markdown report
dataq profile data.csv --format markdown

# Save to file
dataq profile data.csv --output report.json --format json

# Custom completeness threshold
dataq profile data.csv --min-completeness 90
```

### Supported formats

- CSV files (`.csv`)
- JSON arrays or objects (`.json`)
- JSON Lines (`.jsonl`)

### Exit codes

- `0` — Quality score ≥ 80 (Good or better)
- `1` — Quality score 60–79 (Needs improvement)
- `2` — Quality score < 60 (Poor)

Useful for CI/CD pipelines to block low-quality data from entering your pipeline.

## What it detects

| Check | Description |
|-------|-------------|
| Missing values | Columns with null/empty values |
| Duplicate rows | Entire dataset duplicate detection |
| Empty columns | Columns with no valid values |
| Outliers | Numeric columns with IQR-based outliers |
| Low completeness | Columns below the completion threshold |
| High duplicate rate | Columns with excessive duplicate values |

## Score calculation

- **Completeness** (40%): Average column completion percentage
- **Validity** (35%): Deductions based on issue severity
- **Consistency** (25%): Penalizes type mismatches and outliers

## CI/CD Integration

```yaml
# GitHub Actions example
- name: Validate data quality
  run: |
    dataq profile data.csv --output report.json --format json
    dataq profile data.csv || echo "Data quality check failed!"
```

## License

MIT — see [LICENSE](LICENSE) for details.