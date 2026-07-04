"""Tests for the agent loop, tool framework, and providers."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# BaseTool + ToolRegistry
# ---------------------------------------------------------------------------


from orchestrator.agent.tools import BaseTool, ToolRegistry, build_registry


class _DummyTool(BaseTool):
    name = "dummy_tool"
    description = "A dummy tool for testing"
    parameters = {"type": "object", "properties": {"x": {"type": "integer"}}}

    def execute(self, **kwargs: Any) -> str:
        return json.dumps({"result": kwargs.get("x", 0) * 2})


class _FailTool(BaseTool):
    name = "fail_tool"
    description = "Always fails"
    is_readonly = True

    def execute(self, **kwargs: Any) -> str:
        raise RuntimeError("boom")


class _UnavailableTool(BaseTool):
    name = "unavailable_tool"
    description = "Not available"

    def check_available(self) -> bool:
        return False


def test_tool_registry_register_and_execute():
    reg = ToolRegistry()
    tool = _DummyTool()
    reg.register(tool)
    assert "dummy_tool" in reg
    assert len(reg) == 1
    result = reg.execute("dummy_tool", {"x": 5})
    data = json.loads(result)
    assert data["result"] == 10


def test_tool_registry_duplicate_raises():
    reg = ToolRegistry()
    reg.register(_DummyTool())
    with pytest.raises(ValueError, match="already registered"):
        reg.register(_DummyTool())


def test_tool_registry_unknown_tool():
    reg = ToolRegistry()
    with pytest.raises(KeyError, match="Unknown tool"):
        reg.get("nope")


def test_tool_registry_execute_catches_errors():
    reg = ToolRegistry()
    reg.register(_FailTool())
    result = reg.execute("fail_tool", {})
    data = json.loads(result)
    assert data["status"] == "error"
    assert "boom" in data["error"]


def test_tool_registry_definitions_exclude_unavailable():
    reg = ToolRegistry()
    reg.register(_DummyTool())
    reg.register(_UnavailableTool())
    defs = reg.get_definitions()
    names = [d["function"]["name"] for d in defs]
    assert "dummy_tool" in names
    assert "unavailable_tool" not in names


def test_tool_to_openai_schema():
    tool = _DummyTool()
    schema = tool.to_openai_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "dummy_tool"
    assert "parameters" in schema["function"]


# ---------------------------------------------------------------------------
# ChatLLM (mocked)
# ---------------------------------------------------------------------------


from orchestrator.providers.chat import ChatLLM, LLMResponse, ToolCallRequest


def test_llm_response_dataclass():
    resp = LLMResponse(content="hello", tool_calls=[], usage={"total_tokens": 10})
    assert resp.content == "hello"
    assert resp.usage["total_tokens"] == 10


def test_tool_call_request_dataclass():
    tc = ToolCallRequest(id="call_1", name="my_tool", arguments={"x": 1})
    assert tc.name == "my_tool"
    assert tc.arguments == {"x": 1}


# ---------------------------------------------------------------------------
# AgentLoop (mocked LLM)
# ---------------------------------------------------------------------------


from orchestrator.agent.loop import AgentLoop, AgentResult


def _mock_llm(final_text: str = "final answer", tool_calls: list = None):
    """Create a mock ChatLLM that returns tool calls then text."""
    mock = MagicMock(spec=ChatLLM)

    responses = []
    if tool_calls:
        for tc in tool_calls:
            responses.append(LLMResponse(tool_calls=[tc]))
    responses.append(LLMResponse(content=final_text))

    mock.chat.side_effect = responses
    return mock


def test_agent_loop_simple():
    reg = ToolRegistry()
    reg.register(_DummyTool())
    llm = _mock_llm("done")

    loop = AgentLoop(llm=llm, registry=reg, system_prompt="test")
    result = loop.run("hello")

    assert isinstance(result, AgentResult)
    assert result.content == "done"
    assert result.tool_calls_made == 0


def test_agent_loop_with_tool_call():
    reg = ToolRegistry()
    reg.register(_DummyTool())
    tc = ToolCallRequest(id="c1", name="dummy_tool", arguments={"x": 7})
    llm = _mock_llm("result is 14", tool_calls=[tc])

    loop = AgentLoop(llm=llm, registry=reg, system_prompt="test")
    result = loop.run("compute")

    assert result.content == "result is 14"
    assert result.tool_calls_made == 1


def test_agent_loop_cancel():
    reg = ToolRegistry()
    llm = MagicMock(spec=ChatLLM)
    llm.chat.return_value = LLMResponse(content="ok")

    loop = AgentLoop(llm=llm, registry=reg, system_prompt="test")
    loop.cancel()
    result = loop.run("hello")
    assert "cancelled" in result.content


# ---------------------------------------------------------------------------
# Build registry (auto-discovery)
# ---------------------------------------------------------------------------


def test_build_registry_finds_tools():
    reg = build_registry()
    assert len(reg) > 0
    # Should find at least the core tools.
    names = reg.list_names()
    assert "run_backtest" in names
    assert "create_hypothesis" in names
    assert "web_search" in names


def test_build_registry_with_extra():
    reg = build_registry(extra_tools=[_DummyTool()])
    assert "dummy_tool" in reg


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


from orchestrator.agent.prompt import build_system_prompt


def test_build_system_prompt():
    reg = build_registry()
    prompt = build_system_prompt(reg)
    assert "trading research agent" in prompt.lower()
    assert str(len(reg)) in prompt
