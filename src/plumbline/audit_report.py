"""Print the GuideLLM audit table from results/guidellm_audit.json.

    python -m plumbline.audit_report results/guidellm_audit.json
"""

import json
import sys


def avg(runs: list, key: str, stat: str) -> float:
    return sum(r[key][stat] for r in runs) / len(runs)


def main(path: str) -> None:
    data = json.loads(open(path).read())
    by_scenario: dict = {}
    for r in data["runs"]:
        by_scenario.setdefault(r["scenario"], []).append(r)

    print("TTFT (seconds). 'sent' = truth measured from when the tool actually sent the request;")
    print("'intended' = truth measured from when the tool's own schedule said to send it.\n")
    print("| scenario | n/trial | tool p50 | truth(sent) p50 | tool p99 | truth(sent) p99 | "
          "truth(intended) p99 | tool dispatch delay p99 |")
    print("|---|---|---|---|---|---|---|---|")
    for name, runs in by_scenario.items():
        n = sum(r["n"] for r in runs) / len(runs)
        print(f"| {name} | {n:.0f} | {avg(runs,'tool_ttft','p50'):.3f} | "
              f"{avg(runs,'truth_ttft_sent','p50'):.3f} | {avg(runs,'tool_ttft','p99'):.3f} | "
              f"{avg(runs,'truth_ttft_sent','p99'):.3f} | "
              f"{avg(runs,'truth_ttft_intended','p99'):.3f} | "
              f"{avg(runs,'tool_dispatch_delay','p99'):.3f} |")

    print("\nITL and TPOT (milliseconds, p50). Truth ITL = (last token - first token)/(N-1).\n")
    print("| scenario | tool ITL | truth ITL | tool TPOT | TPOT / truth ITL |")
    print("|---|---|---|---|---|")
    for name, runs in by_scenario.items():
        itl_t, itl_x, tpot = (avg(runs, "tool_itl", "p50"), avg(runs, "truth_itl", "p50"),
                              avg(runs, "tool_tpot", "p50"))
        print(f"| {name} | {itl_t*1000:.2f} | {itl_x*1000:.2f} | {tpot*1000:.2f} | "
              f"{tpot/itl_x:.2f}x |")

    matched = sum(r["matched"] for r in data["runs"])
    tool_ok = sum(r["tool_successful"] for r in data["runs"])
    print(f"\nMatched {matched} of {tool_ok} successful tool requests to server records.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "results/guidellm_audit.json")
