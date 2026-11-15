"""Print a random sample of questions per source (seeded)."""
import json, collections, random, sys
Q = "./stoa/data/junction-dataset/questions.jsonl"
rows = [json.loads(l) for l in open(Q)]
random.seed(7)
by = collections.defaultdict(list)
for r in rows: by[r["path"].split("/")[1]].append(r)
n = {"cubicasa5k": 26, "swiss_dwellings": 40, "ifc_models": 45, "ifc_bench": 22, "opening_design": 30}
for s, rs in sorted(by.items()):
    print("==", s)
    for r in random.sample(rs, n[s]):
        print(f'{r["path"].split("/",2)[2][-46:]} | {r["question"]} | {str(r["answer"])[:160]} | {r["unit"]} | {r["type"]}')
