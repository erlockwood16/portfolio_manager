from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from portfolio.services.recommend_allocations import run_recommend_allocations


def main(
    db_path: str = "InvestmentAdvisor.db",
    portfolio_value: float = 25000,
    top_stocks: int = 20,
) -> int:
    """Run recommended allocation generation through the shared service module."""
    return run_recommend_allocations(
        db_path=db_path,
        portfolio_value=portfolio_value,
        top_stocks=top_stocks,
    )


if __name__ == "__main__":
    main()
