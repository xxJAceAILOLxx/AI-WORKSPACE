"""Tool framework — BaseTool + ToolRegistry with auto-discovery.

Every tool is a :class:`BaseTool` subclass with a ``name``, JSON Schema
``parameters``, and an ``execute(**kwargs) -> str`` method that returns
a JSON string.  The :class:`ToolRegistry` collects them and exposes OpenAI
function-calling schemas for the LLM.

Auto-discovery scans ``orchestrator/tools/`` for modules containing
``BaseTool`` subclasses and registers them automatically.
"""

from __future__ import annotations

import importlib
import json
import logging
import pkgutil
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# BaseTool
# ---------------------------------------------------------------------------


class BaseTool:
    """Base class for all agent tools.

    Subclasses **must** set ``name`` and ``description`` as class
    attributes, and override :meth:`execute`.

    Attributes
    ----------
    name:
        Unique tool name sent to the LLM (snake_case).
    description:
        One-paragraph description shown to the LLM.
    parameters:
        JSON Schema dict describing the tool's parameters.
    is_readonly:
        If ``True`` (default), the tool can run in parallel with other
        readonly tools.  Set to ``False`` for tools with side effects.
    repeatable:
        If ``False`` (default), duplicate successful calls are suppressed.
    """

    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}
    is_readonly: bool = True
    repeatable: bool = False

    def execute(self, **kwargs: Any) -> str:
        """Run the tool and return a JSON string result.

        Must be overridden by subclasses.
        """
        raise NotImplementedError(f"Tool {self.name!r} did not implement execute()")

    def to_openai_schema(self) -> Dict[str, Any]:
        """Return the OpenAI function-calling schema for this tool."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def check_available(self) -> bool:
        """Return ``True`` if the tool is usable in the current environment.

        Override to gate on optional dependencies or env vars.
        """
        return True


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------


class ToolRegistry:
    """Collection of :class:`BaseTool` instances keyed by name."""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Add a tool.  Raises ``ValueError`` on duplicate names."""
        if tool.name in self._tools:
            existing = self._tools[tool.name]
            if existing is not tool:
                raise ValueError(
                    f"Tool {tool.name!r} already registered to {type(existing).__name__}"
                )
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        """Return the tool registered under ``name``.

        Raises ``KeyError`` if unknown.
        """
        try:
            return self._tools[name]
        except KeyError:
            raise KeyError(
                f"Unknown tool {name!r}. Available: {sorted(self._tools)}"
            ) from None

    def execute(self, name: str, params: Dict[str, Any]) -> str:
        """Execute a tool by name and return its JSON result string.

        Exceptions are caught and returned as ``{"status":"error",...}``.
        """
        try:
            tool = self.get(name)
            result = tool.execute(**params)
            return result
        except Exception as exc:
            logger.exception("Tool %s failed", name)
            return json.dumps({"status": "error", "tool": name, "error": str(exc)})

    def get_definitions(self) -> List[Dict[str, Any]]:
        """Return OpenAI function-calling schemas for all available tools."""
        return [
            tool.to_openai_schema()
            for tool in self._tools.values()
            if tool.check_available()
        ]

    def list_names(self) -> List[str]:
        """Return sorted list of registered tool names."""
        return sorted(self._tools)

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


# ---------------------------------------------------------------------------
# Auto-discovery
# ---------------------------------------------------------------------------


def build_registry(
    extra_tools: Optional[List[BaseTool]] = None,
    include: Optional[Set[str]] = None,
) -> ToolRegistry:
    """Build a :class:`ToolRegistry` by auto-discovering tool modules.

    Scans ``orchestrator/tools/`` for Python modules containing concrete
    :class:`BaseTool` subclasses (non-abstract, with a non-empty ``name``).

    Parameters
    ----------
    extra_tools:
        Additional tool instances to register after auto-discovery.
    include:
        If given, only register tools whose ``name`` is in this set.
    """
    registry = ToolRegistry()

    # Import the tools package to trigger discovery.
    try:
        import orchestrator.tools as tools_pkg
    except ImportError:
        logger.warning("orchestrator.tools package not found; registry is empty")
        if extra_tools:
            for tool in extra_tools:
                registry.register(tool)
        return registry

    package_path = getattr(tools_pkg, "__path__", None)
    if package_path is None:
        if extra_tools:
            for tool in extra_tools:
                registry.register(tool)
        return registry

    # Scan all modules in orchestrator/tools/.
    for importer, modname, ispkg in pkgutil.iter_modules(package_path):
        if modname.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"orchestrator.tools.{modname}")
        except Exception:
            logger.exception("Failed to import tool module %s", modname)
            continue

        # Find all BaseTool subclasses defined in this module.
        for attr_name in dir(mod):
            obj = getattr(mod, attr_name)
            if (
                isinstance(obj, type)
                and issubclass(obj, BaseTool)
                and obj is not BaseTool
                and obj.name
            ):
                if include is not None and obj.name not in include:
                    continue
                try:
                    instance = obj()
                    if instance.check_available():
                        registry.register(instance)
                except Exception:
                    logger.exception("Failed to instantiate tool %s", obj.__name__)

    # Register any manually provided tools.
    if extra_tools:
        for tool in extra_tools:
            registry.register(tool)

    logger.info(
        "Tool registry built: %d tools (%s)",
        len(registry),
        ", ".join(registry.list_names()),
    )
    return registry
