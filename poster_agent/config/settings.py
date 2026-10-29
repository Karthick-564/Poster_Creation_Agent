"""Settings and configuration management."""
import os
from pathlib import Path
from typing import Any, Literal
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

load_dotenv()


class GroqConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = "openai/gpt-oss-120b"
    alt_model: str = "qwen/qwen3.8-27b"
    temperature: float = 0.2
    max_tokens: int = 4096
    timeout_seconds: int = 60

    @property
    def api_key(self) -> str:
        """Secrets loaded only from environment."""
        return os.environ.get("GROQ_API_KEY", "")


class IdeogramConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strategy: Literal["A", "B"] = "B"
    transport: Literal["comfyui", "http", "diffusers", "stub"] = "comfyui"
    endpoint: str = "http://127.0.0.1:8188"
    candidates_per_round: int = 2


class RepairConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_iterations: int = 4
    candidates: int = 2


class RendererConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dpi: int = 300
    default_width: int = 2480
    default_height: int = 3508


class ReviewerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str = "http://127.0.0.1:8080/v1"
    model: str = "LFM3-VL-2B"
    thinking_mode: bool = True


class ChecksConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ocr_engine: str = "paddleocr"
    min_contrast_ratio: float = 4.5
    min_font_pt: int = 14
    min_margin_px: int = 40
    max_allowed_overlap_px: int = 5


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    groq: GroqConfig = Field(default_factory=GroqConfig)
    ideogram: IdeogramConfig = Field(default_factory=IdeogramConfig)
    repair: RepairConfig = Field(default_factory=RepairConfig)
    renderer: RendererConfig = Field(default_factory=RendererConfig)
    reviewer: ReviewerConfig = Field(default_factory=ReviewerConfig)
    checks: ChecksConfig = Field(default_factory=ChecksConfig)


def load_config(config_path: str | Path | None = None) -> AppConfig:
    """Load configuration from YAML file and environment variables."""
    if config_path is None:
        # Default search paths
        search_paths = [
            Path("configs/default.yaml"),
            Path(__file__).resolve().parent.parent.parent / "configs" / "default.yaml",
        ]
        for p in search_paths:
            if p.exists():
                config_path = p
                break

    if config_path and Path(config_path).exists():
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return AppConfig.model_validate(data)

    return AppConfig()


_CONFIG_INSTANCE: AppConfig | None = None


def get_config(reload: bool = False, config_path: str | Path | None = None) -> AppConfig:
    """Get singleton configuration instance."""
    global _CONFIG_INSTANCE
    if _CONFIG_INSTANCE is None or reload:
        _CONFIG_INSTANCE = load_config(config_path)
    return _CONFIG_INSTANCE
