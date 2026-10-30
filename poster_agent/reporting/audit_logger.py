"""Stage 8: Multi-Stage Audit Reporter (Generates Comprehensive Markdown and JSON Transparency Logs)."""
import json
import time
from pathlib import Path
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from poster_agent.ingestion.extractor import ExtractedBrief
from poster_agent.vision.art_measurer import MeasuredArtBundle
from poster_agent.checks.pixel_verifier import VerificationReport
from poster_agent.reviewer.probes import VisualAuditReport
from poster_agent.loop.typed_patcher import LoopSummary


class AuditStageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage_number: int
    stage_name: str
    status: str  # "PASSED", "WARNING", "FAILED"
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)


class MultiStageAuditReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    timestamp: str
    brief_title: str
    final_status: str
    stages: list[AuditStageRecord] = Field(default_factory=list)


class AuditLogger:
    """Compiles and exports the complete multi-stage execution report."""

    def __init__(self, run_id: str, output_dir: Path | str):
        self.run_id = run_id
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.stages: list[AuditStageRecord] = []

    def record_stage(self, stage_number: int, stage_name: str, status: str, summary: str, details: dict[str, Any]):
        self.stages.append(AuditStageRecord(
            stage_number=stage_number,
            stage_name=stage_name,
            status=status,
            summary=summary,
            details=details,
        ))

    def export_report(self, brief_title: str) -> tuple[Path, Path]:
        """Write both Markdown report and JSON trace to the run directory."""
        report = MultiStageAuditReport(
            run_id=self.run_id,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            brief_title=brief_title,
            final_status="PASSED" if all(s.status in ["PASSED", "WARNING"] for s in self.stages) else "FAILED",
            stages=self.stages,
        )

        json_path = self.output_dir / "audit_report.json"
        json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

        # Compile rich Markdown
        md_lines = [
            f"# Multi-Stage Poster Pipeline Audit Report",
            f"**Run ID**: `{self.run_id}` | **Date**: `{report.timestamp}` | **Status**: **{report.final_status}**",
            f"**Event Title**: {brief_title}",
            "",
            "---",
            "## Executive Stage Summary",
            "| Stage | Name | Status | Key Output / Decision |",
            "| :--- | :--- | :--- | :--- |",
        ]

        for s in self.stages:
            status_badge = "✅ PASSED" if s.status == "PASSED" else ("⚠️ WARNING" if s.status == "WARNING" else "❌ FAILED")
            md_lines.append(f"| Stage {s.stage_number} | **{s.stage_name}** | {status_badge} | {s.summary} |")

        md_lines.append("\n---\n")

        # Detail sections for each stage
        for s in self.stages:
            md_lines.append(f"### Stage {s.stage_number}: {s.stage_name}")
            md_lines.append(f"**Status**: {s.status} — *{s.summary}*\n")
            if s.details:
                md_lines.append("```json")
                md_lines.append(json.dumps(s.details, indent=2))
                md_lines.append("```\n")

        md_path = self.output_dir / "audit_report.md"
        md_path.write_text("\n".join(md_lines), encoding="utf-8")

        return md_path, json_path

