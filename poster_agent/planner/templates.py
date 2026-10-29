"""Template library loader and slot manager for planner."""
import json
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from poster_agent.spec.models import BBox


class TemplateSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slot_id: str
    role: str
    box: BBox
    char_budget: int = 0
    prominence: int = 3
    default_font_size_pt: int = 0


class LayoutTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    orientation: Literal["portrait", "landscape"]
    canvas_width_px: int
    canvas_height_px: int
    description: str
    text_safe_zones: list[BBox] = Field(default_factory=list)
    slots: list[TemplateSlot] = Field(default_factory=list)


class TemplateLibrary:
    """Manages loaded layout templates."""

    def __init__(self, templates_dir: Path | str | None = None):
        if templates_dir is None:
            default_dirs = [
                Path("templates"),
                Path(__file__).resolve().parent.parent.parent / "templates",
            ]
            for d in default_dirs:
                if d.exists():
                    templates_dir = d
                    break
            if templates_dir is None:
                templates_dir = Path("templates")

        self.templates_dir = Path(templates_dir)
        self.templates: dict[str, LayoutTemplate] = {}
        self.load_all()

    def load_all(self) -> None:
        if not self.templates_dir.exists():
            return
        for file in self.templates_dir.glob("*.json"):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                template = LayoutTemplate.model_validate(data)
                self.templates[template.id] = template
            except Exception as e:
                pass

    def get(self, template_id: str) -> LayoutTemplate | None:
        return self.templates.get(template_id)

    def list_all(self) -> list[LayoutTemplate]:
        return list(self.templates.values())

    def format_for_prompt(self) -> str:
        """Format templates list and slots into human-readable text for system prompt."""
        lines = ["AVAILABLE LAYOUT TEMPLATES:"]
        for t in self.templates.values():
            lines.append(f"\nTemplate ID: '{t.id}' - {t.name} ({t.orientation}, {t.canvas_width_px}x{t.canvas_height_px}px)")
            lines.append(f"Description: {t.description}")
            lines.append("Slots:")
            for s in t.slots:
                lines.append(
                    f"  - slot '{s.slot_id}': role={s.role}, box={s.box.to_list()} [y_min, x_min, y_max, x_max], "
                    f"char_budget={s.char_budget}, default_font_size={s.default_font_size_pt}pt"
                )
        return "\n".join(lines)


_LIBRARY_INSTANCE = None


def get_template_library() -> TemplateLibrary:
    global _LIBRARY_INSTANCE
    if _LIBRARY_INSTANCE is None:
        _LIBRARY_INSTANCE = TemplateLibrary()
    return _LIBRARY_INSTANCE

