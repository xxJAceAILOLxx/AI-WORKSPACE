"""Market data tool — fetch OHLCV data through the loader layer."""

from __future__ import annotations

import json
from typing import Any

from ..agent.tools import BaseTool


class GetMarketDataTool(BaseTool):
    name = "get_market_data"
    description = (
        "Fetch OHLCV (Open/High/Low/Close/Volume) data for a ticker. "
        "Returns the most recent bars as a list of dicts."
    )
    is_readonly = True
    parameters = {
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "Ticker symbol (e.g. SPY, QQQ, AAPL)"},
            "start": {"type": "string", "description": "Start date YYYY-MM-DD (default: 1 year ago)"},
            "end": {"type": "string", "description": "End date YYYY-MM-DD (default: today)"},
            "period": {
                "type": "string",
                "description": "Period shortcut: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max",
            },
            "interval": {
                "type": "string",
                "description": "Bar interval: 1m, 2m, 5m, 15m, 30m, 60m, 1d, 1wk, 1mo",
            },
        },
        "required": ["ticker"],
    }

    def execute(self, **kwargs: Any) -> str:
        import yfinance as yf

        ticker = kwargs.get("ticker", "SPY")
        start = kwargs.get("start")
        end = kwargs.get("end")
        period = kwargs.get("period", "1y")
        interval = kwargs.get("interval", "1d")

        try:
            t = yf.Ticker(ticker)
            if start and end:
                df = t.history(start=start, end=end, interval=interval)
            else:
                df = t.history(period=period, interval=interval)

            if df.empty:
                return json.dumps({"status": "ok", "ticker": ticker, "bars": [], "message": "no data"})

            # Convert to list of dicts for JSON serialization.
            df = df.reset_index()
            cols = [c for c in ["Date", "Open", "High", "Low", "Close", "Volume"] if c in df.columns]
            df = df[cols]
            # Convert Timestamps to strings.
            if "Date" in df.columns:
                df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
            bars = df.tail(100).to_dict(orient="records")  # last 100 bars

            return json.dumps({
                "status": "ok",
                "ticker": ticker,
                "interval": interval,
                "count": len(bars),
                "bars": bars,
            })
        except Exception as exc:
            return json.dumps({"status": "error", "error": str(exc)})
