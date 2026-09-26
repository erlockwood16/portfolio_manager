from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from analytics.services.volatility_service import calculate_volatility_scores_from_db


def main(db_path: str = "InvestmentAdvisor.db"):
    """Return volatility scores from the shared service layer."""
    return calculate_volatility_scores_from_db(db_path=db_path)


if __name__ == "__main__":
    print(main())
