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

def setup(c):
 c.execute("""CREATE TABLE IF NOT EXISTS advisor_trade_plan(plan_date TEXT NOT NULL,sequence INTEGER NOT NULL,ticker TEXT NOT NULL,action TEXT NOT NULL,amount REAL NOT NULL,funding_source TEXT,expected_cash_after REAL,priority_score REAL,rationale TEXT,status TEXT NOT NULL DEFAULT 'PROPOSED',created_timestamp TEXT NOT NULL,PRIMARY KEY(plan_date,sequence))""")
def main():
 p=argparse.ArgumentParser(); p.add_argument('--database',type=Path,default=DEFAULT_DB); p.add_argument('--date'); p.add_argument('--full-refresh',action='store_true'); p.add_argument('--minimum-trade',type=float,default=100); a=p.parse_args()
 with sqlite3.connect(a.database.resolve()) as c:
  for t in ['portfolio_dashboard','advisor_recommendations']:
   if not exists(c,t): raise RuntimeError(f'{t} is required')
  setup(c); d=a.date or latest(c); cash,total=c.execute("SELECT COALESCE(SUM(CASE WHEN asset_type='CASH' THEN market_value END),0),MAX(total_account_value) FROM portfolio_dashboard WHERE dashboard_date=?",(d,)).fetchone()
  recs=c.execute("""SELECT recommendation_type,ticker,recommendation_amount,priority_score,rationale FROM advisor_recommendations WHERE recommendation_date=? AND status='PROPOSED' ORDER BY CASE WHEN recommendation_amount<0 THEN 0 ELSE 1 END,priority_score DESC""",(d,)).fetchall()
  sells={}; buys={}
  for typ,t,amt,pri,why in recs:
   if t=='CASH' or abs(amt)<a.minimum_trade: continue
   bucket=sells if amt<0 else buys
   old=bucket.get(t)
   if old is None or pri>old[1]: bucket[t]=(abs(float(amt)),float(pri),why,typ)
  available=float(cash)+sum(x[0] for x in sells.values()); rows=[]; seq=1; running=float(cash); now=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
  for t,(amt,pri,why,typ) in sorted(sells.items(),key=lambda x:-x[1][1]):
   running+=amt; rows.append((d,seq,t,'SELL',-amt,'POSITION_SALE',running,pri,why,'PROPOSED',now)); seq+=1
  for t,(requested,pri,why,typ) in sorted(buys.items(),key=lambda x:-x[1][1]):
   amt=min(requested,max(0,running));
   if amt<a.minimum_trade: continue
   running-=amt; rows.append((d,seq,t,'BUY',amt,'CASH_AND_SALES',running,pri,why,'PROPOSED',now)); seq+=1
  if a.full_refresh:c.execute('DELETE FROM advisor_trade_plan WHERE plan_date=?',(d,))
  c.executemany("""INSERT INTO advisor_trade_plan VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(plan_date,sequence) DO UPDATE SET ticker=excluded.ticker,action=excluded.action,amount=excluded.amount,funding_source=excluded.funding_source,expected_cash_after=excluded.expected_cash_after,priority_score=excluded.priority_score,rationale=excluded.rationale,status='PROPOSED',created_timestamp=excluded.created_timestamp""",rows); c.commit()
 print(f'TRADE PLAN | {d} | {len(rows)} trades | ending cash ${running:,.2f}')
 for r in rows: print(f'{r[1]:>2} {r[3]:<4} {r[2]:<8} ${r[4]:>12,.2f} cash after ${r[6]:>12,.2f}')
if __name__=='__main__': main()
