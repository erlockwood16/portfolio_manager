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
 c.execute("""CREATE TABLE IF NOT EXISTS advisor_sector_targets(sector TEXT PRIMARY KEY,min_weight_pct REAL NOT NULL,target_weight_pct REAL NOT NULL,max_weight_pct REAL NOT NULL,allow_buy INTEGER NOT NULL DEFAULT 1,allow_sell INTEGER NOT NULL DEFAULT 1,notes TEXT,source TEXT NOT NULL,updated_timestamp TEXT NOT NULL)""")
def main():
 p=argparse.ArgumentParser(); p.add_argument('--database',type=Path,default=DEFAULT_DB); p.add_argument('--seed-from-current',action='store_true'); p.add_argument('--cash-target',type=float,default=10); p.add_argument('--band',type=float,default=3); a=p.parse_args()
 with sqlite3.connect(a.database.resolve()) as c:
  if not exists(c,'portfolio_sector_allocation'): raise RuntimeError('portfolio_sector_allocation is required')
  setup(c); d=c.execute('SELECT MAX(allocation_date) FROM portfolio_sector_allocation').fetchone()[0]; data=c.execute('SELECT sector,account_weight_pct FROM portfolio_sector_allocation WHERE allocation_date=?',(d,)).fetchall()
  if not data: raise RuntimeError('No sector allocation rows')
  invested=sum(float(x[1]) for x in data); scale=(100-a.cash_target)/invested if invested else 0; now=datetime.now().strftime('%Y-%m-%d %H:%M:%S'); rows=[]
  for s,w in data:
   target=float(w)*scale; rows.append((s,max(0,target-a.band),target,min(100,target+a.band),1,1,'Seeded from current allocation; review manually','CURRENT_ALLOCATION_SEED',now))
  rows.append(('CASH',max(0,a.cash_target-a.band),a.cash_target,min(100,a.cash_target+a.band),1,1,'Strategic liquidity target','POLICY',now))
  c.executemany("""INSERT INTO advisor_sector_targets VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(sector) DO UPDATE SET min_weight_pct=excluded.min_weight_pct,target_weight_pct=excluded.target_weight_pct,max_weight_pct=excluded.max_weight_pct,allow_buy=excluded.allow_buy,allow_sell=excluded.allow_sell,notes=excluded.notes,source=excluded.source,updated_timestamp=excluded.updated_timestamp""",rows); c.commit()
 print(f'SECTOR TARGETS COMPLETE | total {sum(r[2] for r in rows):.2f}%')
 for r in sorted(rows,key=lambda x:-x[2]): print(f'{r[0]:<35} {r[1]:6.2f} {r[2]:7.2f} {r[3]:7.2f}')
if __name__=='__main__': main()
