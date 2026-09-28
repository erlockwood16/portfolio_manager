from __future__ import annotations

import argparse
import sqlite3
import time
import certifi
import urllib3

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning
)
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT / "InvestmentAdvisor.db"
SEC_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
DEFAULT_USER_AGENT = "Eric Lockwood erlockwood16@gmail.com"

REVENUE_TAGS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
    "Revenues",
]
NET_INCOME_TAGS = ["NetIncomeLoss", "ProfitLoss"]
ASSET_TAGS = ["Assets"]
LIABILITY_TAGS = ["Liabilities", "LiabilitiesAndStockholdersEquity"]
US_GAAP_SHARE_TAGS = [
    "CommonStockSharesOutstanding",
    "CommonStocksIncludingAdditionalPaidInCapitalMember",
]
DEI_SHARE_TAGS = ["EntityCommonStockSharesOutstanding"]
ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone() is not None


def table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        row[1]
        for row in conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    }


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sec_financials (
            ticker TEXT NOT NULL,
            fiscal_year INTEGER NOT NULL,
            revenue REAL,
            net_income REAL,
            assets REAL,
            liabilities REAL,
            shares_outstanding REAL,
            filing_date TEXT,
            source_form TEXT,
            loaded_timestamp TEXT,
            PRIMARY KEY (ticker, fiscal_year)
        )
        """
    )

    required = {
        "revenue": "REAL",
        "net_income": "REAL",
        "assets": "REAL",
        "liabilities": "REAL",
        "shares_outstanding": "REAL",
        "filing_date": "TEXT",
        "source_form": "TEXT",
        "loaded_timestamp": "TEXT",
    }
    existing = table_columns(conn, "sec_financials")
    for column_name, data_type in required.items():
        if column_name not in existing:
            conn.execute(
                f'ALTER TABLE sec_financials ADD COLUMN "{column_name}" {data_type}'
            )


def load_companies(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    if not table_exists(conn, "sec_company_map"):
        raise RuntimeError("Required table 'sec_company_map' does not exist.")
    if not table_exists(conn, "company_universe"):
        raise RuntimeError("Required table 'company_universe' does not exist.")

    map_columns = table_columns(conn, "sec_company_map")
    universe_columns = table_columns(conn, "company_universe")
    if not {"ticker", "cik"}.issubset(map_columns):
        raise RuntimeError("sec_company_map must contain ticker and cik columns.")
    if "ticker" not in universe_columns:
        raise RuntimeError("company_universe must contain a ticker column.")

    rows = conn.execute(
        """
        SELECT DISTINCT
            UPPER(TRIM(m.ticker)) AS ticker,
            CAST(m.cik AS TEXT) AS cik
        FROM sec_company_map AS m
        INNER JOIN company_universe AS u
            ON UPPER(TRIM(u.ticker)) = UPPER(TRIM(m.ticker))
        WHERE m.ticker IS NOT NULL
          AND m.cik IS NOT NULL
          AND TRIM(CAST(m.cik AS TEXT)) <> ''
        ORDER BY ticker
        """
    ).fetchall()

    companies: list[tuple[str, str]] = []
    for ticker, cik in rows:
        digits = "".join(character for character in str(cik) if character.isdigit())
        if ticker and digits:
            companies.append((ticker, digits.zfill(10)))
    return companies


def build_session(user_agent: str) -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov",
        }
    )
    return session


def _annual_candidates(fact: dict[str, Any], unit: str) -> list[dict[str, Any]]:
    candidates = []
    for item in fact.get("units", {}).get(unit, []):
        form = str(item.get("form") or "").upper()
        fiscal_year = item.get("fy")
        value = item.get("val")
        if fiscal_year is None or value is None or form not in ANNUAL_FORMS:
            continue
        candidates.append(item)
    return candidates


def latest_annual_fact(
    namespace_facts: dict[str, Any],
    tags: list[str],
    unit: str,
    preferred_fiscal_year: int | None = None,
) -> tuple[int | None, float | None, str | None, str | None]:
    candidates: list[dict[str, Any]] = []
    for tag_order, tag in enumerate(tags):
        fact = namespace_facts.get(tag)
        if not fact:
            continue
        for item in _annual_candidates(fact, unit):
            candidate = dict(item)
            candidate["_tag_order"] = tag_order
            candidates.append(candidate)

    if not candidates:
        return None, None, None, None

    if preferred_fiscal_year is not None:
        same_year = [item for item in candidates if int(item["fy"]) == preferred_fiscal_year]
        if same_year:
            candidates = same_year

    candidates.sort(
        key=lambda item: (
            int(item.get("fy") or 0),
            str(item.get("filed") or ""),
            str(item.get("end") or ""),
            -int(item.get("_tag_order") or 0),
        ),
        reverse=True,
    )
    selected = candidates[0]
    return (
        int(selected["fy"]),
        float(selected["val"]),
        selected.get("filed"),
        selected.get("form"),
    )


def latest_shares_fact(
    us_gaap: dict[str, Any],
    dei: dict[str, Any],
    preferred_fiscal_year: int | None,
) -> tuple[int | None, float | None, str | None, str | None]:
    result = latest_annual_fact(
        us_gaap,
        US_GAAP_SHARE_TAGS,
        "shares",
        preferred_fiscal_year,
    )
    if result[1] is not None:
        return result
    return latest_annual_fact(
        dei,
        DEI_SHARE_TAGS,
        "shares",
        preferred_fiscal_year,
    )


def extract_company_financials(
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    facts_root = payload.get("facts", {})
    us_gaap = facts_root.get("us-gaap", {})
    dei = facts_root.get("dei", {})
    if not us_gaap:
        return None

    revenue_fy, revenue, filing_date, source_form = latest_annual_fact(
        us_gaap, REVENUE_TAGS, "USD"
    )
    if revenue_fy is None:
        # Some issuers do not expose a usable revenue concept; anchor on net income.
        revenue_fy, _, filing_date, source_form = latest_annual_fact(
            us_gaap, NET_INCOME_TAGS, "USD"
        )
    if revenue_fy is None:
        return None

    _, net_income, net_filed, net_form = latest_annual_fact(
        us_gaap, NET_INCOME_TAGS, "USD", revenue_fy
    )
    _, assets, assets_filed, assets_form = latest_annual_fact(
        us_gaap, ASSET_TAGS, "USD", revenue_fy
    )
    _, liabilities, liabilities_filed, liabilities_form = latest_annual_fact(
        us_gaap, LIABILITY_TAGS, "USD", revenue_fy
    )
    _, shares, shares_filed, shares_form = latest_shares_fact(
        us_gaap, dei, revenue_fy
    )

    filing_candidates = [
        value
        for value in (filing_date, net_filed, assets_filed, liabilities_filed, shares_filed)
        if value
    ]
    form_candidates = [
        value
        for value in (source_form, net_form, assets_form, liabilities_form, shares_form)
        if value
    ]

    return {
        "fiscal_year": revenue_fy,
        "revenue": revenue,
        "net_income": net_income,
        "assets": assets,
        "liabilities": liabilities,
        "shares_outstanding": shares,
        "filing_date": max(filing_candidates) if filing_candidates else None,
        "source_form": form_candidates[0] if form_candidates else None,
    }


def upsert_financials(
    conn: sqlite3.Connection,
    ticker: str,
    financials: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO sec_financials (
            ticker,
            fiscal_year,
            revenue,
            net_income,
            assets,
            liabilities,
            shares_outstanding,
            filing_date,
            source_form,
            loaded_timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker, fiscal_year) DO UPDATE SET
            revenue = COALESCE(excluded.revenue, sec_financials.revenue),
            net_income = COALESCE(excluded.net_income, sec_financials.net_income),
            assets = COALESCE(excluded.assets, sec_financials.assets),
            liabilities = COALESCE(excluded.liabilities, sec_financials.liabilities),
            shares_outstanding = COALESCE(
                excluded.shares_outstanding,
                sec_financials.shares_outstanding
            ),
            filing_date = COALESCE(excluded.filing_date, sec_financials.filing_date),
            source_form = COALESCE(excluded.source_form, sec_financials.source_form),
            loaded_timestamp = excluded.loaded_timestamp
        """,
        (
            ticker,
            financials["fiscal_year"],
            financials["revenue"],
            financials["net_income"],
            financials["assets"],
            financials["liabilities"],
            financials["shares_outstanding"],
            financials["filing_date"],
            financials["source_form"],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )


