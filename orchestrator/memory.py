"""Persistent memory backed by the vault ``memory.md`` note.

The on-disk file is plain markdown organised by ``## Section`` headings.
:class:`Memory` parses those sections into a dict on :meth:`load` and
re-emits them on :meth:`save`, so the orchestrator can append new
content without disturbing the rest of the note.

Internal representation returned by :meth:`load`::

    {
        "title": "Memory",
        "sections": [
            {"heading": "Last Updated", "content": "2026-06-26 ..."},
            {"heading": "Trading Framework (From Vault)", "content": "..."},
            ...
        ],
    }

:meth:`append_run` writes new workflow runs to the ``framework_runs``
section, creating the section if it does not yet exist.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# Heading that :meth:`Memory.append_run` looks for / creates.
FRAMEWORK_RUNS_HEADING = "Framework Runs"

# Matches a markdown heading like "## Foo" or "## Foo Bar".
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$", re.MULTILINE)

# Strips a leading "N. " numeric prefix from a heading so that
# "9. Backtest snapshot" normalises the same as "Backtest snapshot".
_NUM_PREFIX_RE = re.compile(r"^\d+\.\s*")


def _slugify(heading: str) -> str:
    """Lowercase + alnum/underscore slug used for dict key lookups."""
    s = heading.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def _normalize_heading(heading: str) -> str:
    """Slugify a heading after stripping any leading ``"N. "`` numeric prefix.

    This makes section lookups tolerant to numbered headings like
    ``"9. Backtest snapshot"`` so callers can pass the un-numbered title
    (e.g. ``"Backtest snapshot"``) and still find the existing section.
    """
    s = heading.strip()
    s = _NUM_PREFIX_RE.sub("", s)
    return _slugify(s)


def _now_iso() -> str:
    """ISO 8601 UTC timestamp, second precision."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Registered-strategy manifest
# ---------------------------------------------------------------------------
#
# The ``## 5. Registered strategies`` section of ``memory.md`` is rendered
# from this dict so it can be rewritten automatically when a new strategy
# is added.  Each entry maps the registered strategy name to a metadata
# dict with the columns shown in the table.
STRATEGY_MANIFEST: Dict[str, Dict[str, str]] = {
    "ibs_spy": {
        "ticker": "SPY",
        "entry": "IBS < 0.20",
        "exit": "5-day hold",
        "sizing": "95% equity",
        "cost": "etf_0.1pct",
    },
    "ibs_trend": {
        "ticker": "SPY",
        "entry": "IBS<0.20 AND Close>SMA200 AND TOM",
        "exit": "5-day hold",
        "sizing": "95% equity",
        "cost": "etf_0.1pct",
    },
    "qqq_mr": {
        "ticker": "QQQ",
        "entry": "IBS<0.20 AND Close>SMA200",
        "exit": "5-day hold",
        "sizing": "95% equity",
        "cost": "etf_0.1pct",
    },
    "rsi2_mr": {
        "ticker": "SPY",
        "entry": "RSI(2)<10 AND Close>SMA200",
        "exit": "5-day hold",
        "sizing": "95% equity",
        "cost": "etf_0.1pct",
    },
    "pct_b_mr": {
        "ticker": "SPY",
        "entry": "%B<0.10 AND Close>SMA200",
        "exit": "5-day hold",
        "sizing": "95% equity",
        "cost": "etf_0.1pct",
    },
    "multiple_days_down": {
        "ticker": "SPY",
        "entry": "down streak >=5 AND Close>SMA200",
        "exit": "5-day hold",
        "sizing": "95% equity",
        "cost": "etf_0.1pct",
    },
    "turn_of_month_strategy": {
        "ticker": "SPY",
        "entry": "last trading day of month",
        "exit": "4-day hold",
        "sizing": "95% equity",
        "cost": "etf_0.1pct",
    },
    "volume_scaled_ibs": {
        "ticker": "SPY",
        "entry": "IBS<threshold(vol_ratio) AND Close>SMA200 (inverted rule)",
        "exit": "2x ATR(14) stop OR IBS>0.50 OR 5-day hold",
        "sizing": "fixed-risk 10% of capital",
        "cost": "etf_0.1pct",
    },
    "qqq_dual_ma": {
        "ticker": "QQQ",
        "entry": "trend pullback on SMA pair",
        "exit": "Close<SMA(short)",
        "sizing": "95% equity",
        "cost": "etf_0.1pct",
    },
    "vix_etn": {
        "ticker": "SVXY/VXX",
        "entry": "VIX-regime (contango/back) flip",
        "exit": "regime flip OR end-of-data",
        "sizing": "vol-targeted",
        "cost": "vix_etn_40",
    },
    "mr_portfolio": {
        "ticker": "composite",
        "entry": "sub-signals: ibs_spy + rsi2_mr + pct_b_mr + turn_of_month",
        "exit": "per-sub hold (4-5d)",
        "sizing": "per-trade 0.95",
        "cost": "etf_0.1pct",
    },
}


