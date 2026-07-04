"""File read/write/edit tools for scaffolded signal engines."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..agent.tools import BaseTool


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read the contents of a file."
    is_readonly = True
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to read"},
        },
        "required": ["path"],
    }

    def execute(self, **kwargs: Any) -> str:
        path = kwargs.get("path", "")
        try:
            content = Path(path).read_text(encoding="utf-8")
            return json.dumps({"status": "ok", "path": path, "content": content[:50000]})
        except Exception as exc:
            return json.dumps({"status": "error", "error": str(exc)})


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Write content to a file (creates or overwrites)."
    is_readonly = False
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to write"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "required": ["path", "content"],
    }

    def execute(self, **kwargs: Any) -> str:
        path = kwargs.get("path", "")
        content = kwargs.get("content", "")
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return json.dumps({"status": "ok", "path": path, "bytes_written": len(content)})
        except Exception as exc:
            return json.dumps({"status": "error", "error": str(exc)})


class EditFileTool(BaseTool):
    name = "edit_file"
    description = "Replace an exact string in a file with new content."
    is_readonly = False
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"},
            "old_string": {"type": "string", "description": "Exact string to find"},
            "new_string": {"type": "string", "description": "Replacement string"},
        },
        "required": ["path", "old_string", "new_string"],
    }

    def execute(self, **kwargs: Any) -> str:
        path = kwargs.get("path", "")
        old = kwargs.get("old_string", "")
        new = kwargs.get("new_string", "")
        try:
            p = Path(path)
            content = p.read_text(encoding="utf-8")
            if old not in content:
                return json.dumps({"status": "error", "error": "old_string not found in file"})
            new_content = content.replace(old, new, 1)
            p.write_text(new_content, encoding="utf-8")
            return json.dumps({"status": "ok", "path": path, "replaced": True})
        except Exception as exc:
            return json.dumps({"status": "error", "error": str(exc)})


class ListDirectoryTool(BaseTool):
    name = "list_directory"
    description = "List files and subdirectories in a directory."
    is_readonly = True
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path (default: current dir)"},
        },
    }

    def execute(self, **kwargs: Any) -> str:
        path = kwargs.get("path", ".")
        try:
            entries = sorted(os.listdir(path))
            return json.dumps({"status": "ok", "path": path, "entries": entries[:200]})
        except Exception as exc:
            return json.dumps({"status": "error", "error": str(exc)})
