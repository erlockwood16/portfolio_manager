from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

FACTOR_WEIGHTS = {"momentum_score": .25, "value_score": .25, "quality_score": .25, "growth_score": .25}

class Scores:
    """Convenience wrapper around the factor analytics pipeline."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path).resolve()

    def __len__(self) -> int:
        with self._connect() as conn:
            self._ensure_schema(conn)
            if not _table_exists(conn, "analytics_scores"):
                return 0
            row = conn.execute("SELECT COUNT(*) FROM analytics_scores").fetchone()
            return int(row[0]) if row else 0

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self, conn):
        _ensure_table(conn)

    def update(self) -> int:
        return run_update(str(self.db_path))

    def fetch_scores(self):
        with self._connect() as conn:
            return pd.read_sql_query("SELECT * FROM analytics_scores ORDER BY ticker", conn)

    def calculate(self):
        with self._connect() as conn:
            base = _price_factors(conn).merge(_fundamental_factors(conn), on="ticker", how="left")
            base["overall_score"] = _composite(base)
            return base


def _table_exists(c, name):
    return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _columns(c, name):
    return {
        r[1]
        for r in c.execute(
            f'PRAGMA table_info("{name}")'
        ).fetchall()
    }


def _ensure_table(c):
    c.execute("""CREATE TABLE IF NOT EXISTS analytics_scores(
        ticker TEXT PRIMARY KEY,current_price REAL,sma20 REAL,sma50 REAL,sma200 REAL,
        momentum_score REAL,volatility REAL,value_score REAL,quality_score REAL,
        growth_score REAL,overall_score REAL,score_date TEXT)""")
    required={"current_price":"REAL","sma20":"REAL","sma50":"REAL","sma200":"REAL",
              "momentum_score":"REAL","volatility":"REAL","value_score":"REAL",
              "quality_score":"REAL","growth_score":"REAL","overall_score":"REAL","score_date":"TEXT"}
    existing=_columns(c,"analytics_scores")
    for name,typ in required.items():
        if name not in existing:
            c.execute(f'ALTER TABLE analytics_scores ADD COLUMN "{name}" {typ}')


def _pct(s, higher=True):
    x = pd.to_numeric(
        s,
        errors="coerce"
    ).replace([np.inf, -np.inf], np.nan)

    out = pd.Series(
        np.nan,
        index=s.index,
        dtype=float
    )

    valid = x.notna()

    if valid.any():

        if higher:
            ranks = x.loc[valid].rank(
                method="average",
                pct=True,
                ascending=True
            )
        else:
            ranks = x.loc[valid].rank(
                method="average",
                pct=True,
                ascending=False
            )

        out.loc[valid] = ranks * 100

    return out.round(2)

def _composite(df):
    num=pd.Series(0.,index=df.index); den=pd.Series(0.,index=df.index)
    for col,w in FACTOR_WEIGHTS.items():
        valid=df[col].notna(); num.loc[valid]+=df.loc[valid,col]*w; den.loc[valid]+=w
    return (num/den.replace(0,np.nan)).clip(0,100).round(2)


def _price_factors(c):
    if not _table_exists(c,"prices"): raise RuntimeError("Required table 'prices' does not exist.")
    p=pd.read_sql_query("""SELECT UPPER(TRIM(ticker)) ticker,price_date,close_price FROM prices
                           WHERE ticker IS NOT NULL AND close_price IS NOT NULL ORDER BY ticker,price_date""",c)
    p["close_price"]=pd.to_numeric(p["close_price"],errors="coerce")
    rows=[]
    for ticker,g in p.groupby("ticker",sort=True):
        close=g["close_price"].dropna().astype(float)
        if close.empty: continue
        cur=float(close.iloc[-1]); avgs={n:(float(close.tail(n).mean()) if len(close)>=n else np.nan) for n in (20,50,200)}
        points=available=0.
        for n,w in ((20,30.),(50,30.),(200,40.)):
            if pd.notna(avgs[n]):
                available+=w
                if cur>avgs[n]: points+=w
        trend=points/available*100 if available else np.nan
        ret=close.pct_change().dropna(); vol=float(ret.std(ddof=1)*np.sqrt(252)*100) if len(ret)>=2 else np.nan
        rows.append((ticker,cur,avgs[20],avgs[50],avgs[200],trend,vol))
    out=pd.DataFrame(rows,columns=["ticker","current_price","sma20","sma50","sma200","trend_score","volatility"])
    if out.empty: raise RuntimeError("No usable price histories found.")
    out["trend_percentile"]=_pct(out["trend_score"],True)
    out["low_volatility_percentile"]=_pct(out["volatility"],False)
    out["momentum_score"]=(out["trend_percentile"]*.70+out["low_volatility_percentile"]*.30).round(2)
    return out


def _fundamental_factors(c):
    frames=[]
    if _table_exists(c,"fundamental_metrics"):
        m=pd.read_sql_query("""SELECT UPPER(TRIM(ticker)) ticker,revenue_growth,earnings_growth,asset_growth,
          net_margin,debt_ratio,roa,quality_score source_quality_score,calculated_date FROM fundamental_metrics""",c)
        if not m.empty: frames.append(m.sort_values("calculated_date").drop_duplicates("ticker",keep="last"))
    if _table_exists(c,"fundamentals"):
        f=pd.read_sql_query("""SELECT UPPER(TRIM(ticker)) ticker,pe_ratio,revenue_growth fundamentals_revenue_growth,
          earnings_growth fundamentals_earnings_growth,debt_to_equity,roe,price_to_book,last_updated FROM fundamentals""",c)
        if not f.empty: frames.append(f.sort_values("last_updated").drop_duplicates("ticker",keep="last"))
    if not frames: return pd.DataFrame(columns=["ticker","value_score","quality_score","growth_score"])
    x=frames[0]
    for f in frames[1:]: x=x.merge(f,on="ticker",how="outer")
    bounds={"revenue_growth":(-50,100),"earnings_growth":(-100,200),"asset_growth":(-50,100),
            "fundamentals_revenue_growth":(-50,100),"fundamentals_earnings_growth":(-100,200)}
    for col,(lo,hi) in bounds.items():
        if col in x: x[col]=pd.to_numeric(x[col],errors="coerce").clip(lo,hi)
    growth=[]
    for col in ("revenue_growth","earnings_growth","asset_growth"):
        if col in x: growth.append(_pct(x[col],True))
    x["growth_score"]=pd.concat(growth,axis=1).mean(axis=1,skipna=True).round(2) if growth else np.nan
    source=_pct(x["source_quality_score"],True) if "source_quality_score" in x else pd.Series(np.nan,index=x.index)
    q=[]
    for col,high in (("net_margin",True),("roa",True),("roe",True),("debt_ratio",False),("debt_to_equity",False)):
        if col in x:q.append(_pct(x[col],high))
    fallback=pd.concat(q,axis=1).mean(axis=1,skipna=True) if q else pd.Series(np.nan,index=x.index)
    x["quality_score"]=source.fillna(fallback).round(2)
    value=[]
    for col in ("pe_ratio","price_to_book"):
        if col in x:
            positive=pd.to_numeric(x[col],errors="coerce").where(lambda z:z>0)
            value.append(_pct(positive,False))
    if "roe" in x:value.append(_pct(x["roe"],True))
    x["value_score"]=pd.concat(value,axis=1).mean(axis=1,skipna=True).round(2) if value else np.nan
    return x[["ticker","value_score","quality_score","growth_score"]]


def run_update(db_path: str) -> int:
    db = Path(db_path).resolve()

    if not db.exists():
        raise FileNotFoundError(
            f"Database not found: {db}"
        )

    with sqlite3.connect(db) as c:

        _ensure_table(c)

        scores = (
            _price_factors(c)
            .merge(
                _fundamental_factors(c),
                on="ticker",
                how="left"
            )
            .drop_duplicates(
                subset=["ticker"]
            )
        )

        scores["overall_score"] = _composite(scores)

        assert (
            scores["overall_score"]
            .dropna()
            .between(0, 100)
            .all()
        )

        date = datetime.today().strftime("%Y-%m-%d")

        payload = []

        cols = [
            "ticker",
            "current_price",
            "sma20",
            "sma50",
            "sma200",
            "momentum_score",
            "volatility",
            "value_score",
            "quality_score",
            "growth_score",
            "overall_score"
        ]

        for _, r in scores.iterrows():

            row = []

            for col in cols:

                value = r[col]

                if pd.isna(value):
                    row.append(None)

                elif col == "ticker":
                    row.append(value)

                else:
                    row.append(
                        round(float(value), 2)
                    )

            row.append(date)

            payload.append(tuple(row))

        if not payload:
            raise RuntimeError(
                "No analytics scores were generated."
            )

        c.executemany(
            """
            INSERT INTO analytics_scores(
                ticker,
                current_price,
                sma20,
                sma50,
                sma200,
                momentum_score,
                volatility,
                value_score,
                quality_score,
                growth_score,
                overall_score,
                score_date
            )
            VALUES(
                ?,?,?,?,?,?,
                ?,?,?,?,?,?
            )
            ON CONFLICT(ticker)
            DO UPDATE SET
                current_price = excluded.current_price,
                sma20 = excluded.sma20,
                sma50 = excluded.sma50,
                sma200 = excluded.sma200,
                momentum_score = excluded.momentum_score,
                volatility = excluded.volatility,
                value_score = excluded.value_score,
                quality_score = excluded.quality_score,
                growth_score = excluded.growth_score,
                overall_score = excluded.overall_score,
                score_date = excluded.score_date
            """,
            payload,
        )

        c.commit()

    counts = (
        scores[
            [
                "value_score",
                "quality_score",
                "growth_score",
            ]
        ]
        .notna()
        .sum()
    )

    print("\n" + "=" * 76)
    print("MULTI-FACTOR SCORE UPDATE COMPLETE")
    print("=" * 76)

    print(
        f"Database: {db}\n"
        f"Tickers updated: {len(scores):,}\n"
        f"Value scores: {counts['value_score']:,}\n"
        f"Quality scores: {counts['quality_score']:,}\n"
        f"Growth scores: {counts['growth_score']:,}\n"
        f"Score date: {date}"
    )

    print(
        "Overall scores are 0-100 and use only available, non-synthetic factors."
    )

    print("=" * 76)

    return len(scores)