"""Agent registry for the orchestration layer.

Each :class:`Agent` mirrors one entry in the vault ``agents.md`` note:
purpose, responsibilities, prompt template, references, and which
workflow stage owns it.  No external LLM calls are made here - the
templates are stored verbatim so they can be populated and printed by
the workflow.

Stage assignment follows the documented pipeline::

    research -> design -> backtest -> validate -> deploy -> monitor -> learn

* ``research``  -> Web Researcher
* ``design``    -> Strategy Architect
* ``backtest``  -> Backtest Engine
* ``validate``  -> Risk Manager
* ``deploy``    -> Prop Firm Challenger
* ``monitor``   -> Mistake Tracker
* ``learn``     -> Knowledge Curator

The remaining agents (Market Regime Detector, Structure Analyst, Order
Flow Interpreter, Neural Network Architect, Portfolio Optimizer) are
recorded with their canonical stage so the registry remains a faithful
mirror of ``agents.md``, but they are not directly invoked by the
default workflow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# Canonical stage ordering, mirrored by :data:`orchestrator.workflow.STAGES`.
ALL_STAGES: Tuple[str, ...] = (
    "research",
    "design",
    "backtest",
    "validate",
    "deploy",
    "monitor",
    "learn",
)

# Primary agent for each stage.  This matches the "Workflow Stages"
# section of ``agents.md`` and is the agent whose prompt is printed by
# the workflow when that stage runs.  Other agents with the same
# ``stage`` value (e.g. multiple agents mapped to ``design``) remain
# accessible via :func:`by_stage`.
PRIMARY_AGENT_BY_STAGE: Dict[str, str] = {
    "research": "web_researcher",
    "design": "strategy_architect",
    "backtest": "backtest_engine",
    "validate": "risk_manager",
    "deploy": "prop_firm_challenger",
    "monitor": "mistake_tracker",
    "learn": "knowledge_curator",
}


def primary_agent(stage: str) -> "Agent":
    """Return the primary :class:`Agent` for ``stage``.

    Raises :class:`ValueError` for unknown stages and :class:`KeyError`
    if the primary agent name is not registered (should never happen
    for stages present in :data:`PRIMARY_AGENT_BY_STAGE`).
    """
    if stage not in ALL_STAGES:
        raise ValueError(
            f"Unknown stage {stage!r}. Expected one of {list(ALL_STAGES)}"
        )
    return get_agent(PRIMARY_AGENT_BY_STAGE[stage])


@dataclass(frozen=True)
class Agent:
    """Definition of a single orchestration agent.

    Attributes
    ----------
    name:
        Stable identifier used in code and CLI flags (snake_case).
    purpose:
        One-sentence description of the agent's role.
    responsibilities:
        Ordered tuple of bullet-point responsibilities.
    prompt_template:
        Verbatim prompt template from ``agents.md`` with ``{...}``
        placeholders that the workflow fills in.
    references:
        Ordered tuple of vault note references (wikilinks or paths).
    stage:
        The workflow stage that owns this agent.  One of
        ``research|design|backtest|validate|deploy|monitor|learn``.
    extra:
        Free-form additional metadata (currently empty by default but
        reserved for future extension without breaking the dataclass).
    """

    name: str
    purpose: str
    responsibilities: Tuple[str, ...]
    prompt_template: str
    references: Tuple[str, ...]
    stage: str
    extra: Dict[str, str] = field(default_factory=dict)

    def format_prompt(self, **kwargs: str) -> str:
        """Return ``prompt_template`` with ``{key}`` placeholders filled in.

        Unknown placeholders are left untouched so callers can populate
        the prompt progressively without raising.
        """
        try:
            return self.prompt_template.format(**kwargs)
        except KeyError:
            # ``str.format`` raises on missing keys even when they are
            # escaped.  Use a safe two-pass substitution instead.
            out = self.prompt_template
            for key, value in kwargs.items():
                out = out.replace("{" + key + "}", str(value))
            return out


# ---------------------------------------------------------------------------
# Agent definitions - mirrors agents.md exactly.
# ---------------------------------------------------------------------------


_STRATEGY_ARCHITECT = Agent(
    name="strategy_architect",
    purpose="Design, prototype, and validate trading strategies before backtesting.",
    responsibilities=(
        "Translate market insights into testable hypotheses",
        "Define entry/exit rules, position sizing, and risk parameters",
        "Map strategies to regime context and market structure",
        "Reference: [[Building and Backtesting Strategies]]",
    ),
    prompt_template=(
        "You are a quantitative strategist. Given a market edge or observation:\n"
        "1. Formalize it into a testable hypothesis\n"
        "2. Define precise entry/exit criteria\n"
        "3. Specify position sizing and risk rules\n"
        "4. Identify which market regimes this works in\n"
        "5. Flag potential look-ahead bias or overfitting risks\n"
        "\n"
        "Idea: {idea}\n"
        "Strategy name hint: {strategy_name}\n"
    ),
    references=("[[Building and Backtesting Strategies]]",),
    stage="design",
)


_BACKTEST_ENGINE = Agent(
    name="backtest_engine",
    purpose="Run backtests, validate results, and stress-test strategies.",
    responsibilities=(
        "Execute backtests using the unified registry and runner",
        "Run walk-forward validation, Monte Carlo, regime analysis",
        "Detect overfitting via Deflated Sharpe Ratio",
        "Generate performance reports with honest assessments",
        "Reference: [[All Strategies Backtest]], [[QQQ Dual-Signal Edge]]",
    ),
    prompt_template=(
        "You are a rigorous backtester. When given a strategy:\n"
        "1. Run the backtest with realistic assumptions (slippage, commissions)\n"
        "2. Calculate Sharpe, Sortino, max drawdown, win rate, profit factor\n"
        "3. Run walk-forward and out-of-sample validation\n"
        "4. Flag any overfitting concerns\n"
        "5. Provide honest assessment - no sugarcoating\n"
        "\n"
        "Idea: {idea}\n"
        "Strategy: {strategy_name}\n"
        "Ticker: {ticker}\n"
        "Period: {start} -> {end}\n"
        "Execution: {execution}\n"
        "Cost model: {cost_model}\n"
    ),
    references=(
        "[[All Strategies Backtest]]",
        "[[QQQ Dual-Signal Edge]]",
    ),
    stage="backtest",
)


_RISK_MANAGER = Agent(
    name="risk_manager",
    purpose="Enforce risk rules and manage portfolio-level exposure.",
    responsibilities=(
        "Monitor position sizes vs account equity",
        "Enforce max drawdown, daily loss limits, correlation limits",
        "Manage prop firm challenge constraints (10% target, 10% DD, 5% daily)",
        "Calculate Kelly criterion or half-Kelly sizing",
        "Reference: [[Funded 80% Pass Strategy]], [[Building and Backtesting Strategies]]",
    ),
    prompt_template=(
        "You are a risk manager for a prop firm challenge:\n"
        "- Account: ${account_size}\n"
        "- Max drawdown: {max_dd_pct}% (${max_dd_abs})\n"
        "- Daily loss limit: {daily_loss_pct}% (${daily_loss_abs})\n"
        "- Target: {target_pct}% (${target_abs})\n"
        "Given current positions and P&L, advise on:\n"
        "1. Position sizing for next trade\n"
        "2. Whether risk limits are being approached\n"
        "3. Adjustments needed to stay within constraints\n"
        "\n"
        "Backtest metrics for context:\n"
        "{metrics}\n"
    ),
    references=(
        "[[Funded 80% Pass Strategy]]",
        "[[Building and Backtesting Strategies]]",
    ),
    stage="validate",
)


_MARKET_REGIME_DETECTOR = Agent(
    name="market_regime_detector",
    purpose="Classify current market conditions and select appropriate strategies.",
    responsibilities=(
        "Identify regime: Trending, Mean-Reverting, Volatile, Balanced",
        "Read volume profile shape (bimodal vs normal)",
        "Detect regime shifts using composite profiles",
        "Recommend which strategies are active/inactive",
        "Reference: [[Market Regime Context]], [[Composite Profiles]], [[Auction Market Theory]]",
    ),
    prompt_template=(
        "You are a market regime analyst. Given recent price action and volume profile:\n"
        "1. Classify the current regime (Trending/Mean-Reverting/Volatile/Balanced)\n"
        "2. Describe the volume profile shape and what it implies\n"
        "3. Which strategies from the vault are best suited for this regime?\n"
        "4. Which strategies should be avoided?\n"
        "5. What are the key levels to watch?\n"
    ),
    references=(
        "[[Market Regime Context]]",
        "[[Composite Profiles]]",
        "[[Auction Market Theory]]",
    ),
    stage="research",
)


_STRUCTURE_ANALYST = Agent(
    name="structure_analyst",
    purpose="Analyze volume profile structure and identify trade setups.",
    responsibilities=(
        "Identify value areas, HVN, LVN, POC",
        "Detect breakout vs false breakout (Head Fakes)",
        "Find Throwback setups after confirmed breaks",
        "Map institutional order flow via volume clusters",
        "Reference: [[Volume Profile]], [[HVN vs LVN]], [[Head Fakes]], [[The Throwback]]",
    ),
    prompt_template=(
        "You are a volume profile specialist. Given a volume profile and price action:\n"
        "1. Identify the Value Area High/Low and POC\n"
        "2. Note any HVN/LVN zones and their significance\n"
        "3. Is this a balanced or imbalanced profile?\n"
        "4. Are there signs of absorption or institutional activity?\n"
        "5. What setups are forming (Head Fake, Throwback, Fade)?\n"
    ),
    references=(
        "[[Volume Profile]]",
        "[[HVN vs LVN]]",
        "[[Head Fakes]]",
        "[[The Throwback]]",
    ),
    stage="design",
)


_ORDER_FLOW_INTERPRETER = Agent(
    name="order_flow_interpreter",
    purpose="Analyze real-time order flow and microstructure.",
    responsibilities=(
        "Interpret delta, cumulative delta, divergence",
        "Detect absorption, spoofing, iceberg orders",
        "Confirm or deny structure-based signals",
        "Time entries based on order flow alignment",
        "Reference: [[Order Flow]], [[Absorption]], [[Delta Divergence]], [[Iceberg Orders]], [[Spoofing]]",
    ),
    prompt_template=(
        "You are an order flow analyst. Given recent tape/footprint data:\n"
        "1. What is the delta doing relative to price?\n"
        "2. Any signs of absorption or large passive orders?\n"
        "3. Is there spoofing or layering in the book?\n"
        "4. Does order flow confirm or contradict the structure?\n"
        "5. Timing recommendation for entry/exit\n"
    ),
    references=(
        "[[Order Flow]]",
        "[[Absorption]]",
        "[[Delta Divergence]]",
        "[[Iceberg Orders]]",
        "[[Spoofing]]",
    ),
    stage="design",
)


_MISTAKE_TRACKER = Agent(
    name="mistake_tracker",
    purpose="Log, categorize, and learn from trading errors.",
    responsibilities=(
        "Log every losing trade with context",
        "Categorize mistakes: (Entry, Exit, Sizing, Regime, Emotional)",
        "Identify recurring patterns in losses",
        "Generate weekly mistake reports",
        "Suggest rule improvements based on patterns",
        "Reference: [[Reflections/Volume Profile - Key Insights]]",
    ),
    prompt_template=(
        "You are a trading mistake analyst. Given a losing trade:\n"
        "1. What was the setup and thesis?\n"
        "2. Where did execution go wrong?\n"
        "3. Categorize the mistake (Entry/Exit/Sizing/Regime/Emotional)\n"
        "4. Is this a recurring pattern?\n"
        "5. What rule change would prevent this in the future?\n"
        "\n"
        "Recent run summary:\n"
        "{summary}\n"
    ),
    references=("[[Reflections/Volume Profile - Key Insights]]",),
    stage="monitor",
)


_KNOWLEDGE_CURATOR = Agent(
    name="knowledge_curator",
    purpose="Maintain and organize the trading knowledge base.",
    responsibilities=(
        "Ensure all notes are properly wikilinked",
        "Identify gaps in the knowledge base",
        "Suggest new concepts or strategies to research",
        "Keep [[MOC - Trading]] up to date",
        "Cross-reference related concepts",
        "Reference: [[MOC - Trading]], [[Concepts/]]",
    ),
    prompt_template=(
        "You are a knowledge management specialist for a trading vault:\n"
        "1. Review the vault structure and identify missing links\n"
        "2. Which concepts need more detail or examples?\n"
        "3. Are there contradictions between notes?\n"
        "4. Suggest new notes that would fill knowledge gaps\n"
        "5. Recommend priority order for creating new content\n"
    ),
    references=(
        "[[MOC - Trading]]",
        "[[Concepts/]]",
    ),
    stage="learn",
)


_WEB_RESEARCHER = Agent(
    name="web_researcher",
    purpose="Scrape and synthesize trading research from the web.",
    responsibilities=(
        "Search for new strategies, edges, and research papers",
        "Scrape trading forums, Twitter, QuantConnect for ideas",
        "Summarize findings into actionable vault notes",
        "Evaluate novelty vs existing vault knowledge",
        "Reference: [[Niche Trading Strategies II]]",
    ),
    prompt_template=(
        "You are a quantitative researcher. Find new trading edges:\n"
        "1. Search for recently published strategies (2024-2026)\n"
        "2. Focus on: mean reversion, momentum, microstructure, options flow\n"
        "3. For each finding: summarize the edge, expected Sharpe, data requirements\n"
        "4. Compare to existing strategies in the vault\n"
        "5. Rate viability (1-5) and effort to implement (1-5)\n"
        "\n"
        "Idea to research: {idea}\n"
    ),
    references=("[[Niche Trading Strategies II]]",),
    stage="research",
)


_PROP_FIRM_CHALLENGER = Agent(
    name="prop_firm_challenger",
    purpose="Optimize strategies for prop firm evaluations.",
    responsibilities=(
        "Adapt strategies to prop firm rules (drawdown, daily loss, target)",
        "Calculate optimal position sizing for challenge phase",
        "Monitor progress toward profit target",
        "Advise on scaling after passing challenge",
        "Reference: [[Funded 80% Pass Strategy]]",
    ),
    prompt_template=(
        "You are a prop firm challenge specialist:\n"
        "- Phase: {phase}\n"
        "- Account: ${account_size}\n"
        "- Rules: profit target {target_pct}%, max DD {max_dd_pct}%, daily loss {daily_loss_pct}%\n"
        "Given current performance metrics, advise:\n"
        "1. Is the target achievable within the time limit?\n"
        "2. Optimal position sizing to reach target safely\n"
        "3. Any rule violations imminent?\n"
        "4. Should strategy be adjusted for the remaining phases?\n"
        "\n"
        "Backtest metrics:\n"
        "{metrics}\n"
    ),
    references=(
        "[[Funded 80% Pass Strategy]]",
    ),
    stage="deploy",
)


_NEURAL_NETWORK_ARCHITECT = Agent(
    name="neural_network_architect",
    purpose="Design and train deep learning models for trading.",
    responsibilities=(
        "Design LSTM/GRU models for price prediction",
        "Build CNN models for pattern recognition in charts",
        "Create transformer models for sequence analysis",
        "Optimize hyperparameters and avoid overfitting",
        "Reference: [[Deep Learning]], [[Building and Backtesting Strategies]]",
    ),
    prompt_template=(
        "You are a deep learning engineer for trading:\n"
        "1. Design a model architecture for [prediction task]\n"
        "2. Specify input features (OHLCV, order flow, indicators)\n"
        "3. Define train/validation/test splits (no look-ahead)\n"
        "4. Suggest regularization to prevent overfitting\n"
        "5. Outline evaluation metrics beyond accuracy (Sharpe, profit factor)\n"
    ),
    references=(
        "[[Deep Learning]]",
        "[[Building and Backtesting Strategies]]",
    ),
    stage="design",
)


_PORTFOLIO_OPTIMIZER = Agent(
    name="portfolio_optimizer",
    purpose="Allocate capital across strategies and manage correlation.",
    responsibilities=(
        "Calculate optimal strategy weights",
        "Monitor strategy correlation",
        "Rebalance based on regime changes",
        "Maximize portfolio Sharpe while limiting drawdown",
        "Reference: [[Building and Backtesting Strategies]], [[All Strategies Backtest]]",
    ),
    prompt_template=(
        "You are a portfolio manager optimizing across multiple strategies:\n"
        "- Available strategies: [list with Sharpe, DD, correlation matrix]\n"
        "- Risk budget: [max DD, target Sharpe]\n"
        "Advise on:\n"
        "1. Optimal allocation weights\n"
        "2. Which strategies to activate/deactivate based on regime\n"
        "3. Rebalancing schedule\n"
        "4. Expected portfolio metrics\n"
    ),
    references=(
        "[[Building and Backtesting Strategies]]",
        "[[All Strategies Backtest]]",
    ),
    stage="deploy",
)


# Public registry: name -> Agent.  Built explicitly so the ordering is
# deterministic and easy to audit against agents.md.
AGENTS: Dict[str, Agent] = {
    a.name: a
    for a in (
        _STRATEGY_ARCHITECT,
        _BACKTEST_ENGINE,
        _RISK_MANAGER,
        _MARKET_REGIME_DETECTOR,
        _STRUCTURE_ANALYST,
        _ORDER_FLOW_INTERPRETER,
        _MISTAKE_TRACKER,
        _KNOWLEDGE_CURATOR,
        _WEB_RESEARCHER,
        _PROP_FIRM_CHALLENGER,
        _NEURAL_NETWORK_ARCHITECT,
        _PORTFOLIO_OPTIMIZER,
    )
}


def get_agent(name: str) -> Agent:
    """Return the :class:`Agent` registered under ``name``.

    Raises :class:`KeyError` if the agent is unknown.  Use
    :func:`list_agents` to enumerate the available names.
    """
    try:
        return AGENTS[name]
    except KeyError as exc:
        raise KeyError(
            f"Unknown agent {name!r}. Available: {sorted(AGENTS)}"
        ) from exc


def list_agents() -> List[str]:
    """Return the sorted list of registered agent names."""
    return sorted(AGENTS)


def by_stage(stage: str) -> List[Agent]:
    """Return all agents assigned to ``stage``, sorted by name.

    Raises :class:`ValueError` if ``stage`` is not one of the canonical
    workflow stages.
    """
    if stage not in ALL_STAGES:
        raise ValueError(
            f"Unknown stage {stage!r}. Expected one of {list(ALL_STAGES)}"
        )
    return sorted(
        (agent for agent in AGENTS.values() if agent.stage == stage),
        key=lambda a: a.name,
    )


__all__ = [
    "AGENTS",
    "Agent",
    "ALL_STAGES",
    "PRIMARY_AGENT_BY_STAGE",
    "by_stage",
    "get_agent",
    "list_agents",
    "primary_agent",
]
