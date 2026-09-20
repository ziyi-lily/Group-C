#!/usr/bin/env python3
"""
PE6201 · A2 — ENTRY POINT
=====================================================================
    python run_eval.py                 the whole evaluation set, graded
    python run_eval.py CLM-8842        one case, every turn shown
    python run_eval.py --prompt        what the model is told, and its size
    python run_eval.py --prompt-diff   v1 against v2, sizes side by side
    python run_eval.py --sequential    the same set, one call per turn (D2c)
    python run_eval.py --list          every case and its label

>>> THIS IS WHAT A MARKER RUNS. <<<
Clone, `python run_eval.py`, numbers come back. No key, no network, no
arguments. If that does not work in a clean folder, D5(a) has failed
and Technical Execution is capped — so test it the way a marker will:
clone this repository into a FRESH folder and run it there. "Works on
my laptop" has caught out every cohort.
=====================================================================
"""
import json
import os
import sys

PE6201_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SHARED_RUNTIME = os.path.join(PE6201_ROOT, "shared_runtime")
if SHARED_RUNTIME not in sys.path:
    sys.path.insert(0, SHARED_RUNTIME)

import config
from harness import (load_cases, load_key, report, run_set, is_negative)


def _banner():
    print()
    print(config.summary())
    print("data: %s" % config.data_root())


def _list_cases():
    key = load_key()
    cases = load_cases()
    print("\n  %-12s %-22s %-32s %s"
          % ("CASE", "EXPECTED", "TRIGGER / FAMILY", "TRIALS"))
    print("  " + "-" * 84)
    n_neg = 0
    for cid in cases:
        e = key.get(cid)
        if e is None:
            print("  %-12s %s" % (cid, "!! NO LABEL IN THE ANSWER KEY !!"))
            continue
        neg = is_negative(e)
        n_neg += neg
        print("  %-12s %-22s %-32s %d%s"
              % (cid, e["expected_decision"],
                 e.get("trigger") or e.get("family", ""),
                 3 if neg else 1, "   <- negative" if neg else ""))
    unlabelled = [c for c in cases if c not in key]
    orphans = [c for c in key if c not in cases]
    trials = sum(3 if is_negative(key[c]) else 1 for c in cases if c in key)
    print("  " + "-" * 84)
    print("  %d cases, %d negative, %d trials per model" % (len(cases), n_neg,
                                                            trials))
    print()
    print("  D4 asks for 30-50 cases with 6-10 negative.")
    print("    cases     %d  %s" % (len(cases),
                                    "OK" if 30 <= len(cases) <= 50
                                    else "<- not there yet"))
    print("    negative  %d  %s" % (n_neg,
                                    "OK" if 6 <= n_neg <= 10
                                    else "<- outside the 6-10 band"))
    if unlabelled:
        print("\n  !! %d claim(s) with no answer-key row: %s"
              % (len(unlabelled), ", ".join(unlabelled)))
        print("     Add a row to expected_outcomes_A.json, or they are skipped.")
    if orphans:
        print("\n  !! %d answer-key row(s) with no claim: %s"
              % (len(orphans), ", ".join(orphans)))
    print()
    return 0


def _one_case(case_id):
    print()
    print("-" * 70)
    print("  %s — every turn" % case_id)
    print("-" * 70)
    results, queue = run_set([case_id], trials_for=lambda e: 1, verbose=True)
    if not results:
        print("\n  %s is not in the work queue, or has no answer-key row.\n"
              % case_id)
        return 1
    r = results[0]
    print()
    print("  DECISION RECORD")
    print(json.dumps(r["record"], indent=2, default=str)[:3000])
    print()
    print("  CODE CHECK   %s" % ("PASS" if r["passed"] else "FAIL"))
    for f in r["fails"]:
        print("      %s" % f)
    print()
    print("  JUDGEMENT CHECK — not automated. A person, or a second model,")
    print("  reads the reason above and rules on each item:")
    for item in queue[0]["must_record"]:
        print("      [ ] %s" % item)
    print()
    return 0 if r["passed"] else 1


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("-")]
    flags = {a for a in argv[1:] if a.startswith("-")}

    if "--sequential" in flags:
        # D2(c): the before picture. Same calls, one per turn.
        config.CALL_MODE = "sequential"
    if "--parallel" in flags:
        config.CALL_MODE = "parallel"

    _banner()

    if "--prompt" in flags:
        import prompt
        print()
        prompt.audit()
        return 0

    if "--prompt-diff" in flags:
        import prompt
        prompt.compare_versions()
        return 0

    if "--list" in flags:
        return _list_cases()

    if args:
        return _one_case(args[0])

    # ---- the whole set -----------------------------------------------
    key = load_key()
    cases = [c for c in load_cases() if c in key]
    n_neg = sum(1 for c in cases if is_negative(key[c]))
    trials = sum(3 if is_negative(key[c]) else 1 for c in cases)

    print("\n  Running %d case(s), %d negative — %d trials "
          "(1 per ordinary case, 3 per negative)."
          % (len(cases), n_neg, trials))
    if config.BACKEND == "scripted":
        print("  Scripted backend: free, deterministic, no key, no network.")

    results, queue = run_set(cases)
    summary = report(results)

    filename = "results_%s_%s_%s_%s.json" % (
        config.BACKEND,
        (
            config.MODEL.split("/")[-1]
            if config.BACKEND == "live"
            else "planner"
        ),
        config.CALL_MODE,
        config.PROMPT_VERSION,
    )
    
    output_directory = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "results"))
    os.makedirs(output_directory, exist_ok=True)
    out = os.path.join(output_directory, filename)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"config": config.summary(),
                   "summary": summary,
                   "results": results,
                   "judgement_queue": queue}, fh, indent=2, default=str)
    print("  Wrote %s — commit it. Every number in the report comes from" % out)
    print("  a file like this one, and a marker reads it alongside the report.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
