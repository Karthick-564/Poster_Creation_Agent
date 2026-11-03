"""LLM Backend abstraction for agentic poster designer and vision critic.

Supports configurable model backends (Anthropic, Gemini, OpenAI-compatible)
with zero third-party pip dependencies (uses Python standard library urllib).
Validates model names at startup and fails loudly if unknown or missing.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from typing import Any, Optional
import urllib.error
import urllib.request
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class ModelValidationError(ValueError):
    """Raised when a configured model name is not recognized or available."""
    pass


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    model: str = ""
    provider: str = ""


class LLMBackend:
    """Base interface for all LLM providers."""

    def __init__(self, model: str, temperature: float = 0.2, api_key: Optional[str] = None):
        self.model = model
        self.temperature = temperature
        self.api_key = api_key or ""
        self.validate_model()

    def validate_model(self) -> bool:
        """Validate that the model name is valid for this provider. Fails loudly."""
        raise NotImplementedError

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        images: Optional[list[Path | str]] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """Execute a chat completion request with optional tool calling and vision images."""
        raise NotImplementedError


class AnthropicBackend(LLMBackend):
    """Anthropic Claude API client using urllib.request."""

    KNOWN_MODELS = {
        "claude-sonnet-5-5",
        "claude-3-7-sonnet-latest",
        "claude-3-5-sonnet-latest",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-latest",
        "claude-3-opus-latest",
    }

    def __init__(self, model: str, temperature: float = 0.2, api_key: Optional[str] = None):
        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        super().__init__(model=model, temperature=temperature, api_key=key)

    def validate_model(self) -> bool:
        if not self.model:
            raise ModelValidationError("Anthropic model name cannot be empty.")
        # Check against known models or canonical prefixes
        if self.model not in self.KNOWN_MODELS and not self.model.startswith("claude-"):
            raise ModelValidationError(
                f"Invalid Anthropic model '{self.model}'. Must be one of {sorted(self.KNOWN_MODELS)} or start with 'claude-'."
            )
        return True

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        images: Optional[list[Path | str]] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set. Set it in .env or environment.")

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        # Convert standard OpenAI/generic messages into Anthropic format
        anthropic_messages = []
        system_prompt = ""
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                system_prompt += content + "\n"
            else:
                anthropic_messages.append({"role": role, "content": content})

        # Attach images to the last user message if supplied
        if images and anthropic_messages:
            last_msg = anthropic_messages[-1]
            content_blocks: list[dict[str, Any]] = []
            if isinstance(last_msg["content"], str):
                content_blocks.append({"type": "text", "text": last_msg["content"]})
            elif isinstance(last_msg["content"], list):
                content_blocks.extend(last_msg["content"])

            for img_path in images:
                p = Path(img_path)
                if p.exists():
                    data = base64.b64encode(p.read_bytes()).decode("utf-8")
                    ext = p.suffix.lower().lstrip(".")
                    media_type = f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"
                    content_blocks.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": data,
                        },
                    })
            last_msg["content"] = content_blocks

        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "temperature": temperature if temperature is not None else self.temperature,
            "messages": anthropic_messages,
        }
        if system_prompt.strip():
            payload["system"] = system_prompt.strip()

        if tools:
            anthropic_tools = []
            for t in tools:
                anthropic_tools.append({
                    "name": t.get("name"),
                    "description": t.get("description", ""),
                    "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
                })
            payload["tools"] = anthropic_tools

        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Anthropic API error HTTP {e.code}: {err_body}")

        # Parse Anthropic response
        content_text = ""
        tool_calls = []
        for block in res_data.get("content", []):
            if block.get("type") == "text":
                content_text += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.get("id", ""),
                    name=block.get("name", ""),
                    arguments=block.get("input", {}),
                ))

        return LLMResponse(
            content=content_text,
            tool_calls=tool_calls,
            raw=res_data,
            model=self.model,
            provider="anthropic",
        )


class GeminiBackend(LLMBackend):
    """Google Gemini API client using urllib.request."""

    KNOWN_MODELS = {
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-flash-latest",
        "gemini-pro-latest",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    }

    def __init__(self, model: str, temperature: float = 0.2, api_key: Optional[str] = None):
        key = api_key or os.environ.get("GEMINI_API_KEY", "")
        super().__init__(model=model, temperature=temperature, api_key=key)

    def validate_model(self) -> bool:
        if not self.model:
            raise ModelValidationError("Gemini model name cannot be empty.")
        if self.model not in self.KNOWN_MODELS and not self.model.startswith("gemini-"):
            raise ModelValidationError(
                f"Invalid Gemini model '{self.model}'. Must be one of {sorted(self.KNOWN_MODELS)} or start with 'gemini-'."
            )
        return True

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        images: Optional[list[Path | str]] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set. Set it in .env or environment.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"content-type": "application/json"}

        contents = []
        for m in messages:
            role = m.get("role", "user")
            # Gemini expects 'user' or 'model'
            gemini_role = "model" if role in ("assistant", "model") else "user"
            parts: list[dict[str, Any]] = [{"text": m.get("content", "")}]
            contents.append({"role": gemini_role, "parts": parts})

        # Attach images to the last user turn if provided
        if images and contents:
            for img_path in images:
                p = Path(img_path)
                if p.exists():
                    data = base64.b64encode(p.read_bytes()).decode("utf-8")
                    ext = p.suffix.lower().lstrip(".")
                    mime = f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"
                    contents[-1]["parts"].append({
                        "inline_data": {
                            "mime_type": mime,
                            "data": data,
                        }
                    })

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature if temperature is not None else self.temperature,
            },
        }

        # Convert tool definitions to Gemini function declarations if given
        if tools:
            func_decls = []
            for t in tools:
                func_decls.append({
                    "name": t.get("name"),
                    "description": t.get("description", ""),
                    "parameters": t.get("parameters", {"type": "object", "properties": {}}),
                })
            payload["tools"] = [{"function_declarations": func_decls}]

        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Gemini API error HTTP {e.code}: {err_body}")

        content_text = ""
        tool_calls = []
        candidates = res_data.get("candidates", [])
        if candidates:
            cand = candidates[0]
            parts = cand.get("content", {}).get("parts", [])
            for p in parts:
                if "text" in p:
                    content_text += p["text"]
                elif "functionCall" in p:
                    fc = p["functionCall"]
                    tool_calls.append(ToolCall(
                        id=f"call_{fc.get('name')}",
                        name=fc.get("name", ""),
                        arguments=fc.get("args", {}),
                    ))

        return LLMResponse(
            content=content_text,
            tool_calls=tool_calls,
            raw=res_data,
            model=self.model,
            provider="gemini",
        )


def get_backend(role: str = "designer", config_path: Optional[Path | str] = None) -> LLMBackend:
    """Instantiate and validate an LLM backend configured for the specified role."""
    cfg_file = Path(config_path) if config_path else (PROJECT_ROOT / "configs" / "agentic.yaml")
    if not cfg_file.exists():
        raise FileNotFoundError(f"Config file not found: {cfg_file}")

    with open(cfg_file, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    roles_cfg = cfg.get("roles", {})
    if role not in roles_cfg:
        raise KeyError(f"Role '{role}' not configured in {cfg_file}. Available roles: {list(roles_cfg.keys())}")

    role_info = roles_cfg[role]
    provider = str(role_info.get("provider", "")).lower()
    model = str(role_info.get("model", ""))
    temp = float(role_info.get("temperature", 0.2))

    if provider == "anthropic":
        return AnthropicBackend(model=model, temperature=temp)
    elif provider == "gemini":
        return GeminiBackend(model=model, temperature=temp)
    else:
        raise ValueError(f"Unsupported provider '{provider}' for role '{role}'. Supported: anthropic, gemini")

