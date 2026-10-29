"""Comprehensive run logging: per-run folder, versioned specs, candidates, checks, decisions."""
import datetime
import json
import re
import shutil
from pathlib import Path
from typing import Any

from poster_agent.context.loader import ContextBundle
from poster_agent.spec.models import PosterSpec
from poster_agent.checks.models import CheckReport


def slugify(text: str, max_length: int = 32) -> str:
    """Generate filesystem-safe short slug from brief."""
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "_", s)
    return s[:max_length].strip("_") or "poster"


class RunLogger:
    """Manages recording of all artifacts, specs, candidates, and check logs for a run."""

    def __init__(self, requirements_text: str, base_dir: Path | str = "runs"):
        self.base_dir = Path(base_dir)
        self.requirements_text = requirements_text
        self.start_time = datetime.datetime.now()
        timestamp_str = self.start_time.strftime("%Y%m%d_%H%M%S")
        slug = slugify(requirements_text)
        self.run_dir = self.base_dir / f"{timestamp_str}_{slug}"
        self.run_dir.mkdir(parents=True, exist_ok=True)

        # Write initial requirements
        (self.run_dir / "requirements.txt").write_text(requirements_text, encoding="utf-8")

    def log_context(self, context: ContextBundle) -> None:
        (self.run_dir / "context_snapshot.md").write_text(context.raw_markdown, encoding="utf-8")

    def log_spec_version(self, spec: PosterSpec, version: int) -> Path:
        spec_path = self.run_dir / f"spec_v{version}.json"
        spec_path.write_text(spec.model_dump_json(indent=2), encoding="utf-8")
        return spec_path

    def get_iteration_dir(self, iteration: int) -> Path:
        it_dir = self.run_dir / f"iteration_{iteration}"
        it_dir.mkdir(parents=True, exist_ok=True)
        return it_dir

    def log_iteration(
        self,
        iteration: int,
        generator_payload: dict[str, Any],
        seed: int,
        candidates: list[tuple[int, Path, CheckReport]],
        decision_text: str,
    ) -> None:
        it_dir = self.get_iteration_dir(iteration)
        (it_dir / "generator_payload.json").write_text(
            json.dumps(generator_payload, indent=2), encoding="utf-8"
        )
        (it_dir / "seed.txt").write_text(str(seed), encoding="utf-8")

        # Copy candidate images into iteration folder if not already there
        check_reports_dict: dict[str, Any] = {}
        for cand_idx, img_path, report in candidates:
            if img_path.exists():
                dest_img = it_dir / f"candidate_{cand_idx}.png"
                if img_path.resolve() != dest_img.resolve():
                    shutil.copy2(img_path, dest_img)
            check_reports_dict[f"candidate_{cand_idx}"] = report.model_dump()

        (it_dir / "check_results.json").write_text(
            json.dumps(check_reports_dict, indent=2), encoding="utf-8"
        )
        (it_dir / "decision.txt").write_text(decision_text, encoding="utf-8")

    def finalize_run(
        self,
        status: str,
        best_png_path: Path | None,
        best_pdf_path: Path | None,
        final_spec: PosterSpec,
        iterations_used: int,
        reviewer_output: dict[str, Any] | None = None,
        repair_actions: list[str] | None = None,
    ) -> Path:
        duration_s = (datetime.datetime.now() - self.start_time).total_seconds()

        # Copy final PNG and PDF to root of run_dir
        final_png = self.run_dir / "final.png"
        if best_png_path and best_png_path.exists() and best_png_path.resolve() != final_png.resolve():
            shutil.copy2(best_png_path, final_png)

        final_pdf = self.run_dir / "final.pdf"
        if best_pdf_path and best_pdf_path.exists() and best_pdf_path.resolve() != final_pdf.resolve():
            shutil.copy2(best_pdf_path, final_pdf)

        (self.run_dir / "final_spec.json").write_text(
            final_spec.model_dump_json(indent=2), encoding="utf-8"
        )

        if reviewer_output is not None:
            (self.run_dir / "reviewer_output.json").write_text(
                json.dumps(reviewer_output, indent=2), encoding="utf-8"
            )

        summary = {
            "status": status,
            "iterations_used": iterations_used,
            "duration_seconds": round(duration_s, 2),
            "repair_actions_taken": repair_actions or [],
            "timestamp": self.start_time.isoformat(),
            "canvas_size": [final_spec.canvas_width_px, final_spec.canvas_height_px],
            "template_id": final_spec.template_id,
        }
        (self.run_dir / "run_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )

        return self.run_dir