def render_strategy_table(
    manifest: Optional[Dict[str, Dict[str, str]]] = None,
    *,
    include: Optional[List[str]] = None,
) -> str:
    """Render the ``Registered strategies`` markdown table.

    Parameters
    ----------
    manifest:
        Mapping ``name -> {ticker, entry, exit, sizing, cost}``.  Defaults
        to :data:`STRATEGY_MANIFEST`.
    include:
        Optional iterable of names to include (in addition to anything
        in ``manifest``); useful for appending a newly-registered
        strategy that is not yet in the static manifest.
    """
    if manifest is None:
        manifest = STRATEGY_MANIFEST

    rows: List[tuple[str, Dict[str, str]]] = []
    seen: set[str] = set()
    for name in sorted(manifest):
        rows.append((name, manifest[name]))
        seen.add(name)
    if include:
        for name in include:
            if name in seen:
                continue
            rows.append((name, {"ticker": "?", "entry": "?", "exit": "?", "sizing": "?", "cost": "?"}))

    lines: List[str] = [
        "| Name | Ticker | Entry | Exit | Sizing | Cost |",
        "|---|---|---|---|---|---|",
    ]
    for name, meta in rows:
        lines.append(
            f"| `{name}` | {meta.get('ticker', '?')} | "
            f"{meta.get('entry', '?')} | {meta.get('exit', '?')} | "
            f"{meta.get('sizing', '?')} | {meta.get('cost', '?')} |"
        )
    return "\n".join(lines)


def render_snapshot_bullet(
    strategy_name: str,
    metrics: Dict[str, Any],
    verdict: str,
    timestamp: Optional[str] = None,
) -> str:
    """Render a one-line backtest snapshot bullet.

    ``metrics`` may contain any of ``profit_factor``, ``sharpe``,
    ``cagr``, ``max_drawdown``, ``win_rate``, ``trade_count``; missing
    values are rendered as ``?``.
    """
    ts = timestamp or _now_iso()

    def _num(key: str, default: float = 0.0) -> float:
        v = metrics.get(key, default)
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    pf = _num("profit_factor")
    sharpe = _num("sharpe")
    cagr = _num("cagr")
    dd = _num("max_drawdown")
    wr = _num("win_rate")
    trades_raw = metrics.get("trade_count", 0)
    try:
        trades = int(trades_raw)
    except (TypeError, ValueError):
        trades = 0
    return (
        f"- **{ts}** - `{strategy_name}`: "
        f"PF {pf:.2f}, Sharpe {sharpe:.2f}, CAGR {cagr:.2%}, "
        f"DD {dd:.2%}, WR {wr:.2%}, {trades} trades. "
        f"Verdict: {verdict}."
    )


__all__ = [
    "FRAMEWORK_RUNS_HEADING",
    "STRATEGY_MANIFEST",
    "Memory",
    "parse_markdown",
    "render_markdown",
    "render_strategy_table",
    "render_snapshot_bullet",
]



def _format_run_entry(run: Dict[str, Any]) -> str:
    """Render ``run`` as a markdown bullet block suitable for appending."""
    timestamp = str(run.get("timestamp") or _now_iso())
    idea = str(run.get("idea") or "").strip() or "(no idea provided)"
    strategy_name = str(run.get("strategy_name") or "-")
    stages = run.get("stages") or []
    metrics = run.get("metrics") or {}
    notes = run.get("notes") or ""

    lines: List[str] = []
    lines.append(f"- **{timestamp}** - idea: {idea}")
    lines.append(f"  - strategy: `{strategy_name}`")
    if stages:
        lines.append("  - stages: " + ", ".join(str(s) for s in stages))
    if metrics:
        # Render metrics as a compact JSON block so it's machine readable.
        try:
            metrics_json = json.dumps(metrics, indent=2, sort_keys=True, default=str)
        except (TypeError, ValueError):
            metrics_json = json.dumps({k: str(v) for k, v in metrics.items()}, indent=2, sort_keys=True)
        lines.append("  - metrics:")
        for mline in metrics_json.splitlines():
            lines.append(f"    {mline}")
    if notes:
        notes_clean = str(notes).strip().replace("\n", " ")
        lines.append(f"  - notes: {notes_clean}")
    return "\n".join(lines)


