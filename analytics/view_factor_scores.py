from abc import ABC, abstractmethod
import sqlite3


class row(ABC):
    """Abstract base class for a factor-score record."""

    @property
    @abstractmethod
    def ticker(self):
        """Return the ticker symbol."""

    @property
    @abstractmethod
    def value_score(self):
        """Return the value factor score."""

    @property
    @abstractmethod
    def quality_score(self):
        """Return the quality factor score."""

    @property
    @abstractmethod
    def growth_score(self):
        """Return the growth factor score."""

    @property
    @abstractmethod
    def momentum_score(self):
        """Return the momentum factor score."""

    @property
    @abstractmethod
    def overall_score(self):
        """Return the overall score."""

    @abstractmethod
    def as_dict(self):
        """Return a dictionary representation of the row."""

    @abstractmethod
    def format_for_display(self):
        """Return a display-friendly string."""


class FactorScoreRow(row):
    """Concrete implementation of a factor-score row."""

    @classmethod
    def from_db_row(cls, db_row):
        """Build a row from a SQLite result tuple."""
        return cls(
            ticker=db_row[0],
            value_score=db_row[1],
            quality_score=db_row[2],
            growth_score=db_row[3],
            momentum_score=db_row[4],
            overall_score=db_row[5],
        )

    def __init__(self, ticker, value_score, quality_score, growth_score, momentum_score, overall_score):
        self._ticker = "" if ticker is None else str(ticker)
        self._value_score = self._coerce_float(value_score)
        self._quality_score = self._coerce_float(quality_score)
        self._growth_score = self._coerce_float(growth_score)
        self._momentum_score = self._coerce_float(momentum_score)
        self._overall_score = self._coerce_float(overall_score)

    @staticmethod
    def _coerce_float(value):
        """Convert a score-like value to a float while preserving useful defaults."""
        return float(value) if value is not None else 0.0

    @property
    def ticker(self):
        return self._ticker

    @ticker.setter
    def ticker(self, value):
        self._ticker = str(value)

    @property
    def value_score(self):
        return self._value_score

    @value_score.setter
    def value_score(self, value):
        self._value_score = self._coerce_float(value)

    @property
    def quality_score(self):
        return self._quality_score

    @quality_score.setter
    def quality_score(self, value):
        self._quality_score = self._coerce_float(value)

    @property
    def growth_score(self):
        return self._growth_score

    @growth_score.setter
    def growth_score(self, value):
        self._growth_score = self._coerce_float(value)

    @property
    def momentum_score(self):
        return self._momentum_score

    @momentum_score.setter
    def momentum_score(self, value):
        self._momentum_score = self._coerce_float(value)

    @property
    def overall_score(self):
        return self._overall_score

    @overall_score.setter
    def overall_score(self, value):
        self._overall_score = self._coerce_float(value)

    def as_dict(self):
        return {
            "ticker": self.ticker,
            "value_score": self.value_score,
            "quality_score": self.quality_score,
            "growth_score": self.growth_score,
            "momentum_score": self.momentum_score,
            "overall_score": self.overall_score,
        }

    def format_for_display(self):
        return (
            f"{self.ticker:<8} "
            f"V={self.value_score:>5.1f} "
            f"Q={self.quality_score:>5.1f} "
            f"G={self.growth_score:>5.1f} "
            f"M={self.momentum_score:>5.1f} "
            f"Overall={self.overall_score:>6.2f}"
        )

    def __str__(self):
        return self.format_for_display()

    def __repr__(self):
        return (
            f"FactorScoreRow(ticker={self.ticker!r}, value_score={self.value_score!r}, "
            f"quality_score={self.quality_score!r}, growth_score={self.growth_score!r}, "
            f"momentum_score={self.momentum_score!r}, overall_score={self.overall_score!r})"
        )

    def __eq__(self, other):
        return isinstance(other, FactorScoreRow) and self.as_dict() == other.as_dict()


def load_factor_scores(db_path="InvestmentAdvisor.db"):
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                ticker,
                value_score,
                quality_score,
                growth_score,
                momentum_score,
                overall_score
            FROM analytics_scores
            ORDER BY overall_score DESC
            """
        )
        return [
            FactorScoreRow(
                ticker=row[0],
                value_score=row[1],
                quality_score=row[2],
                growth_score=row[3],
                momentum_score=row[4],
                overall_score=row[5],
            )
            for row in cursor.fetchall()
        ]
    finally:
        conn.close()


if __name__ == "__main__":
    print("\nFACTOR SCORES\n")
    for record in load_factor_scores():
        print(record.format_for_display())
