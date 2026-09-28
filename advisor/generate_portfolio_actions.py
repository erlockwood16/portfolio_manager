import argparse, sqlite3
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
DB=ROOT/'InvestmentAdvisor.db'
def setup(c): c.executescript(Path(__file__).with_name('advisor_recommendations.sql').read_text())
def latest(c):
 d=c.execute('SELECT MAX(dashboard_date) FROM portfolio_dashboard').fetchone()[0]
 if not d: raise RuntimeError('portfolio_dashboard is empty')
 return d
def policy(c): return dict(c.execute('SELECT policy_name,policy_value FROM advisor_policy'))
def save(c,rows):
 c.executemany("""INSERT INTO advisor_recommendations(recommendation_date,recommendation_type,ticker,current_weight_pct,target_weight_pct,weight_gap_pct,recommendation_amount,score,priority_score,rationale,source,created_timestamp) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(recommendation_date,recommendation_type,ticker) DO UPDATE SET current_weight_pct=excluded.current_weight_pct,target_weight_pct=excluded.target_weight_pct,weight_gap_pct=excluded.weight_gap_pct,recommendation_amount=excluded.recommendation_amount,score=excluded.score,priority_score=excluded.priority_score,rationale=excluded.rationale,status='PROPOSED',source=excluded.source,created_timestamp=excluded.created_timestamp""",rows)
import subprocess,sys
def main():
 p=argparse.ArgumentParser(); p.add_argument('--database',type=Path,default=DB); p.add_argument('--date'); p.add_argument('--full-refresh',action='store_true'); a=p.parse_args(); args=['--database',str(a.database.resolve())]+(['--date',a.date] if a.date else [])+(['--full-refresh'] if a.full_refresh else [])
 for name in ['generate_sell_recommendations.py','generate_rebalance_recommendations.py','generate_buy_recommendations.py']:
  subprocess.run([sys.executable,str(Path(__file__).with_name(name)),*args],check=True,cwd=ROOT)
 with sqlite3.connect(a.database.resolve()) as c:
  setup(c); d=a.date or c.execute('SELECT MAX(recommendation_date) FROM advisor_recommendations').fetchone()[0]; rows=c.execute("SELECT recommendation_type,ticker,recommendation_amount,priority_score,rationale FROM advisor_recommendations WHERE recommendation_date=? AND status='PROPOSED' ORDER BY priority_score DESC",(d,)).fetchall()
 print(f'PORTFOLIO ACTIONS | {d}')
 for typ,ticker,amt,pri,why in rows: print(f'{typ:<10}{ticker:<8}${amt:>12,.2f} priority={pri:>7.2f} | {why}')
 print('Decision support only; review before execution.')
if __name__=='__main__': main()
