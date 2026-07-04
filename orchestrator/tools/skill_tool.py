"""Skill tools — load and save reusable trading skill documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..agent.tools import BaseTool

_SKILLS_DIR = Path(__file__).parent.parent / "skills" / "bundled"


class LoadSkillTool(BaseTool):
    name = "load_skill"
    description = "Load a skill document by name from the bundled skills directory."
    is_readonly = True
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill name (filename without .md)"},
        },
        "required": ["name"],
    }

    def execute(self, **kwargs: Any) -> str:
        name = kwargs.get("name", "")
        skill_path = _SKILLS_DIR / f"{name}.md"
        if not skill_path.exists():
            # Try without extension.
            skill_path = _SKILLS_DIR / name
        if not skill_path.exists():
            return json.dumps({
                "status": "error",
                "error": f"Skill {name!r} not found in {_SKILLS_DIR}",
                "available": [p.stem for p in _SKILLS_DIR.glob("*.md")],
            })
        content = skill_path.read_text(encoding="utf-8")
        return json.dumps({"status": "ok", "name": name, "content": content[:10000]})


class SaveSkillTool(BaseTool):
    name = "save_skill"
    description = "Save a skill document to the bundled skills directory."
    is_readonly = False
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill name (filename without .md)"},
            "content": {"type": "string", "description": "Markdown content of the skill"},
        },
        "required": ["name", "content"],
    }

    def execute(self, **kwargs: Any) -> str:
        name = kwargs.get("name", "")
        content = kwargs.get("content", "")
        _SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        skill_path = _SKILLS_DIR / f"{name}.md"
        skill_path.write_text(content, encoding="utf-8")
        return json.dumps({"status": "ok", "path": str(skill_path)})
