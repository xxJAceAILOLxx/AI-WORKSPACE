"""Data loading and OHLCV container utilities.

The data module wraps :mod:`yfinance` for daily OHLCV downloads and provides
a thin ``OHLCV`` container that exposes only the columns the framework
needs (Open, High, Low, Close, Volume).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import pandas as pd

try:
    import yfinance as yf  # type: ignore
except ImportError as e:  # pragma: no cover - import guard
    raise ImportError(
        "yfinance is required for backtest.data. Install it via `pip install yfinance`."
    ) from e


@dataclass(frozen=True)
class OHLCV:
    """Container for a single ticker's daily OHLCV data.

    The wrapped ``df`` must contain only the columns ``Open``, ``High``,
    ``Low``, ``Close`` and ``Volume`` with a :class:`pandas.DatetimeIndex`.
    """

    ticker: str
    df: pd.DataFrame

    def __post_init__(self) -> None:
        required = {"Open", "High", "Low", "Close", "Volume"}
        missing = required.difference(self.df.columns)
        if missing:
            raise ValueError(
                f"OHLCV for {self.ticker!r} missing columns: {sorted(missing)}"
            )
        if not isinstance(self.df.index, pd.DatetimeIndex):
            raise ValueError(
                f"OHLCV for {self.ticker!r} must be indexed by DatetimeIndex, got "
                f"{type(self.df.index).__name__}"
            )

    @property
    def close(self) -> pd.Series:
        return self.df["Close"]

    @property
    def dates(self) -> pd.DatetimeIndex:
        return self.df.index

    def align_to(self, other: "OHLCV") -> pd.DataFrame:
        """Return ``self.df`` restricted to the dates shared with ``other``."""
        common = self.df.index.intersection(other.df.index)
        return self.df.loc[common].copy()


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse a possible MultiIndex columns object to a flat level.

    ``yfinance`` can return either a flat ``DatetimeIndex`` of columns or
    a 2-level ``MultiIndex`` (Price, Ticker) depending on the version and
    number of tickers requested.  The framework only ever downloads one
    ticker, so we take the first level (``Price``).
    """
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    return df


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only OHLCV columns and enforce a sorted DatetimeIndex."""
    df = _flatten_columns(df)
    wanted = ["Open", "High", "Low", "Close", "Volume"]
    present = [c for c in wanted if c in df.columns]
    if len(present) != len(wanted):
        missing = [c for c in wanted if c not in df.columns]
        raise ValueError(f"Downloaded data missing expected columns: {missing}")
    df = df[wanted].copy()
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    # Drop any rows with NaN in OHLC (volume NaN is allowed -> 0).
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    df["Volume"] = df["Volume"].fillna(0).astype(float)
    return df


def _cache_path(ticker: str, start: str, end: str, cache_dir: str) -> str:
    safe_ticker = ticker.replace("/", "_").replace(" ", "_")
    return os.path.join(cache_dir, f"{safe_ticker}_{start}_{end}.csv")


def load_daily(
    ticker: str,
    start: str,
    end: str,
    cache_dir: str = "data/cache",
    force: bool = False,
) -> OHLCV:
    """Load daily OHLCV data for ``ticker`` between ``start`` and ``end``.

    Data is cached as a CSV under ``cache_dir`` keyed by ticker and date
    range so subsequent calls are offline.  Pass ``force=True`` to ignore
    the cache and re-download.
    """
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = _cache_path(ticker, start, end, cache_dir)

    if cache_file.endswith(".csv") and os.path.exists(cache_file) and not force:
        raw = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        df = _normalize(raw)
    else:
        df_downloaded = yf.download(
            ticker,
            start=start,
            end=end,
            progress=False,
            auto_adjust=False,
            threads=False,
        )
        if df_downloaded is None or len(df_downloaded) == 0:
            raise ValueError(
                f"No data downloaded for ticker {ticker!r} between {start} and {end}."
            )
        df = _normalize(df_downloaded)
        df.to_csv(cache_file)

    return OHLCV(ticker=ticker, df=df)


def from_dataframe(ticker: str, df: pd.DataFrame) -> OHLCV:
    """Helper to construct an :class:`OHLCV` from a raw DataFrame (e.g. tests)."""
    return OHLCV(ticker=ticker, df=_normalize(df))


# ---------------------------------------------------------------------------
# Intraday loaders: Binance public data + HF Data Library
# ---------------------------------------------------------------------------
#
# These loaders expose the same OHLCV container as `load_daily` but accept
# sub-daily bar frequencies. They are intentionally dependency-light
# (urllib + stdlib + `requests` which is already required by yfinance).
#
# Caching: monthly zips (Binance) and JSON responses (HF) are stored as
# flat CSVs under ``cache_dir`` so subsequent loads are offline.


import io as _io
import json as _json
import os as _os
import time as _time
import zipfile as _zipfile
from typing import Optional as _Optional
from urllib.parse import urlencode as _urlencode
from urllib.request import Request as _Request, urlopen as _urlopen

try:
    import requests as _requests  # already required by yfinance
except ImportError:  # pragma: no cover - import guard
    _requests = None  # type: ignore[assignment]


BINANCE_VISION_BASE = "https://data.binance.vision/data/spot/monthly/klines"
HF_DATA_API_BASE = "https://api.hfdatalibrary.com/v1"


# Map our interval names to Binance Vision interval strings.
_BINANCE_INTERVALS = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "2h": "2h",
    "4h": "4h",
    "6h": "6h",
    "8h": "8h",
    "12h": "12h",
    "1d": "1d",
}


def _month_range(start: str, end: str):
    """Yield (year, month) pairs covering the inclusive [start, end] range."""
    s = pd.Timestamp(start).to_period("M")
    e = pd.Timestamp(end).to_period("M")
    for p in pd.period_range(s, e, freq="M"):
        yield int(p.year), int(p.month)


def _download_binance_zip(symbol: str, interval: str, year: int, month: int, timeout: int = 60) -> bytes:
    """Download one monthly zip from Binance public data. Raises on HTTP error."""
    fname = f"{symbol}-{interval}-{year:04d}-{month:02d}.zip"
    url = f"{BINANCE_VISION_BASE}/{symbol}/{interval}/{fname}"
    req = _Request(url, headers={"User-Agent": "backtest-framework/1.0"})
    with _urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _parse_binance_csv(raw: bytes) -> pd.DataFrame:
    """Parse Binance kline CSV bytes into a normalised OHLCV DataFrame.

    ``raw`` may be either a raw CSV payload or a zip archive containing one
    CSV (the monthly files from data.binance.vision are zipped). When the
    first bytes look like a zip (``PK\\x03\\x04``) we extract the first
    member and parse that instead.

    Binance CSV columns (no header):
        0 open_time (ms epoch)
        1 open
        2 high
        3 low
        4 close
        5 volume
        6 close_time
        7 quote_volume
        8 count
        9 taker_buy_base
        10 taker_buy_quote
        11 ignore
    """
    # If the payload is a zip, extract the first CSV member.
    if raw[:4] == b"PK\x03\x04":
        with _zipfile.ZipFile(_io.BytesIO(raw)) as zf:
            csv_name = next(n for n in zf.namelist() if n.endswith(".csv"))
            with zf.open(csv_name) as fh:
                csv_bytes = fh.read()
    else:
        csv_bytes = raw

    df = pd.read_csv(_io.BytesIO(csv_bytes), header=None)
    # Columns: 0=open_time, 1=open, 2=high, 3=low, 4=close, 5=volume,
    # 6=close_time, 7=quote_volume, 8=count, ...
    df = df.iloc[:, [0, 1, 2, 3, 4, 5]].copy()
    df.columns = ["_open_time", "Open", "High", "Low", "Close", "Volume"]
    # Binance switched from millisecond to microsecond timestamps in 2025.
    # A 2025+ timestamp in ms is ~1.74e12; in us it is ~1.74e15. Auto-detect.
    first_ts = float(df["_open_time"].iloc[0])
    unit = "us" if first_ts > 1e13 else "ms"
    df.index = pd.to_datetime(df["_open_time"], unit=unit)
    df = df.drop(columns=["_open_time"])
    for c in ("Open", "High", "Low", "Close"):
        df[c] = df[c].astype(float)
    df["Volume"] = df["Volume"].astype(float)
    return df[["Open", "High", "Low", "Close", "Volume"]].sort_index()


def load_intraday_binance(
    symbol: str,
    interval: str,
    start: str,
    end: str,
    cache_dir: str = "data/cache_intraday",
    timeout: int = 60,
    force: bool = False,
    sleep_seconds: float = 0.0,
) -> "OHLCV":
    """Load intraday OHLCV from Binance public data (data.binance.vision).

    Parameters
    ----------
    symbol : str
        Binance symbol, e.g. ``"BTCUSDT"`` or ``"ETHUSDT"``.
    interval : str
        One of ``1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d``.
    start, end : str
        ISO dates ``"YYYY-MM-DD"`` (inclusive).
    cache_dir : str
        Where monthly CSV shards are stored on disk.
    timeout, force, sleep_seconds :
        Network / politeness controls.

    Returns
    -------
    OHLCV
    """
    if interval not in _BINANCE_INTERVALS:
        raise ValueError(
            f"Unsupported interval {interval!r}; expected one of {sorted(_BINANCE_INTERVALS)}"
        )
    biv = _BINANCE_INTERVALS[interval]
    _os.makedirs(cache_dir, exist_ok=True)

    shards: list[pd.DataFrame] = []
    for year, month in _month_range(start, end):
        shard_path = _os.path.join(
            cache_dir, f"{symbol}_{biv}_{year:04d}-{month:02d}.csv"
        )
        if _os.path.exists(shard_path) and not force:
            shard = pd.read_csv(shard_path, index_col=0, parse_dates=True)
        else:
            try:
                raw = _download_binance_zip(symbol, biv, year, month, timeout=timeout)
            except Exception as e:  # pragma: no cover - network dependent
                # Missing months (e.g. before a symbol listed) -> skip silently.
                print(f"  skip {symbol} {biv} {year:04d}-{month:02d}: {e}")
                continue
            shard = _parse_binance_csv(raw)
            shard.to_csv(shard_path)
        shards.append(shard)
        if sleep_seconds > 0:
            _time.sleep(sleep_seconds)

    if not shards:
        raise ValueError(
            f"No Binance data downloaded for {symbol} {biv} between {start} and {end}."
        )
    df = pd.concat(shards).sort_index()
    df = df[~df.index.duplicated(keep="first")]
    df = df.loc[pd.Timestamp(start) : pd.Timestamp(end) + pd.Timedelta(days=1)]
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    df["Volume"] = df["Volume"].fillna(0).astype(float)
    return OHLCV(ticker=symbol, df=df)


def _hf_data_get(path: str, params: dict, api_key: _Optional[str], timeout: int = 30):
    """GET request against the HF Data Library REST API."""
    if _requests is None:
        raise ImportError("requests is required for the HF Data Library loader")
    url = f"{HF_DATA_API_BASE}{path}"
    headers = {"Accept": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    resp = _requests.get(url, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp


def load_intraday_hf(
    ticker: str,
    start: str,
    end: str,
    version: str = "clean",
    cache_dir: str = "data/cache_intraday_hf",
    api_key: _Optional[str] = None,
    timeout: int = 30,
    force: bool = False,
) -> "OHLCV":
    """Load 1-minute OHLCV from the HF Data Library (CC BY 4.0).

    Requires a free API key from https://hfdatalibrary.com/ (register with
    name, institution, email). Set the ``HF_DATA_API_KEY`` environment
    variable or pass ``api_key=...``. Without a key, the loader will raise.

    Coverage: 1,391 US stocks and ETFs from December 2002 to present.
    """
    if api_key is None:
        api_key = _os.environ.get("HF_DATA_API_KEY")
    if not api_key:
        raise ValueError(
            "HF Data Library requires an API key. Register free at "
            "https://hfdatalibrary.com/ and set HF_DATA_API_KEY in env, "
            "or pass api_key=..."
        )
    _os.makedirs(cache_dir, exist_ok=True)
    cache_file = _os.path.join(cache_dir, f"{ticker}_{version}_{start}_{end}.csv")
    if _os.path.exists(cache_file) and not force:
        raw = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        df = _normalize(raw)
        return OHLCV(ticker=ticker, df=df)

    rows: list[dict] = []
    offset = 0
    page_size = 10_000
    while True:
        params = {
            "start": start,
            "end": end,
            "version": version,
            "format": "json",
            "limit": page_size,
            "offset": offset,
        }
        resp = _hf_data_get(f"/bars/{ticker}", params, api_key=api_key, timeout=timeout)
        data = resp.json()
        page = data.get("bars") or data.get("data") or []
        if not page:
            break
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size

    if not rows:
        raise ValueError(
            f"HF Data Library returned no bars for {ticker} between {start} and {end}."
        )
    df = pd.DataFrame(rows)
    # Normalise column names: HF uses lowercase + timestamps.
    rename = {
        "t": "datetime", "timestamp": "datetime", "time": "datetime", "date": "datetime",
        "o": "Open", "open": "Open",
        "h": "High", "high": "High",
        "l": "Low", "low": "Low",
        "c": "Close", "close": "Close",
        "v": "Volume", "volume": "Volume",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    if "datetime" not in df.columns:
        raise ValueError(f"HF response missing datetime column; got: {list(df.columns)}")
    df.index = pd.to_datetime(df["datetime"])
    df = df.drop(columns=["datetime"])
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    for c in ("Open", "High", "Low", "Close", "Volume"):
        df[c] = df[c].astype(float)
    df = df.sort_index()
    df = df.loc[pd.Timestamp(start) : pd.Timestamp(end) + pd.Timedelta(days=1)]
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    df["Volume"] = df["Volume"].fillna(0).astype(float)
    df.to_csv(cache_file)
    return OHLCV(ticker=ticker, df=df)
