"""JSON-RPC MCP frontend for the v2 poster core.

The CLI is the batch frontend; this server is the interactive frontend. Both
call the same ``Pipeline``. Tool calls only select inputs and budgets -- the
deterministic gates remain the delivery authority.

Run with::

    python -m poster_agent.mcp.v2_server
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from poster_agent.ingestion.extractor import BriefExtractor
from poster_agent.v2.assets import ComfyUIAssetBroker, MockAssetBroker
from poster_agent.v2.brand import get_brand, load_brand_contracts, resolve_format
from poster_agent.v2.composer import MockRenderer, VectorCraftComposer
from poster_agent.v2.pipeline import Pipeline
from poster_agent.v2.planner import KCTPlanner
from poster_agent.v2.reviewer import StaticReviewer


class V2PosterMCPServer:
    """Dependency-free MCP server exposing the v2 pipeline as tools."""

    def __init__(self, project_root: str | Path | None = None, session_id: str = "v2"):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.session_id = session_id
        self.tool_call_history: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Tool definitions
    # ------------------------------------------------------------------
    def get_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "run_poster",
                "description": (
                    "Run the full v2 pipeline for one brief: plan candidates, resolve "
                    "assets, compose, run deterministic gates, and optionally review. "
                    "Returns the audit summary and the winning raster path."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "brief_text": {"type": "string", "description": "Inline brief text"},
                        "brief_file": {"type": "string", "description": "Path to a brief file"},
                        "school": {"type": "string", "default": "KCT"},
                        "format_name": {"type": "string", "default": "story"},
                        "mode": {"type": "string", "enum": ["mock", "live"], "default": "mock"},
                        "output_dir": {"type": "string", "default": "runs/v2_mcp"},
                        "endpoint": {
                            "type": "string",
                            "description": "ComfyUI endpoint for live mode",
                            "default": "http://127.0.0.1:8188",
                        },
                        "allow_placeholder_logo": {"type": "boolean", "default": True},
                        "review_score": {
                            "type": "number",
                            "description": "Optional static review score for offline tests",
                        },
                        "max_candidates": {"type": "integer", "minimum": 1},
                        "include_spec": {"type": "boolean", "default": False},
                    },
                    "anyOf": [
                        {"required": ["brief_text"]},
                        {"required": ["brief_file"]},
                    ],
                },
            },
            {
                "name": "plan_poster",
                "description": "Return ranked layout candidates without generating assets or rendering.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "brief_text": {"type": "string"},
                        "brief_file": {"type": "string"},
                        "school": {"type": "string", "default": "KCT"},
                        "format_name": {"type": "string", "default": "story"},
                    },
                    "anyOf": [
                        {"required": ["brief_text"]},
                        {"required": ["brief_file"]},
                    ],
                },
            },
            {
                "name": "get_brand_contract",
                "description": "Return the deterministic brand contract for one school.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"school": {"type": "string", "default": "KCT"}},
                },
            },
            {
                "name": "list_schools",
                "description": "List the schools that have a v2 brand contract.",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------
    def run_poster(
        self,
        brief_text: str | None = None,
        brief_file: str | None = None,
        school: str = "KCT",
        format_name: str = "story",
        mode: str = "mock",
        output_dir: str = "runs/v2_mcp",
        endpoint: str = "http://127.0.0.1:8188",
        allow_placeholder_logo: bool = True,
        review_score: float | None = None,
        max_candidates: int | None = None,
        include_spec: bool = False,
    ) -> dict[str, Any]:
        try:
            text = self._read_brief(brief_text, brief_file)
            out = self._resolve_path(output_dir)
            if mode == "live":
                broker = ComfyUIAssetBroker(
                    out / "assets",
                    endpoint=endpoint,
                    allow_placeholder_logo=allow_placeholder_logo,
                )
                composer = VectorCraftComposer()
            elif mode == "mock":
                broker = MockAssetBroker(out / "assets", allow_placeholder_logo=allow_placeholder_logo)
                composer = MockRenderer()
            else:
                return {"error": f"InvalidArgumentsError: unknown mode {mode!r}"}

            reviewer = StaticReviewer(score=review_score) if review_score is not None else None
            pipeline = Pipeline(broker=broker, renderer=composer, reviewer=reviewer)
            result = pipeline.run(
                brief_text=text,
                school_id=school,
                format_name=format_name,
                output_dir=out,
                allow_placeholder_logo=allow_placeholder_logo,
                max_candidates=max_candidates,
            )
        except Exception as exc:
            return {"error": f"ToolExecutionError: {exc}"}

        payload: dict[str, Any] = {
            "success": result.success,
            "message": result.message,
            "school": result.school_id,
            "candidate": result.spec.candidate_id,
            "format": {
                "width": result.spec.format.width,
                "height": result.spec.format.height,
                "dpi": result.spec.format.dpi,
            },
            "output_path": result.output_path,
            "gates": {
                "passed": result.gates.passed,
                "blocking": [self._issue(i) for i in result.gates.blocking],
                "warnings": [self._issue(i) for i in result.gates.warnings],
                "checks": result.gates.checks,
            },
            "attempts": [a.model_dump() for a in result.attempts],
            "review": result.review.model_dump() if result.review else None,
        }
        if include_spec:
            payload["spec"] = result.spec.model_dump()
        return payload

    def plan_poster(
        self,
        brief_text: str | None = None,
        brief_file: str | None = None,
        school: str = "KCT",
        format_name: str = "story",
    ) -> dict[str, Any]:
        try:
            brand = get_brand(school, self.project_root / "configs" / "brand_contracts.yaml")
            fmt = resolve_format(brand, format_name)
            brief = BriefExtractor().extract(self._read_brief(brief_text, brief_file))
            planner = KCTPlanner()
            candidates = planner.plan_candidates(brief, brand, fmt)
        except Exception as exc:
            return {"error": f"ToolExecutionError: {exc}"}

        return {
            "school": brand.school_id,
            "format": {"width": fmt.width, "height": fmt.height, "dpi": fmt.dpi},
            "candidates": [
                {
                    "id": spec.candidate_id,
                    "score": round(planner.score(spec, brand, brief), 2),
                    "text_blocks": len(spec.text_blocks),
                    "hero": spec.image("hero").box.model_dump() if spec.image("hero") else None,
                    "qr": spec.qr is not None,
                    "description": spec.design_notes,
                }
                for spec in candidates
            ],
        }

    def get_brand_contract(self, school: str = "KCT") -> dict[str, Any]:
        try:
            brand = get_brand(school, self.project_root / "configs" / "brand_contracts.yaml")
        except Exception as exc:
            return {"error": f"ToolExecutionError: {exc}"}
        return brand.model_dump()

    def list_schools(self) -> dict[str, Any]:
        try:
            contracts = load_brand_contracts(self.project_root / "configs" / "brand_contracts.yaml")
        except Exception as exc:
            return {"error": f"ToolExecutionError: {exc}"}
        return {
            "schools": [
                {"id": key, "name": contract.name, "formats": sorted(contract.formats)}
                for key, contract in sorted(contracts.items())
            ]
        }

    # ------------------------------------------------------------------
    # Dispatch and JSON-RPC
    # ------------------------------------------------------------------
    def dispatch_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.tool_call_history.append({"name": name, "arguments": arguments, "time": time.time()})
        method = getattr(self, name, None)
        if method is None or name.startswith("_") or name in {
            "dispatch_tool",
            "handle_message",
            "run_stdio",
            "get_tool_definitions",
        }:
            return {"error": f"ToolNotFound: Unknown tool {name!r}"}
        try:
            return method(**arguments)
        except TypeError as exc:
            return {"error": f"InvalidArgumentsError: {exc}"}
        except Exception as exc:
            return {"error": f"ToolExecutionError: {exc}"}

    def handle_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        msg_id = message.get("id")
        method = message.get("method")
        params = message.get("params", {})

        if msg_id is None:
            return None

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "poster-v2-mcp", "version": "0.1.0"},
                },
            }
        if method == "ping":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": self.get_tool_definitions()},
            }
        if method == "tools/call":
            result = self.dispatch_tool(params.get("name", ""), params.get("arguments", {}))
            is_error = isinstance(result, dict) and "error" in result
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
                    "isError": is_error,
                },
            }
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method {method!r} not found"},
        }

    def run_stdio(self) -> None:
        """Run a line-delimited JSON-RPC loop, with Content-Length framing support."""
        sys.stderr.write(f"[Poster v2 MCP Server] Started (session: {self.session_id})\n")
        sys.stderr.flush()
        while True:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue
            if line.lower().startswith("content-length:"):
                try:
                    length = int(line.split(":", 1)[1].strip())
                    # Consume the blank separator line.
                    sys.stdin.readline()
                    line = sys.stdin.read(length)
                except (ValueError, OSError):
                    continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            response = self.handle_message(message)
            if response is None:
                continue
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _read_brief(self, brief_text: str | None, brief_file: str | None) -> str:
        if brief_text:
            return brief_text
        if not brief_file:
            raise ValueError("Provide brief_text or brief_file.")
        return self._resolve_path(brief_file).read_text(encoding="utf-8")

    def _resolve_path(self, path: str | Path) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.project_root / candidate
        return candidate

    @staticmethod
    def _issue(issue) -> dict[str, Any]:
        return {
            "code": issue.code,
            "stage": issue.stage,
            "severity": issue.severity,
            "message": issue.message,
            "target": issue.target,
            "fix_hint": issue.fix_hint,
            "measured": issue.measured,
        }


if __name__ == "__main__":
    V2PosterMCPServer().run_stdio()
