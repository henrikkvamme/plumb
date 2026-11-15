import collections
from common import *
rows=[r for r in load() if src(r["path"])=="ifc_models"]
c=collections.Counter(); u={}
for r in rows:
    t=template(r["question"]); c[t]+=1; u[t]=(r["unit"], os.path.splitext(r["path"])[1])
for t,n in c.most_common(): print(n, u[t][0], u[t][1], t[:110], sep="|")
