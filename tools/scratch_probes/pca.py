import sys, csv, math; sys.path.insert(0,'.')
from backend.domain.card_model import DETAIL_ATTRS
rows=[r for r in csv.DictReader(open('data/fc26_real_foundation/players.csv'))
      if r['position_primary'] not in ('GK','')]
attrs=[a for a in DETAIL_ATTRS]
X=[]
for r in rows:
    try: X.append([float(r[a]) for a in attrs])
    except (ValueError,KeyError): pass
n=len(X); m=len(attrs)
mean=[sum(row[j] for row in X)/n for j in range(m)]
sd=[ (sum((row[j]-mean[j])**2 for row in X)/n)**0.5 or 1.0 for j in range(m)]
Z=[[(row[j]-mean[j])/sd[j] for j in range(m)] for row in X]
# covariance (=correlation since standardized)
C=[[sum(Z[i][a]*Z[i][b] for i in range(n))/n for b in range(m)] for a in range(m)]
# power iteration for PC1
v=[1.0]*m
for _ in range(300):
    w=[sum(C[a][b]*v[b] for b in range(m)) for a in range(m)]
    nrm=math.sqrt(sum(x*x for x in w)) or 1.0
    v=[x/nrm for x in w]
lam=sum(v[a]*sum(C[a][b]*v[b] for b in range(m)) for a in range(m))
print(f"n={n} attrs={m}")
print(f"PC1 eigenvalue = {lam:.2f}  -> explains {lam/m:.1%} of total attribute variance")
print("mean |pairwise correlation| =", round(sum(abs(C[a][b]) for a in range(m) for b in range(m) if a!=b)/(m*m-m),3))
# correlation of PC1 score with OVR
ovr=[]
k=0
for r in rows:
    try:
        [float(r[a]) for a in attrs]; ovr.append(float(r['overall_rating']))
    except (ValueError,KeyError): pass
pc1=[sum(Z[i][j]*v[j] for j in range(m)) for i in range(n)]
def pear(x,y):
    mx=sum(x)/len(x); my=sum(y)/len(y)
    return sum((a-mx)*(b-my) for a,b in zip(x,y))/((sum((a-mx)**2 for a in x)*sum((b-my)**2 for b in y))**0.5)
print("corr(PC1, OVR) =", round(abs(pear(pc1,ovr)),3))
