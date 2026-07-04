"""Tests for the Hypothesis Registry."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from orchestrator.hypotheses.models import Hypothesis, RunCard
from orchestrator.hypotheses.registry import HypothesisRegistry


def test_hypothesis_create_and_get(tmp_path):
    reg = HypothesisRegistry(store_dir=tmp_path)
    h = reg.create_hypothesis(
        title="IBS Edge",
        thesis="Low IBS predicts mean reversion",
        universe="SPY",
        signal_definition="IBS < 0.2",
    )
    assert h.title == "IBS Edge"
    assert h.status == "draft"
    assert len(h.hypothesis_id) == 12

    h2 = reg.get_hypothesis(h.hypothesis_id)
    assert h2 is not None
    assert h2.title == "IBS Edge"
    assert h2.thesis == "Low IBS predicts mean reversion"


def test_hypothesis_list_and_filter(tmp_path):
    reg = HypothesisRegistry(store_dir=tmp_path)
    h1 = reg.create_hypothesis(title="A")
    h2 = reg.create_hypothesis(title="B")
    h3 = reg.create_hypothesis(title="C")
    reg.update_hypothesis(h1.hypothesis_id, status="draft")
    reg.update_hypothesis(h2.hypothesis_id, status="active")
    reg.update_hypothesis(h3.hypothesis_id, status="draft")

    all_h = reg.list_hypotheses()
    assert len(all_h) == 3

    drafts = reg.list_hypotheses(status="draft")
    assert len(drafts) == 2


def test_hypothesis_update(tmp_path):
    reg = HypothesisRegistry(store_dir=tmp_path)
    h = reg.create_hypothesis(title="Test")
    h2 = reg.update_hypothesis(h.hypothesis_id, status="active", thesis="updated")
    assert h2.status == "active"
    assert h2.thesis == "updated"


def test_hypothesis_link_backtest(tmp_path):
    reg = HypothesisRegistry(store_dir=tmp_path)
    h = reg.create_hypothesis(title="Test")
    h2 = reg.link_backtest(
        h.hypothesis_id,
        run_dir="/tmp/run1",
        metrics={"profit_factor": 1.5, "sharpe": 1.2},
        notes="good run",
    )
    assert len(h2.run_cards) == 1
    assert h2.run_cards[0].metrics["profit_factor"] == 1.5


def test_hypothesis_invalidate(tmp_path):
    reg = HypothesisRegistry(store_dir=tmp_path)
    h = reg.create_hypothesis(title="Test", thesis="original")
    h2 = reg.invalidate_hypothesis(h.hypothesis_id, note="overfitting")
    assert h2.status == "rejected"
    assert "REJECTED" in h2.thesis


def test_hypothesis_search(tmp_path):
    reg = HypothesisRegistry(store_dir=tmp_path)
    reg.create_hypothesis(title="IBS Mean Reversion", thesis="uses IBS indicator")
    reg.create_hypothesis(title="Momentum Breakout", thesis="price momentum")
    results = reg.search_hypotheses("IBS")
    assert len(results) == 1
    assert results[0].title == "IBS Mean Reversion"


def test_hypothesis_serialization():
    h = Hypothesis(
        title="Test",
    thesis="thesis",
    universe="SPY",
    signal_definition="close > sma",
    run_cards=[RunCard(run_dir="/tmp", metrics={"sharpe": 1.0})],
    )
    d = h.to_dict()
    h2 = Hypothesis.from_dict(d)
    assert h2.title == "Test"
    assert len(h2.run_cards) == 1
    assert h2.run_cards[0].metrics["sharpe"] == 1.0


def test_hypothesis_get_nonexistent(tmp_path):
    reg = HypothesisRegistry(store_dir=tmp_path)
    assert reg.get_hypothesis("nonexistent") is None
