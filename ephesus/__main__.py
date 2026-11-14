import argparse
import json
import os
from pathlib import Path
import sys

from .evidence import CASES, load_case
from .provider import ClaudeProvider
from .runner import investigate


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the standalone EPHESUS Claude workflow")
    parser.add_argument("--case", choices=CASES, default=CASES[0])
    parser.add_argument("--model", default=os.environ.get("EPHESUS_MODEL"),
                        help="Exact available Claude model ID. Defaults to EPHESUS_MODEL.")
    parser.add_argument("--output", type=Path, help="Save the run record to a new JSON file")
    args = parser.parse_args(argv)
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key or not args.model:
        parser.error("Set ANTHROPIC_API_KEY and pass --model or set EPHESUS_MODEL. No demo fallback.")
    try:
        case = load_case(args.case)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            # Reserve the target before incurring provider cost.
            with args.output.open("x", encoding="utf-8") as handle:
                result = investigate(case, ClaudeProvider(key, args.model))
                json.dump(result, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
        else:
            result = investigate(case, ClaudeProvider(key, args.model))
            print(json.dumps(result, indent=2, ensure_ascii=False))
    except (OSError, ValueError, KeyError) as exc:
        print(f"Unable to complete local setup or save the run ({type(exc).__name__}).",
              file=sys.stderr)
        return 2
    if result["status"] != "completed":
        print(f"Run incomplete: {result['error']}", file=sys.stderr)
        return 1
    if args.output:
        print(f"Completed live investigation. Report and trace saved to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
