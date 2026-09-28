import argparse, sqlite3
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
DEFAULT_DB=ROOT/"InvestmentAdvisor.db"
def exists(c,n): return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(n,)).fetchone() is not None
def cols(c,n): return {r[1] for r in c.execute(f'PRAGMA table_info("{n}")')}
def latest(c):
 r=c.execute("SELECT MAX(dashboard_date) FROM portfolio_dashboard").fetchone()[0]
 if not r: raise RuntimeError("portfolio_dashboard is empty")
 return r
import subprocess,sys
def setup(c):
 c.execute("""CREATE TABLE IF NOT EXISTS advisor_actions_v2(action_date TEXT NOT NULL,sequence INTEGER NOT NULL,ticker TEXT NOT NULL,action TEXT NOT NULL,amount REAL NOT NULL,expected_return_pct REAL,priority_score REAL,rationale TEXT,status TEXT NOT NULL DEFAULT 'PROPOSED',created_timestamp TEXT NOT NULL,PRIMARY KEY(action_date,sequence))""")
def main():
 p=argparse.ArgumentParser(); p.add_argument('--database',type=Path,default=DEFAULT_DB); p.add_argument('--date'); p.add_argument('--full-refresh',action='store_true'); a=p.parse_args(); db=a.database.resolve()
 cmd=[sys.executable,str(Path(__file__).with_name('generate_trade_plan.py')),'--database',str(db)]+(['--date',a.date] if a.date else [])+(['--full-refresh'] if a.full_refresh else []); subprocess.run(cmd,check=True,cwd=ROOT)
 with sqlite3.connect(db) as c:
  setup(c)
  d = a.date or c.execute('SELECT MAX(plan_date) FROM advisor_trade_plan').fetchone()[0]
  md = (
      c.execute("""
SELECT MAX(model_date)
FROM advisor_expected_returns
WHERE model_version = 'V3_MULTI_FACTOR_BLEND'
""").fetchone()[0]
      if exists(c, 'advisor_expected_returns')
      else None
  )
  print(f"Trade Plan Date      : {d}")
  print(f"Expected Return Date : {md}")
  check = c.execute("""
SELECT
    ticker,
    model_date,
    model_version,
    expected_return_pct
FROM advisor_expected_returns
WHERE ticker IN (
    'MSFT',
    'PLTR',
    'NOW',
    'QQQ'
)
ORDER BY model_date DESC
""").fetchall()

  print("\nExpected Return Rows:")
  for row in check:
      print(row)

  q = """SELECT p.sequence,p.ticker,p.action,p.amount,p.priority_score,p.rationale,e.expected_return_pct FROM advisor_trade_plan p LEFT JOIN advisor_expected_returns e
      ON e.ticker = p.ticker
     AND e.model_date = ?
     AND e.model_version = 'V3_MULTI_FACTOR_BLEND'
   WHERE p.plan_date=? ORDER BY p.sequence"""
  data = c.execute(q, (md, d)).fetchall()
  now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

  if a.full_refresh:
      c.execute('DELETE FROM advisor_actions_v2 WHERE action_date=?', (d,))

  rows = [(d, seq, t, act, amt, er, pri, why, 'PROPOSED', now) for seq, t, act, amt, pri, why, er in data]
  c.executemany("INSERT OR REPLACE INTO advisor_actions_v2 VALUES(?,?,?,?,?,?,?,?,?,?)", rows)
  c.commit()

  print(f'PORTFOLIO ACTIONS V2 | {d} | {len(rows)} actions')
  for r in rows:
      print(f'{r[1]:>2} {r[3]:<4} {r[2]:<8} ${r[4]:>11,.2f} expected={r[5] if r[5] is not None else "N/A"}')
  print('Decision support only; review all actions before execution.')

if __name__=='__main__': main()
