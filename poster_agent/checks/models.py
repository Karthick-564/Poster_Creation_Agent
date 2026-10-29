"""Check models and report types."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class CheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    check_name: str
    severity: Literal["blocking", "warning", "pass"]
    detail: str
    fix_hint: str | None = None


class CheckReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    passed: bool
    blocking_count: int
    warning_count: int
    results: list[CheckResult]
    summary: str

