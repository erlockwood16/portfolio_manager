from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from analytics.services.ranking_service import run_ranking_update


def main(db_path: str = "InvestmentAdvisor.db"):
    """Run the ranking update as a thin wrapper."""
    return run_ranking_update(db_path=db_path)


if __name__ == "__main__":
    print(f"Scores Updated: {main()}")
