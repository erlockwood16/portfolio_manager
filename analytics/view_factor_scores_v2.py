import sqlite3


class row:
    def __init__(
        self,
        ticker,
        value_score,
        quality_score,
        growth_score,
        momentum_score,
        overall_score,
    ):
        self.ticker = ticker
        self.value_score = float(value_score)
        self.quality_score = float(quality_score)
        self.growth_score = float(growth_score)
        self.momentum_score = float(momentum_score)
        self.overall_score = float(overall_score)

    def __iter__(self):
        yield from (
            self.ticker,
            self.value_score,
            self.quality_score,
            self.growth_score,
            self.momentum_score,
            self.overall_score,
        )

    def as_tuple(self):
        return (
            self.ticker,
            self.value_score,
            self.quality_score,
            self.growth_score,
            self.momentum_score,
            self.overall_score,
        )

    def as_dict(self):
        return {
            "ticker": self.ticker,
            "value_score": self.value_score,
            "quality_score": self.quality_score,
            "growth_score": self.growth_score,
            "momentum_score": self.momentum_score,
            "overall_score": self.overall_score,
        }

    def __str__(self):
        return (
            f"{self.ticker:<8} "
            f"V={self.value_score:6.1f} "
            f"Q={self.quality_score:6.1f} "
            f"G={self.growth_score:6.1f} "
            f"M={self.momentum_score:6.1f} "
            f"Overall={self.overall_score:6.2f}"
        )

    def display(self):
        print(self)


conn = sqlite3.connect("InvestmentAdvisor.db")
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

rows = [row(*record) for record in cursor.fetchall()]

print("\n" + "=" * 80)
print("FACTOR SCORES V2")
print("=" * 80)

for item in rows:
    item.display()

conn.close()
