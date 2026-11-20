import sys, json, math, datetime as dt
sys.path.insert(0, '/tmp/repo/scripts')
import allocator as A, tcal
repo='/tmp/repo'; day='2026-11-19'
S={k:v for k,v in A.sleeves(repo).items() if k.startswith('L')}
spy=A.dclose(repo,'SPY',total_return=True); vix=A.dclose(repo,'VIX')
tcal.START=dt.date(2025,6,2)
rows,W=A.simulate(repo,day,S,spy,vix)
n=len(rows)
contrib={k:0.0 for k in S}; held={k:0 for k in S}
for r,w in zip(rows,W):
    for k,wt in w['weights'].items(): contrib[k]+=wt*S[k].get(r['date'],0.0); held[k]+=1
print('days',n,'gross',round(sum(contrib.values()),2),'rebal cost',round(sum(r['rebal_cost'] for r in rows),2),'turnover/day',round(sum(r['turnover'] for r in rows)/n,3),'avg invested',round(sum(r['invested'] for r in rows)/n,3))
print('%-26s %7s %7s %6s %8s %8s'%('sleeve','ownSum','contrib','held','avgW','retWhenHeld/day'))
for k in sorted(S):
    own=sum(S[k].get(r['date'],0.0) for r in rows)
    wh=[S[k].get(r['date'],0.0) for r,w in zip(rows,W) if k in w['weights']]
    nh=[S[k].get(r['date'],0.0) for r,w in zip(rows,W) if k not in w['weights']]
    print('%-26s %7.2f %7.2f %6d %8.3f %8.4f vs notheld %8.4f'%(k,own,contrib[k],held[k],sum(w['weights'].get(k,0) for w in W)/n,sum(wh)/len(wh) if wh else 0,sum(nh)/len(nh) if nh else 0))
# weight persistence: avg days a position is held consecutively
import statistics
runs=[]
for k in S:
    c=0
    for w in W:
        if k in w['weights']: c+=1
        elif c: runs.append(c); c=0
    if c: runs.append(c)
print('median holding run (days)',statistics.median(runs),'mean',round(sum(runs)/len(runs),1),'n runs',len(runs))
# variants: (a) posterior mean instead of Thompson draw; (b) no-regime; (c) equal weight scaled
import random
def variant(name, patch):
    patch(); rows2,W2=A.simulate(repo,day,S,spy,vix)
    xs=[r['ai'] for r in rows2]; cum=1;peak=1;dd=0
    for x in xs: cum*=1+x/100; peak=max(peak,cum); dd=max(dd,1-cum/peak)
    m=sum(xs)/len(xs); sd=math.sqrt(sum((x-m)**2 for x in xs)/(len(xs)-1))
    print('%-34s total %6.2f sharpe %5.2f dd %5.2f invested %.3f turn/day %.3f cost %.2f'%(name,(cum-1)*100,m/sd*math.sqrt(252),dd*100,sum(r['invested'] for r in rows2)/len(rows2),sum(r['turnover'] for r in rows2)/len(rows2),sum(r['rebal_cost'] for r in rows2)))
variant('as is (vol breaker)', lambda: None)
class G:
    def __init__(s,h): pass
    def gauss(s,mu,sd): return mu
orig=random.Random
def p1(): A.random.Random=G
variant('posterior mean (no sampling)', p1)
A.random.Random=orig
def p2(): setattr(A,'K_REG',1e9)
variant('no regime split', p2)
A.K_REG=20
def p3(): A.random.Random=G; setattr(A,'K_REG',1e9)
variant('mean + no regime', p3)
A.random.Random=orig; A.K_REG=20
def p4(): setattr(A,'BAND',0.05)
variant('band 5pp', p4); A.BAND=0.02
def p5(): setattr(A,'K_ALL',0)
variant('no shrink to zero', p5); A.K_ALL=30
eq=[sum(S[k].get(r['date'],0.0) for k in S)/len(S) for r in rows]
for sc in (1,0.25):
    cum=1
    for x in eq: cum*=1+sc*x/100
    print('equal weight x',sc,round((cum-1)*100,2))