def run_load(
    db_path: str | Path,
    user_agent: str,
    request_delay: float = 0.12,
    limit: int | None = None,
) -> int:
    database = Path(db_path).resolve()
    if not database.exists():
        raise FileNotFoundError(f"Database not found: {database}")

    session = build_session(user_agent)
    loaded = 0
    skipped = 0
    errors = 0
    missing_shares = 0

    with sqlite3.connect(database) as conn:
        ensure_schema(conn)
        companies = load_companies(conn)
        if limit is not None:
            companies = companies[:limit]
        if not companies:
            raise RuntimeError(
                "No mapped tickers were found in both sec_company_map and company_universe."
            )

        print(f"\nLoading SEC data for {len(companies):,} universe companies\n")

        for index, (ticker, cik) in enumerate(companies, start=1):
            url = SEC_COMPANY_FACTS_URL.format(cik=cik)
            try:
                response = session.get(url, timeout=30, verify=False)
                response.raise_for_status()
                financials = extract_company_financials(response.json())
                if financials is None:
                    skipped += 1
                    print(f"[{index:>4}/{len(companies):,}] {ticker:<8} skipped: no annual facts")
                else:
                    upsert_financials(conn, ticker, financials)
                    loaded += 1
                    if financials["shares_outstanding"] is None:
                        missing_shares += 1
                    print(
                        f"[{index:>4}/{len(companies):,}] {ticker:<8} "
                        f"FY{financials['fiscal_year']} "
                        f"shares={'yes' if financials['shares_outstanding'] is not None else 'no'}"
                    )
                if index % 25 == 0:
                    conn.commit()
            except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
                errors += 1
                print(f"[{index:>4}/{len(companies):,}] {ticker:<8} error: {exc}")
            time.sleep(max(0.0, request_delay))

        conn.commit()

    print("\n" + "=" * 76)
    print("SEC FINANCIAL LOAD COMPLETE")
    print("=" * 76)
    print(f"Database:                    {database}")
    print(f"Universe companies checked: {len(companies):,}")
    print(f"Companies loaded:            {loaded:,}")
    print(f"Companies skipped:           {skipped:,}")
    print(f"Request/errors:              {errors:,}")
    print(f"Loaded rows missing shares:  {missing_shares:,}")
    print("=" * 76)
    return loaded


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Load annual SEC company facts, including shares outstanding, "
            "for tickers in company_universe."
        )
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument(
        "--request-delay",
        type=float,
        default=0.12,
        help="Seconds to wait between SEC requests (default: 0.12).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional number of universe companies to process for testing.",
    )
    args = parser.parse_args()
    run_load(args.database, args.user_agent, args.request_delay, args.limit)


if __name__ == "__main__":
    main()
