"""Provider payload contracts; no credentials, network access or model routing changes."""
from __future__ import annotations

from copy import deepcopy
import re


def normalize_effort(model: str | None, effort: str | None) -> str | None:
    name = (model or "").lower().split("/")[-1]
    value = (effort or "").strip().lower() or None
    if name.startswith("gpt-6") and value in {"none", "minimal"}:
        return "low"
    if name.startswith(("gpt-5.2", "gpt-5.4", "gpt-5.5", "gpt-5.6")) and value == "minimal":
        return "low"
    return value


def supports_sampling(model: str | None, effort: str | None = None) -> bool:
    name = (model or "").lower().split("/")[-1]
    if re.match(r"^o[1-9]([.\-]|$)", name) or name.startswith("gpt-6"):
        return False
    if name.startswith("gpt-5"):
        # Newer GPT-5 revisions accept sampling only with reasoning explicitly disabled.
        return bool(re.match(r"^gpt-5\.[1-9]", name)) and effort == "none"
    return True


def strict_response_format(schema: dict, name: str) -> dict | None:
    """Close typed objects recursively. Open maps cannot be closed without losing application data."""
    schema = deepcopy(schema)

    def visit(node):
        if isinstance(node, list):
            return all(visit(child) for child in node)
        if not isinstance(node, dict):
            return True
        node.pop("default", None)
        if node.get("type") == "object":
            if "properties" not in node or isinstance(node.get("additionalProperties"), dict):
                return False
            node["additionalProperties"] = False
            node["required"] = list(node["properties"])
        # Traverse schema nodes, not arbitrary string-valued examples/annotations.
        for key in ("$defs", "definitions", "properties"):
            if key in node and not all(visit(child) for child in node[key].values()):
                return False
        return all(visit(node[key]) for key in ("items", "anyOf", "oneOf", "allOf") if key in node)

    if not visit(schema):
        return None
    return {"type": "json_schema", "json_schema": {
        "name": re.sub(r"[^a-zA-Z0-9_-]", "_", name)[:64], "strict": True, "schema": schema,
    }}