class Memory:
    """Read/write the vault ``memory.md`` note.

    Parameters
    ----------
    path:
        Filesystem path to the markdown file.  Defaults to ``memory.md``
        in the current working directory.
    create_if_missing:
        If True and the file does not exist, :meth:`load` returns an
        empty skeleton instead of raising.  :meth:`save` will then write
        a fresh document.
    """

    def __init__(self, path: str = "memory.md", create_if_missing: bool = True) -> None:
        self.path = path
        self.create_if_missing = create_if_missing

    # -- I/O --------------------------------------------------------------

    def exists(self) -> bool:
        return os.path.isfile(self.path)

    def load(self) -> Dict[str, Any]:
        """Parse ``memory.md`` into a dict.

        Returns a document of the form
        ``{"title": str, "sections": [{"heading", "content"}, ...]}``.
        Section order is preserved.
        """
        if not self.exists():
            if not self.create_if_missing:
                raise FileNotFoundError(self.path)
            return {"title": "Memory", "sections": []}

        with open(self.path, "r", encoding="utf-8") as fh:
            text = fh.read()

        return parse_markdown(text)

    def save(self, data: Dict[str, Any]) -> None:
        """Write ``data`` back to ``memory.md`` atomically.

        Accepts the same dict structure returned by :meth:`load`.
        Sections are emitted in the order they appear in ``data``.  An
        empty ``title`` falls back to ``"Memory"``.
        """
        text = render_markdown(data)
        # Write atomically via a sibling temp file so a crash mid-write
        # can't corrupt the vault note.
        tmp = self.path + ".tmp"
        os.makedirs(os.path.dirname(os.path.abspath(self.path)) or ".", exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, self.path)

    # -- High-level helpers ----------------------------------------------

    def append_run(self, run: Dict[str, Any]) -> None:
        """Append ``run`` to the ``framework_runs`` section.

        Creates the section (and the file, if missing) when needed.
        ``run`` may contain any of: ``timestamp`` (ISO str), ``idea``,
        ``strategy_name``, ``stages`` (list), ``metrics`` (dict), and
        ``notes``.  A timestamp is added if not provided.
        """
        if "timestamp" not in run:
            run = {**run, "timestamp": _now_iso()}

        data = self.load()
        entry = _format_run_entry(run)

        target_idx = self._find_section_index(data, FRAMEWORK_RUNS_HEADING)

        if target_idx is None:
            data["sections"].append(
                {"heading": FRAMEWORK_RUNS_HEADING, "content": entry}
            )
        else:
            existing = data["sections"][target_idx]["content"] or ""
            if existing and not existing.endswith("\n"):
                existing += "\n"
            data["sections"][target_idx]["content"] = existing + entry + "\n"

        self.save(data)

    def update_section(
        self,
        title: str,
        content: str,
        mode: str = "replace",
    ) -> None:
        """Replace or append the body of a markdown section.

        The H2 section whose heading matches ``title`` (case- and
        numeric-prefix-insensitive) is updated.  For example,
        ``title="Backtest snapshot"`` matches a heading of
        ``"9. Backtest snapshot"`` already in ``memory.md``.

        Parameters
        ----------
        title:
            Heading to match (the leading ``"N. "`` numeric prefix, if
            any, is stripped before comparison).
        content:
            New body content for the section.  Trailing newlines are
            normalised so the rendered output stays tidy.
        mode:
            * ``"replace"`` (default) — overwrite the body with
              ``content``.
            * ``"append"`` — append ``content`` after the existing body,
              separated by a blank line.

        If no matching section exists, a new section with the literal
        ``title`` (no numeric prefix) is appended at the end of the
        document.  The file is created on demand when
        ``create_if_missing=True`` was passed to ``__init__``.
        """
        if mode not in ("replace", "append"):
            raise ValueError(
                f"mode must be 'replace' or 'append', got {mode!r}"
            )

        new_content = (content or "").rstrip("\n")
        data = self.load()
        target_idx = self._find_section_index(data, title)

        if target_idx is None:
            data["sections"].append(
                {"heading": title, "content": new_content}
            )
        else:
            existing = data["sections"][target_idx].get("content") or ""
            if mode == "replace":
                data["sections"][target_idx]["content"] = new_content
            else:  # append
                if existing and not existing.endswith("\n"):
                    existing += "\n"
                separator = "\n" if existing else ""
                data["sections"][target_idx]["content"] = (
                    existing + separator + new_content
                )

        self.save(data)

    # -- Convenience accessors -------------------------------------------

    def _find_section_index(
        self, data: Dict[str, Any], title: str
    ) -> Optional[int]:
        """Index of the section whose heading matches ``title``.

        Matching is case-insensitive and tolerant of a leading ``"N. "``
        numeric prefix, so ``"Backtest snapshot"`` matches
        ``"9. Backtest snapshot"``.
        """
        target = _normalize_heading(title)
        for idx, section in enumerate(data["sections"]):
            if _normalize_heading(section["heading"]) == target:
                return idx
        return None

    def find_section(self, heading: str) -> Optional[Dict[str, str]]:
        """Return the section dict whose heading matches ``heading``.

        Matching is case-insensitive and tolerant of a leading ``"N. "``
        numeric prefix, so ``"Backtest snapshot"`` matches
        ``"9. Backtest snapshot"``.
        """
        data = self.load()
        idx = self._find_section_index(data, heading)
        if idx is None:
            return None
        return data["sections"][idx]


