"""CLI interface for DataQ — data quality profiling and validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from dataq import __version__
from dataq.models import ProfileResult
from dataq.profiler import DataProfiler


def _format_score(score: float) -> tuple[str, str]:
    """Return a color label for a quality score."""
    if score >= 90:
        return click.style("A", fg="green"), "Excellent"
    if score >= 80:
        return click.style("B", fg="green"), "Good"
    if score >= 70:
        return click.style("C", fg="yellow"), "Fair"
    if score >= 60:
        return click.style("C", fg="yellow"), "Needs improvement"
    return click.style("F", fg="red"), "Poor"


@click.group()
@click.version_option(version=__version__, prog_name="dataq")
def main() -> None:
    """Data quality profiling and validation CLI."""
    pass


@main.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False), required=True)
@click.option(
    "--output", "-o",
    type=click.Path(dir_okay=False, writable=True),
    help="Output file path (auto-detected as JSON for .json/.jsonl, Markdown for .md/.markdown)",
)
@click.option(
    "--format", "fmt",
    type=click.Choice(["json", "markdown", "table"], case_sensitive=False),
    default="table",
    help="Output format (default: table)",
)
@click.option(
    "--min-completeness",
    type=float,
    default=80.0,
    help="Completeness threshold in percent for flagging columns (default: 80)",
)
@click.pass_context
def profile(
    ctx: click.Context,
    file: str,
    output: str | None,
    fmt: str,
    min_completeness: float,
) -> None:
    """Profile a CSV or JSON dataset for data quality issues."""
    path = Path(file)

    try:
        profiler = DataProfiler(completeness_threshold=min_completeness)
        data = profiler.load_file(path)
        profile_result = profiler.profile(data, file_path=str(path))

        if fmt == "json":
            _output_json(profile_result, output)
        elif fmt == "markdown":
            _output_markdown(profile_result, output)
        else:
            _output_table(profile_result)

        # Exit with non-zero code if quality is poor
        if profile_result.overall_score < 60:
            sys.exit(2)
        elif profile_result.overall_score < 80:
            sys.exit(1)

    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        sys.exit(1)


def _dataset_profile_to_dict(profile) -> dict:
    """Convert a DatasetProfile dataclass to a dict for JSON serialization."""
    from dataclasses import asdict

    columns = []
    for cs in profile.column_stats:
        col = asdict(cs)
        columns.append(col)

    issues_list = []
    for issue in profile.issues:
        issues_list.append({
            "rule_id": issue.rule_id.value if hasattr(issue.rule_id, "value") else str(issue.rule_id),
            "severity": issue.severity.value if hasattr(issue.severity, "value") else str(issue.severity),
            "message": issue.message,
            "column": issue.column,
            "detail": issue.detail,
        })

    return {
        "file_path": profile.file_path,
        "total_rows": profile.total_rows,
        "total_columns": profile.total_columns,
        "overall_score": profile.overall_score,
        "completeness_score": profile.completeness_score,
        "validity_score": profile.validity_score,
        "consistency_score": profile.consistency_score,
        "columns": columns,
        "issues": issues_list,
    }


def _output_json(result: object, output: str | None) -> None:
    """Write profile as JSON."""
    if isinstance(result, dict):
        json_str = json.dumps(result, indent=2, default=str)
    else:
        data = _dataset_profile_to_dict(result)
        json_str = json.dumps(data, indent=2, default=str)

    if output:
        Path(output).write_text(json_str, encoding="utf-8")
        click.echo(f"Profile written to {output}")
    else:
        click.echo(json_str)


def _output_markdown(result: object, output: str | None) -> None:
    """Write profile as Markdown."""
    if hasattr(result, "model_dump"):
        data = result.model_dump()
    elif isinstance(result, dict):
        data = result
    else:
        data = {"file_path": str(result.file_path), "overall_score": result.overall_score}

    lines = [
        f"# Data Quality Report: {data.get('file_path', 'unknown')}",
        "",
        "## Summary",
        "",
        f"| Metric | Score |",
        f"|--------|-------|",
        f"| **Overall Quality** | {data.get('overall_score', 0):.1f}/100 |",
        f"| Completeness | {data.get('completeness_score', 0):.1f}/100 |",
        f"| Validity | {data.get('validity_score', 0):.1f}/100 |",
        f"| Consistency | {data.get('consistency_score', 0):.1f}/100 |",
        "",
        f"- **Rows**: {data.get('total_rows', 0)}",
        f"- **Columns**: {data.get('total_columns', 0)}",
    ]

    if data.get("issues"):
        lines.extend(["", "## Issues", ""])
        for issue in data["issues"]:
            severity = issue.get("severity", "")
            col = f" (column: {issue.get('column')})" if issue.get("column") else ""
            lines.append(f"- **[{severity.upper()}]**{col}: {issue.get('message', '')}")

    if data.get("columns"):
        lines.extend(["", "## Column Statistics", ""])
        lines.append("| Column | Type | Rows | Missing | Completion |")
        lines.append("|--------|------|------|---------|------------|")
        for col in data["columns"]:
            lines.append(
                f"| {col.get('name', '')} | {col.get('column_type', '')} | "
                f"{col.get('total_rows', 0)} | {col.get('missing_count', 0)} | "
                f"{col.get('completion_percentage', 0):.1f}% |"
            )

    markdown = "\n".join(lines)

    if output:
        Path(output).write_text(markdown, encoding="utf-8")
        click.echo(f"Profile written to {output}")
    else:
        click.echo(markdown)


def _output_table(result: object) -> None:
    """Print profile as a formatted table."""
    if hasattr(result, "overall_score"):
        overall = result.overall_score
    else:
        overall = result.get("overall_score", 0) if isinstance(result, dict) else 0

    grade, label = _format_score(overall)

    click.echo("")
    click.echo(click.style("=" * 60, fg="blue"))
    click.echo(click.style(f"  DataQ Quality Report: {getattr(result, 'file_path', 'dataset')}", fg="blue"))
    click.echo(click.style("=" * 60, fg="blue"))
    click.echo("")
    rows_label = click.style("  Rows", bold=True)
    click.echo(f"{rows_label}: {getattr(result, 'total_rows', 0)}")
    cols_label = click.style("  Columns", bold=True)
    click.echo(f"{cols_label}: {getattr(result, 'total_columns', 0)}")
    click.echo("")
    click.echo(click.style("  Quality Score:", bold=True))
    click.echo(f"  {grade}/100 — {label}")
    click.echo("")
    click.echo(click.style("  Scores:", bold=True))
    click.echo(f"    Completeness : {getattr(result, 'completeness_score', 0):.1f}/100")
    click.echo(f"    Validity     : {getattr(result, 'validity_score', 0):.1f}/100")
    click.echo(f"    Consistency  : {getattr(result, 'consistency_score', 0):.1f}/100")

    # Print issues
    issues = getattr(result, "issues", []) if hasattr(result, "issues") else result.get("issues", [])
    if issues:
        click.echo("")
        click.echo(click.style("  Issues:", bold=True))
        for issue in issues:
            sev = issue.get("severity", "") if isinstance(issue, dict) else (issue.severity.value if hasattr(issue.severity, "value") else str(issue.severity))
            msg = issue.get("message", "") if isinstance(issue, dict) else str(issue.message)
            col = issue.get("column", "") if isinstance(issue, dict) else getattr(issue, "column", "")
            sev_color = {
                "critical": "red", "high": "red", "medium": "yellow",
                "low": "cyan", "info": "blue",
            }.get(str(sev).lower(), "white")
            prefix = f"  [{sev.upper()}]" if col == "" else f"  [{sev.upper()}] ({col})"
            click.echo(click.style(prefix, fg=sev_color) + f" {msg}")

    click.echo("")


if __name__ == "__main__":
    main()