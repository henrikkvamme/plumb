"""Power, interval and prediction arithmetic for the eval design. No data read. Run: uv run --with numpy python m09_power.py"""
import math, numpy as np
rng = np.random.default_rng(20261114)
def hw(p, n, deff): return 1.96 * math.sqrt(p * (1 - p) * deff / n)
def mde_paired(n, deff, d): return 2.8 * math.sqrt(d * deff / n)   # 80% power, two-sided 5%, d = share of items where the two runs differ
print("A. suite|docs|items|deff|n_eff|95% half-width at p=0.7|paired MDE d=0.10|d=0.20")
S = [("core.cubicasa", 150, 1350, 1.75), ("core.swiss", 100, 1000, 3.27), ("core.ifc", 4, 308, 9.33), ("ladder (per condition)", 100, 800, 2.5),
     ("oracle-new seen", 120, 720, 2.5), ("oracle-new unseen", 120, 720, 2.5), ("resbim", 60, 240, 1.9), ("wild", 40, 200, 2.2), ("unanswerable", 60, 120, 1.3), ("session", 12, 72, 2.5)]
for name, docs, n, deff in S:
    print(f"{name}|{docs}|{n}|{deff}|{n/deff:.0f}|{100*hw(.7,n,deff):.1f}|{100*mde_paired(n,deff,.10):.1f}|{100*mde_paired(n,deff,.20):.1f}")
print("B. sampling SD of the hidden score itself (points): docs x questions | rho=0.1 | 0.3 | 0.5, at p=0.7")
for D, m in [(5, 6), (8, 5), (10, 8), (20, 10)]:
    print(f"{D}x{m}|" + "|".join(f"{100*math.sqrt(.21*(1+(m-1)*r)/(D*m)):.1f}" for r in (.1, .3, .5)))
print("C. expected best-of-K noise gain in units of SE (K runs with no real effect)")
for K in (5, 10, 30, 100): print(K, round(float(np.mean(np.max(rng.standard_normal((20000, K)), axis=1))), 2))
print("D. optimal questions per drawing m* = sqrt((Cd/Cq)*(1-rho)/rho)")
for ratio in (5, 15, 40):
    print(ratio, [round(math.sqrt(ratio * (1 - r) / r), 1) for r in (.106, .13, .3, .5)])
print("E. worked prediction (inputs are ESTIMATES, see design doc)")
cells = ["lookup.V", "count_label.V", "count_symbol.V", "area.V", "model.M", "compound.V", "schedule.V", "count_symbol.R", "area.R", "lookup.S", "count.S", "area.S", "unanswerable"]
k = np.array([196, 190, 150, 170, 180, 96, 34, 62, 40, 28, 12, 6, 84]); n = np.array([200, 200, 200, 200, 200, 120, 40, 120, 120, 40, 40, 30, 120])
deff = np.array([2.5, 2.5, 2.5, 2.5, 5, 2.5, 2.2, 1.9, 1.9, 2.2, 2.2, 2.2, 1.3]); gap = np.array([.01, .02, .10, .05, .03, .12, .10, .10, .10, .15, .10, .05, .10])
scen = {"same generator, new drawings": [.10, .20, .25, .25, .15, 0, 0, 0, 0, 0, 0, 0, .05],
        "compound on clean files": [.05, .05, .10, .15, .20, .30, .05, 0, 0, 0, 0, 0, .10],
        "tricky sheets": [.05, 0, .05, .05, .10, .10, .15, .10, .10, .10, .05, .05, .10],
        "abstention heavy": [.05, 0, .05, .05, .05, .10, .05, .05, .10, .05, .05, .10, .30]}
prior = np.array([.15, .35, .40, .10]); W = np.array(list(scen.values()))
assert np.allclose(W.sum(1), 1)
N = 40000; ne = n / deff; A = rng.beta(1 + k / deff, 1 + (n - k) / deff, size=(N, len(k)))
g = rng.uniform(0, 2, size=(N, 1)); A2 = np.clip(A - g * gap, 0, 1)
sw = rng.dirichlet(prior * 8, size=N); w = sw @ W
H_dev = (w * A).sum(1); H = (w * A2).sum(1)
q = lambda x: [round(100 * float(v), 1) for v in np.quantile(x, [.05, .5, .95])]
print("point estimate, no discount, central weights:", round(100 * float((prior @ W) @ (k / n)), 1))
print("H_dev 5/50/95:", q(H_dev)); print("H_pred (with gap discount) 5/50/95:", q(H))
obs = rng.binomial(40, np.clip(rng.normal(H, np.sqrt(H * (1 - H) * (2.2 - 1) / 40)), 0, 1)) / 40
print("observed hidden score on 8 docs x 5 questions 5/50/95:", q(obs))
for i, s in enumerate(scen): print(s, "|", round(100 * float(W[i] @ (k / n)), 1), "| discounted g=1:", round(100 * float(W[i] @ np.clip(k / n - gap, 0, 1)), 1))
# effect of one change: count_symbol.R from 62/120 to 84/120
k2 = k.copy(); k2[7] = 84; print("after raising count_symbol.R to 84/120, point:", round(100 * float((prior @ W) @ (k2 / n)), 1))
