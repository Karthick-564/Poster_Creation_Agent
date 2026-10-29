"""Context loader: parses context.md and scans assets/ directory."""
import json
import re
from pathlib import Path
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class LogoRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file: str
    svg_file: str | None = None
    name: str
    min_width_px: int = 120
    min_height_px: int = 40
    clear_space_px: int = 20
    required: bool = False


class ContextBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    raw_markdown: str
    college_details: dict[str, str] = Field(default_factory=dict)
    clubs: list[dict[str, str]] = Field(default_factory=list)
    palette: list[str] = Field(default_factory=list)
    fonts: dict[str, str] = Field(default_factory=dict)
    brand_rules: list[str] = Field(default_factory=list)
    logo_rules: dict[str, LogoRule] = Field(default_factory=dict)
    asset_files: list[str] = Field(default_factory=list)

    def contains_verbatim(self, text: str) -> bool:
        """Check if text appears verbatim in raw markdown (case-sensitive or normalized)."""
        clean_text = text.strip()
        if not clean_text:
            return True
        return clean_text in self.raw_markdown


def parse_context_markdown(md_content: str) -> dict[str, Any]:
    """Extract structured elements from context markdown while preserving raw text."""
    college_details: dict[str, str] = {}
    clubs: list[dict[str, str]] = []
    palette: list[str] = []
    fonts: dict[str, str] = {}
    brand_rules: list[str] = []

    # Extract hex colors
    hex_colors = re.findall(r"#[0-9a-fA-F]{6}\b", md_content)
    # Deduplicate while preserving order, convert to uppercase
    seen = set()
    for hc in hex_colors:
        uhc = hc.upper()
        if uhc not in seen:
            seen.add(uhc)
            palette.append(uhc)

    # Extract bullet points under college details
    inst_match = re.search(r"## Institution Profile(.*?)(?=##|\Z)", md_content, re.DOTALL)
    if inst_match:
        for line in inst_match.group(1).splitlines():
            line = line.strip()
            if line.startswith("- **") and "**:" in line:
                key, val = line[4:].split("**:", 1)
                college_details[key.strip()] = val.strip()

    # Extract clubs
    club_match = re.search(r"## Associated Clubs & Societies(.*?)(?=##|\Z)", md_content, re.DOTALL)
    if club_match:
        for line in club_match.group(1).splitlines():
            line = line.strip()
            if line.startswith("- **") and "**:" in line:
                key, val = line[4:].split("**:", 1)
                clubs.append({"name": key.strip(), "description": val.strip()})

    # Extract fonts
    font_match = re.search(r"### Typography Rules(.*?)(?=###|##|\Z)", md_content, re.DOTALL)
    if font_match:
        for line in font_match.group(1).splitlines():
            line = line.strip()
            if line.startswith("- **") and "**:" in line:
                key, val = line[4:].split("**:", 1)
                fonts[key.strip()] = val.strip().strip("`")

    # Extract brand rules
    rules_match = re.search(r"### Brand Rules & Usage(.*?)(?=###|##|\Z)", md_content, re.DOTALL)
    if rules_match:
        for line in rules_match.group(1).splitlines():
            line = line.strip()
            if re.match(r"^\d+\.\s+\*\*", line):
                brand_rules.append(line)

    return {
        "college_details": college_details,
        "clubs": clubs,
        "palette": palette,
        "fonts": fonts,
        "brand_rules": brand_rules,
    }


def load_context(
    context_path: str | Path | None = None,
    assets_dir: str | Path | None = None,
) -> ContextBundle:
    """Load context.md and asset definitions."""
    if context_path is None:
        default_paths = [
            Path("context.md"),
            Path(__file__).resolve().parent.parent.parent / "context.md",
        ]
        for p in default_paths:
            if p.exists():
                context_path = p
                break

    if assets_dir is None:
        default_asset_dirs = [
            Path("assets"),
            Path(__file__).resolve().parent.parent.parent / "assets",
        ]
        for p in default_asset_dirs:
            if p.exists():
                assets_dir = p
                break

    raw_markdown = ""
    if context_path and Path(context_path).exists():
        with open(context_path, "r", encoding="utf-8") as f:
            raw_markdown = f.read()

    parsed = parse_context_markdown(raw_markdown)

    logo_rules: dict[str, LogoRule] = {}
    asset_files: list[str] = []

    if assets_dir and Path(assets_dir).exists():
        assets_path = Path(assets_dir)
        rules_file = assets_path / "rules.json"
        if rules_file.exists():
            with open(rules_file, "r", encoding="utf-8") as f:
                rules_data = json.load(f)
            for k, v in rules_data.items():
                logo_rules[k] = LogoRule.model_validate(v)

        for item in assets_path.iterdir():
            if item.is_file():
                asset_files.append(item.name)

    return ContextBundle(
        raw_markdown=raw_markdown,
        college_details=parsed["college_details"],
        clubs=parsed["clubs"],
        palette=parsed["palette"],
        fonts=parsed["fonts"],
        brand_rules=parsed["brand_rules"],
        logo_rules=logo_rules,
        asset_files=asset_files,
    )
