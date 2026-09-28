import argparse, sqlite3
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
DB=ROOT/"InvestmentAdvisor.db"
APPROVED=("APPROVED","ACTIVE","READY","BUY","SELECTED")
def exists(c,n): return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(n,)).fetchone() is not None
def cols(c,n): return {r[1] for r in c.execute(f'PRAGMA table_info("{n}")')}
def pick(cs,names,required=True):
 v=next((x for x in names if x in cs),None)
 if required and not v: raise RuntimeError("Missing supported column: "+", ".join(names))
 return v
def policy(c,n,d):
 if exists(c,"advisor_policy"):
  r=c.execute("SELECT policy_value FROM advisor_policy WHERE policy_name=?",(n,)).fetchone()
  if r:return float(r[0])
 return d
def main():
 p=argparse.ArgumentParser(description="Approved-research buy engine");p.add_argument("--database",type=Path,default=DB);p.add_argument("--date");p.add_argument("--limit",type=int,default=10);p.add_argument("--full-refresh",action="store_true");a=p.parse_args()
 with sqlite3.connect(a.database.resolve()) as c:
  for t in ("portfolio_dashboard","research_queue"):
   if not exists(c,t):raise RuntimeError(f"{t} is required; no fallback to unapproved scores")
  c.execute("CREATE TABLE IF NOT EXISTS advisor_recommendations(recommendation_date TEXT,recommendation_type TEXT,ticker TEXT,current_weight_pct REAL,target_weight_pct REAL,weight_gap_pct REAL,recommendation_amount REAL,score REAL,priority_score REAL,rationale TEXT,status TEXT DEFAULT 'PROPOSED',source TEXT,created_timestamp TEXT,PRIMARY KEY(recommendation_date,recommendation_type,ticker))")
  d=a.date or c.execute("SELECT MAX(dashboard_date) FROM portfolio_dashboard").fetchone()[0];cs=cols(c,"research_queue");tc=pick(cs,["ticker","symbol"]);sc=pick(cs,["status","research_status","approval_status"]);score=pick(cs,["score","overall_score","composite_score","priority_score"],False);thesis=pick(cs,["thesis","investment_thesis","notes","rationale","summary"],False)
  marks=','.join('?'*len(APPROVED));sx=f'CAST("{score}" AS REAL)' if score else 'NULL';tx=f'"{thesis}"' if thesis else 'NULL';q=f'SELECT UPPER(TRIM("{tc}")),{sx},{tx},UPPER(TRIM("{sc}")) FROM research_queue WHERE UPPER(TRIM("{sc}")) IN ({marks})';approved=c.execute(q,APPROVED).fetchall()
  held={r[0]:r[1] for r in c.execute("SELECT UPPER(ticker),account_weight_pct FROM portfolio_dashboard WHERE dashboard_date=? AND asset_type='SECURITY'",(d,))};targets={}
  if exists(c,"portfolio_targets"):targets={r[0]:r[1:] for r in c.execute("SELECT UPPER(ticker),target_weight_pct,max_weight_pct,allow_buy,thesis_status,target_group FROM portfolio_targets")}
  cash,total=c.execute("SELECT SUM(CASE WHEN asset_type='CASH' THEN market_value ELSE 0 END),MAX(total_account_value) FROM portfolio_dashboard WHERE dashboard_date=?",(d,)).fetchone();deploy=max(0,cash-total*policy(c,"reserve_cash_pct",10)/100);cap=policy(c,"max_new_position_pct",5);minimum=policy(c,"minimum_trade_amount",100);cand=[]
  for t,s,why,status in approved:
   cur=float(held.get(t,0));tar=targets.get(t)
   if tar:
    tw,mw,buy,ts,g=tar
    if not buy or str(ts).upper() not in ("APPROVED","ACTIVE"):continue
    room=max(0,min(tw-cur,mw-cur))*total/100
   else:tw=cap;g="RESEARCH_CANDIDATE";room=max(0,cap-cur)*total/100
   if room>=minimum:cand.append((t,cur,float(tw),room,float(s or 0),why,status,g))
  cand=sorted(cand,key=lambda x:x[4],reverse=True)[:a.limit];den=sum(max(1,x[4]) for x in cand);now=datetime.now().strftime("%Y-%m-%d %H:%M:%S");rows=[]
  for t,cur,tw,room,s,why,status,g in cand:
   amt=min(room,deploy*max(1,s)/den if den else 0)
   if amt>=minimum:rows.append((d,"BUY",t,cur,tw,tw-cur,amt,s,s,f"Approved research ({status}); group {g}. "+(str(why)[:240] if why else ""),"PROPOSED","APPROVED_RESEARCH_BUY_V2",now))
  c.execute("DELETE FROM advisor_recommendations WHERE recommendation_date=? AND recommendation_type='BUY'",(d,));c.executemany("INSERT OR REPLACE INTO advisor_recommendations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",rows);c.commit()
 print(f"APPROVED-RESEARCH BUY COMPLETE | {len(rows)} buys | deployable ${deploy:,.2f}")
 for r in rows:print(f"BUY {r[2]:<8} ${r[6]:>10,.2f} | {r[9]}")
if __name__=="__main__":main()
