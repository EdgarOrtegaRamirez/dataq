# DataQ — AI Agent Notes

## Project Overview
Data quality profiling and validation CLI for CSV and JSON datasets. Detects missing values, outliers, duplicates, and computes quality scores across completeness, validity, and consistency dimensions.

## Architecture
- `src/dataq/profiler.py` — Core profiling engine
- `src/dataq/cli.py` — Click CLI with profile command
- `src/dataq/models.py` — Pydantic models and dataclasses
- `tests/` — Unit and integration tests

## Commands
```bash
dataq profile data.csv                    # Default table output
dataq profile data.csv --format json      # JSON output
dataq profile data.csv --format md        # Markdown report
dataq profile data.csv -o report.md       # Save to file
```

## Key Design Decisions
- IQR method for outlier detection
- Weighted scoring: completeness 40%, validity 35%, consistency 25%
- Exit codes: 0 (good), 1 (needs improvement), 2 (poor) — CI/CD friendly
- Supports CSV, JSON, JSONL via file extension detection
- Zero external API dependencies — fully offline

## Adding Features
1. Add new quality check rules to `profiler.py`
2. Update issue severity logic
3. Add tests covering the new rule
4. Update README.md documentation
