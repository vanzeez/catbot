"""The 6 tools: ToolSpec, OpenAI-style tool schemas, pydantic argument models (spec section 3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, create_model

from catbot.contracts import Tier


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    tier_hint: Tier | None
    args: dict[str, dict[str, Any]] = field(default_factory=dict)  # JSON-schema properties
    required: list[str] = field(default_factory=list)


TOOLS: dict[str, ToolSpec] = {
    s.name: s
    for s in [
        ToolSpec(
            "run_command",
            "Run ONE short shell command in the working directory and return its output.",
            None,
            {
                "command": {"type": "string", "description": "One short shell command."},
                "cwd": {"type": ["string", "null"], "description": "Directory; null = default."},
                "timeout_s": {"type": "integer", "minimum": 1, "maximum": 30, "default": 15},
            },
            ["command"],
        ),
        ToolSpec(
            "set_volume",
            "Change the system output volume: up, down, mute, unmute, or set to a level 0-100.",
            "T1",
            {
                "action": {"type": "string", "enum": ["up", "down", "mute", "unmute", "set"]},
                "level": {"type": ["integer", "null"], "minimum": 0, "maximum": 100},
            },
            ["action"],
        ),
        ToolSpec("lock_screen", "Lock the computer screen.", "T1"),
        ToolSpec("take_screenshot", "Capture the screen now and save it as an image.", "T0"),
        ToolSpec("read_screen", "Read the visible text on the screen (OCR).", "T0"),
        ToolSpec(
            "web_search",
            "Search the web and return the top results.",
            "T0",
            {"query": {"type": "string", "description": "Search query."}},
            ["query"],
        ),
    ]
}


def openai_tool_schema(spec: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.description,
            "parameters": {"type": "object", "properties": spec.args, "required": spec.required},
        },
    }


ALL_TOOL_SCHEMAS: list[dict[str, Any]] = [openai_tool_schema(s) for s in TOOLS.values()]


class _Args(BaseModel):
    model_config = ConfigDict(extra="ignore")


def _field(prop: dict[str, Any], required: bool) -> tuple[Any, Any]:
    types = prop.get("type", "string")
    types = types if isinstance(types, list) else [types]
    nullable = "null" in types
    base = next((t for t in types if t != "null"), "string")
    py: Any = {"string": str, "integer": int, "number": float, "boolean": bool}.get(base, Any)
    if "enum" in prop:
        py = Literal[tuple(prop["enum"])]  # type: ignore[valid-type]
    if nullable:
        py = py | None
    constraints = {k: prop[k] for k in ("minimum", "maximum") if k in prop}
    kw = {"ge": constraints.get("minimum"), "le": constraints.get("maximum")}
    kw = {k: v for k, v in kw.items() if v is not None}
    if base == "string" and required:
        kw["min_length"] = 1
    if required:
        return py, Field(..., **kw)
    return py, Field(prop.get("default"), **kw)


@cache
def args_model(name: str) -> type[BaseModel]:
    spec = TOOLS[name]
    fields = {k: _field(p, k in spec.required) for k, p in spec.args.items()}
    return create_model(f"{name}_args", __base__=_Args, **fields)


def validate_args(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Validated, defaults filled. Raises KeyError (unknown tool) or pydantic.ValidationError."""
    return args_model(name).model_validate(args).model_dump()
