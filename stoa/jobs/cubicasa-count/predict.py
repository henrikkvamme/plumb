"""Print the count head's reading of one or more plans. Runs on the laptop, with the installed artifacts.

cd stoa && uv run python jobs/cubicasa-count/predict.py --spec e1.json path/to/plan.png ...
"""

from __future__ import annotations

import argparse
from pathlib import Path

from bp.tools.count_head import count_plan, get_model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", default="e1.json")
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    model = get_model(args.spec)
    for path in args.paths:
        counts = count_plan(path, model)
        print(
            f"{path.name}: in_distribution={counts.in_distribution} ood={counts.ood_distance} {counts.latency_ms:.0f} ms"
        )
        for family, head in counts.counts.items():
            mark = "answer" if head.trusted else "abstain"
            print(f"  {family:13} {head.value:3d} p={head.probability:.2f} thr={head.threshold:.2f} {mark}")


if __name__ == "__main__":
    main()
