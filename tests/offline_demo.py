"""Scripted protocol walkthrough. Never a benchmark or model performance result."""

import json
from .fixtures import ScriptedProvider
from ephesus.evidence import CASES, load_case
from ephesus.runner import investigate


def main():
    records = [investigate(load_case(case_id), ScriptedProvider()) for case_id in CASES]
    print(json.dumps({"notice": "Offline scripted fixture. No AI inference or measured quality.",
                      "runs": records}, indent=2))
    return int(any(r["status"] != "completed" for r in records))


if __name__ == "__main__":
    raise SystemExit(main())
