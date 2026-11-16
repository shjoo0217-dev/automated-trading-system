"""Point-in-time data contracts. No current-name lookup or latest-restatement joins."""
from __future__ import annotations
from typing import Protocol
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd


class HistoricalProvider(Protocol):
    def security_history(self) -> pd.DataFrame: ...
    def sessions(self, market: str) -> pd.DataFrame: ...
    def bars(self, ticker: str, start: str, end: str) -> pd.DataFrame: ...
    def corporate_actions(self, ticker: str) -> pd.DataFrame: ...
    def disclosures(self, ticker: str, known_at: str) -> pd.DataFrame: ...


class LiveExecution(Protocol):
    """Separate future broker integration. No order submission implementation is included."""
    def quote(self, ticker: str) -> dict: ...
    def submit_order(self, ticker: str, side: str, quantity: int, limit_price: float) -> dict: ...


def available_session(first_seen, sessions):
    """Conservative whole-day lag. Never manufacture Korean holidays with weekday logic."""
    day = pd.Timestamp(first_seen).tz_convert('Asia/Seoul').date()
    candidates = sessions[pd.to_datetime(sessions['session']).dt.date > day].sort_values('session')
    if candidates.empty: return None
    return pd.Timestamp(candidates.iloc[0]['open_at']).isoformat()


def asof_facts(facts, available_at):
    if facts.empty: return facts
    mask = pd.to_datetime(facts['known_at'], utc=True) <= pd.Timestamp(available_at)
    result = facts[mask].sort_values('known_at')
    return result.drop_duplicates(['ticker','metric','period_end','consolidation'], keep='last')


def excess_20(ticker, available_at, sessions, bars, benchmark, benchmark_id, roundtrip_bps=30):
    """Entry open t, exit close t+19: exactly 20 sessions including entry session.
    Inputs MUST use forward total-return adjustment anchored at entry, including dividends,
    splits and delisting settlement; never silently substitute a later available price.
    """
    s = sessions.sort_values('session')
    s = s[pd.to_datetime(s['open_at'], utc=True) >= pd.Timestamp(available_at)].head(20)
    if len(s) != 20: return {'status': 'insufficient_horizon', 'excess_return_20d': None}
    start, end = s.iloc[0]['session'], s.iloc[-1]['session']
    def endpoints(frame):
        frame = frame.set_index('session')
        if frame.index.duplicated().any(): raise ValueError('duplicate_price_sessions')
        if start not in frame.index or end not in frame.index: return None
        if not set(s['session']).issubset(set(frame.index)): return None
        if not frame.loc[list(s['session']), 'tradable'].all(): return None
        rows = frame.loc[[start, end]]
        if not (rows['adjustment_method'] == 'forward_total_return_anchor_entry').all():
            raise ValueError('adjustment_definition_missing')
        op, close = float(frame.loc[start, 'adjusted_open']), float(frame.loc[end, 'adjusted_close'])
        if op <= 0 or close < 0: raise ValueError('invalid_price')
        return op, close, rows['source_id'].tolist()
    equity = endpoints(bars[bars['ticker'] == ticker]); index = endpoints(benchmark)
    if equity is None or index is None: return {'status': 'missing_or_untradable_prices', 'excess_return_20d': None}
    gross = equity[1] / equity[0] - 1; market = index[1] / index[0] - 1
    return {'status': 'observed', 'excess_return_20d': gross - market,
            'net_excess_return_20d': gross - market - roundtrip_bps / 10000,
            'stock_total_return': gross, 'index_total_return': market,
            'entry_session': start, 'exit_session': end, 'entry_at': s.iloc[0]['open_at'], 'exit_at': s.iloc[-1]['close_at'],
            'entry_price': equity[0], 'exit_price': equity[1], 'benchmark_entry': index[0], 'benchmark_exit': index[1],
            'benchmark_id': benchmark_id, 'roundtrip_bps': roundtrip_bps,
            'price_definition': 'entry adjusted open; exit adjusted close at 20th session',
            'adjustment_method': 'forward_total_return_anchor_entry', 'price_evidence': equity[2] + index[2]}