# ---------------------------------------------------------------------------
# Module-level helpers (kept here so tests can import them directly).
# ---------------------------------------------------------------------------


def parse_markdown(text: str) -> Dict[str, Any]:
    """Parse a markdown document into ``{"title", "sections"}`` form.

    The first H1 (if any) becomes the title; H2+ headings become
    section boundaries.  Content between headings is preserved verbatim,
    including blank lines and leading/trailing whitespace.
    """
    title = "Memory"
    sections: List[Dict[str, str]] = []
    current: Optional[Dict[str, str]] = None

    lines = text.splitlines()
    i = 0
    n = len(lines)

    # Detect the document title (first H1) and skip its line.
    title_consumed = False
    while i < n:
        line = lines[i]
        if line.startswith("# ") and not line.startswith("## "):
            title = line[2:].strip() or "Memory"
            title_consumed = True
            i += 1
            break
        elif line.strip() == "":
            i += 1
            continue
        else:
            # No H1 title; treat entire file as one implicit section.
            break

    # Walk remaining lines, splitting on H2+ headings.
    buf: List[str] = []
    if not title_consumed:
        # Whole-document content (no H1) becomes an untitled preamble.
        current = {"heading": "", "content": ""}
    else:
        current = None

    def _flush(buf: List[str]) -> None:
        if current is None:
            return
        # Preserve blank lines around content but trim the trailing whitespace.
        content = "\n".join(buf)
        # Strip leading/trailing blank lines but keep internal structure.
        content = content.strip("\n")
        current["content"] = content
        sections.append(current)

    pending_section: Optional[Dict[str, str]] = None
    while i < n:
        line = lines[i]
        m = _HEADING_RE.match(line)
        if m and len(m.group(1)) >= 2:
            # Close out the previous section.
            _flush(buf)
            buf = []
            heading_text = m.group(2).strip()
            pending_section = {"heading": heading_text, "content": ""}
            current = pending_section
        else:
            buf.append(line)
        i += 1

    _flush(buf)

    # If we never saw a heading at all, fall back to a single implicit
    # section so callers don't have to special-case empty documents.
    if not sections:
        sections.append(current or {"heading": "", "content": ""})

    return {"title": title, "sections": sections}


def render_markdown(data: Dict[str, Any]) -> str:
    """Render a ``{"title", "sections"}`` dict back to markdown text."""
    title = (data.get("title") or "Memory").strip() or "Memory"
    out: List[str] = [f"# {title}", ""]

    for section in data.get("sections", []):
        heading = (section.get("heading") or "").strip()
        content = section.get("content", "")
        if heading:
            out.append(f"## {heading}")
            out.append("")
        if content:
            # Ensure exactly one trailing newline before the next heading.
            out.append(content.rstrip("\n"))
            out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


__all__ = [
    "FRAMEWORK_RUNS_HEADING",
    "Memory",
    "parse_markdown",
    "render_markdown",
]
