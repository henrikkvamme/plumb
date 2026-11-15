"""Scorer edge cases measured on questions.jsonl. Run: uv run 08_scorer_edges.py"""
import json, re, collections, time, hashlib, os
t=time.time()
Q='../../data/junction-dataset/questions.jsonl'
rows=[json.loads(l) for l in open(Q) if l.strip()]
print('load_s',round(time.time()-t,2),'rows',len(rows))
def dec(x):
    s=repr(x); return len(s.split('.')[1]) if '.' in s and 'e' not in s else 0
# rounding half-step of the reference larger than the 2% tolerance
c=collections.Counter(); ex=[]
for r in rows:
    if r['type'] in('area','length','volume'):
        a=r['answer']; d=dec(a); half=0.5*10**-d; tol=0.02*abs(a)
        src=r['path'].split('/')[1]
        if half>tol: c[(src,r['type'],d)]+=1; ex.append((a,src))
        if half>0.5*tol: c[('half>1pct',src)]+=1
print('ref_rounding_exceeds_2pct',dict(c),ex[:8])
# integer-valued measures and trailing-zero drop
print('measure_is_int',collections.Counter((r['path'].split('/')[1],r['type']) for r in rows if r['type'] in('area','length','volume') and float(r['answer']).is_integer()))
# count zero share per source
z=collections.Counter();n=collections.Counter()
for r in rows:
    if r['type']=='count':
        s=r['path'].split('/')[1];n[s]+=1;z[s]+=r['answer']==0
print('count_zero',{s:(z[s],n[s]) for s in n})
# text answers: shapes
od=[r for r in rows if r['type']=='text' and 'opening_design' in r['path']]
for r in od: print('OD_TEXT',repr(r['answer'])[:70])
ib=[r['answer'] for r in rows if 'ifc_bench' in r['path']]
pat={'ft_in':r"\d+'\s*-?\s*\d", 'thousand_comma':r"\d,\d{3}\b",'decimal_comma':r"\d,\d{1,2}\b(?!\d)",'sq_m':r"sq\.? ?m|m²|m2",'cu_m':r"cu\.? ?m|m³|m3",'mm':r"\bmm\b",'pct':r"%",'guid':r"\b[0-9A-Za-z_$]{22}\b",'range':r"\d\s*(?:-|to)\s*\d"}
print('IFCB_n',len(ib),{k:sum(bool(re.search(p,a)) for a in ib) for k,p in pat.items()})
nums=[len(re.findall(r"-?\d[\d,]*\.?\d*",a)) for a in ib]; nums.sort()
print('IFCB_numbers_per_answer p10/med/p90/max',nums[len(nums)//10],nums[len(nums)//2],nums[9*len(nums)//10],nums[-1],'zero_numbers',sum(x==0 for x in nums))
print('IFCB_single_number',sum(x==1 for x in nums),'short<=80ch',sum(len(a)<=80 for a in ib))
# independent items: collapse rows with same path+answer+type into twin groups is done elsewhere (63,404)
# data hash cost
t=time.time();h=hashlib.sha256();nb=0;nf=0
for root,_,fs in os.walk('../../data/junction-dataset/data/swiss_dwellings'):
    for f in sorted(fs):
        b=open(os.path.join(root,f),'rb').read();h.update(b);nb+=len(b);nf+=1
print('hash swiss files',nf,'MB',round(nb/1e6),'s',round(time.time()-t,2))
