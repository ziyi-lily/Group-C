"""
PE6201 · A2 — THE EVALUATION HARNESS  (D4, D5)
=====================================================================
Load the answer key, run cases, grade them, report.

--------------------------------------------------------------------
THE TWO KINDS OF CHECK, AND WHY BOTH ARE NEEDED

A CODE CHECK compares the answer with the answer key.
    decision == expected_decision;  trigger == expected trigger;
    the gated action fired exactly once, or not at all.
    No model, no person, no opinion. Free, instant, identical every run.
    It is what produces the number.

A JUDGEMENT CHECK has someone READ the record and decide.
    "Does the reason actually name the claim total and the amount
     remaining, or does it only say 'cannot be decided at this level'?"
    A person can do it. A second model can do it. Same kind of check —
    the only difference is who grades.

WHY BOTH. With three possible outcomes, a coin flip scores 33% on the
code check alone, and an agent can reach the right decision for
entirely the wrong reason without the code check noticing. `must_record`
is what stops a lucky run counting as a good one.

`prepare_judgement_check` below does NOT grade. It builds the queue a
human — or a second model — works through. If a model grades, name it,
commit the grading prompt, and use a DIFFERENT model from the one being
graded. A model marking its own homework is not a measurement.

--------------------------------------------------------------------
TRIALS (D4). One trial per ordinary case; THREE per negative case,
because negatives are the ones that flip between runs and a single
trial cannot tell a real refusal from a lucky one.

A pass rate reported without its trial count is not a measurement, so
every number this file prints carries one.
=====================================================================
"""
import json
import os
import statistics
from collections import Counter

import config
from agent import run_case

NEGATIVE_DECISIONS = ("escalate", "request_document", "request_information")


# =====================================================================
# LOADING
# =====================================================================
def load_key(problem=None):
    """The answer key — OURS, not the instructor's, once extended.

    Starts as the 15 shipped rows and grows by one per case the team
    writes. Same file throughout: the harness joins on case_id and does
    not care which rows were shipped and which we added.
    """
    problem = problem or config.PROBLEM
    path = os.path.join(config.data_root(),
                        "expected_outcomes_%s.json" % problem)
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh)
    return {r["case_id"]: r for r in rows}


def load_cases(problem=None):
    """Every claim id in the work queue, in file order."""
    problem = problem or config.PROBLEM
    path = os.path.join(config.data_root(), "data_%s" % problem, "claims.json")
    with open(path, encoding="utf-8") as fh:
        return [r["claim_id"] for r in json.load(fh)]


def is_negative(expected):
    """A negative case is one whose correct outcome is anything except
    the act — so an ask or an escalate."""
    return bool(expected) and \
        expected.get("expected_decision") in NEGATIVE_DECISIONS


def default_trials(expected):
    return 3 if is_negative(expected) else 1


# =====================================================================
# THE CODE CHECK
# =====================================================================
def code_check(record, expected):
    """Deterministic comparison. Returns (passed, [reasons it failed]).

    Note what is compared and what is NOT. The DECISION, its single
    TRIGGER, and whether the gated action fired are compared. The
    wording is not; the turn count is not; the cost is not. Two agents
    can both be right and cost very different amounts, and that
    difference is the subject of D6, not of D4.
    """
    fails = []

    got, want = record.get("decision"), expected.get("expected_decision")
    if got != want:
        fails.append("decision %r, expected %r" % (got, want))

    # An escalation must escalate FOR THE RIGHT REASON. A run that
    # reaches the right outcome by the wrong trigger is not a pass — it
    # got there by luck, and it will not get there next time.
    if expected.get("trigger"):
        if record.get("trigger") != expected["trigger"]:
            fails.append("trigger %r, expected %r"
                         % (record.get("trigger"), expected["trigger"]))

    # THE GATED ACTION FIRED EXACTLY ONCE, OR NOT AT ALL. An acting
    # outcome must pass the gate once; a non-acting outcome must never
    # reach it. A run that reached the gate twice is a bug even when the
    # decision came out right.
    gated = record.get("gated_calls", 0)
    if want == "approve_in_principle" and gated != 1:
        fails.append("gated action fired %d times, expected exactly 1" % gated)
    if want in NEGATIVE_DECISIONS and gated != 0:
        fails.append("gated action fired %d times on a non-acting outcome, "
                     "expected 0" % gated)

    return (not fails), fails


# =====================================================================
# THE JUDGEMENT CHECK
# =====================================================================
def prepare_judgement_check(record, expected):
    """Build ONE item for a human — or a second model — to rule on.

    This deliberately decides nothing. `must_record` items are written
    in English and a substring match would be theatre, not a check: the
    Class 4 demonstration had a credulous agent score 3/24 instead of
    0/24 because one check looked for a date that appeared in an answer
    that was wrong about everything else. Check the thing you care
    about, not a string that usually accompanies it.
    """
    return {
        "case_id": record["case_id"],
        "decision": record.get("decision"),
        "trigger": record.get("trigger"),
        "reason": record.get("reason", ""),
        "must_record": expected.get("must_record", []),
        "verdicts": [None] * len(expected.get("must_record", [])),
        "graded_by": None,       # "person: <name>" | "model: <name>"
        "graded_on": None,
    }


# =====================================================================
# RUNNING THE SET
# =====================================================================
def run_set(case_ids=None, trials_for=None, verbose=False, log=True):
    """Run cases and grade them.

    `trials_for(expected) -> int` decides how many trials each case
    gets. The default is D4's rule: one for ordinary, three for
    negative.
    """
    key = load_key()
    case_ids = case_ids or load_cases()
    trials_for = trials_for or default_trials

    results, judgement_queue = [], []

    for cid in case_ids:
        expected = key.get(cid)
        if expected is None:
            # check_my_data.py catches this before you get here. If you
            # are seeing it, a case was added to claims.json without a
            # label in expected_outcomes_A.json.
            print("  SKIP %s — no label in the answer key" % cid)
            continue

        for trial in range(1, trials_for(expected) + 1):
            record = run_case(cid, verbose=verbose, log=log)
            passed, fails = code_check(record, expected)
            results.append({
                "case_id": cid,
                "trial": trial,
                "passed": passed,
                "fails": fails,
                "family": expected.get("family"),
                "negative": is_negative(expected),
                "check": "code",
                "record": record,
            })
            if trial == 1:
                judgement_queue.append(prepare_judgement_check(record, expected))

    return results, judgement_queue


# =====================================================================
# REPORTING
# =====================================================================
def report(results, title="RESULTS"):
    """The result table. EVERY pass rate carries its trial count."""
    if not results:
        print("\n  Nothing ran.\n")
        return {}

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    negs = [r for r in results if r["negative"]]
    neg_passed = sum(1 for r in negs if r["passed"])
    turns = [r["record"]["turns"] for r in results]
    cost = sum(r["record"]["cost_usd"] for r in results)
    tokens_in = sum(r["record"]["tokens_in"] for r in results)

    print()
    print("=" * 70)
    print("  %s   %d of %d trials passed the code check   (%.1f%%)"
          % (title, passed, total, 100.0 * passed / total))
    print("=" * 70)
    print("  backend             %s" % results[0]["record"]["backend"])
    if results[0]["record"].get("model"):
        print("  model               %s" % results[0]["record"]["model"])
    print("  prompt version      %s" % results[0]["record"]["prompt_version"])
    print("  call mode           %s" % results[0]["record"]["call_mode"])
    print("  cases               %d" % len({r["case_id"] for r in results}))
    print("  trials              %d" % total)
    print("  negative trials     %d of %d passed  (%.1f%%)   <- the number "
          "that matters"
          % (neg_passed, len(negs),
             100.0 * neg_passed / len(negs) if negs else 0))
    print()
    print("  TURN DISTRIBUTION   (D7 asks for a distribution, not one number)")
    print("    median            %s" % statistics.median(turns))
    print("    worst case        %s" % max(turns))
    print("    hit the step cap  %d"
          % sum(1 for r in results
                if r["record"]["stopped_by"] == "step_cap"))
    print("    spread            %s"
          % ", ".join("%d turns x%d" % (t, n)
                      for t, n in sorted(Counter(turns).items())))
    print()
    print("  input tokens        %d" % tokens_in)
    print("  total cost          US$%.4f" % cost)

    # D0(b): the implied per-step reliability, worked backwards.
    # You cannot measure s directly; what D4 measures is whether a WHOLE
    # RUN produced the right outcome. s = P^(1/T) is the per-step number
    # consistent with that. It is a DIAGNOSTIC, not a constant.
    p = passed / total
    t_med = statistics.median(turns)
    if p > 0 and t_med:
        s = p ** (1.0 / t_med)
        print()
        print("  IMPLIED PER-STEP RELIABILITY   s = P^(1/T)")
        print("    P = %.3f over a median T = %g turns  ->  s = %.4f"
              % (p, t_med, s))
        print("    at T = 3   -> %.3f      at T = 12  -> %.3f"
              % (s ** 3, s ** 12))
        print("    Same agent, same per-step quality, run success moved by")
        print("    turn count alone. That is why cutting turns is the lever.")
    print()

    failures = [r for r in results if not r["passed"]]
    if failures:
        print("  FAILED TRIALS — each one is either a bug or a wrong label:")
        for r in failures:
            print("    %-12s trial %d  [%s]  last tool: %s"
                  % (r["case_id"], r["trial"], r["family"],
                     r["record"].get("last_tool_before_end")))
            for f in r["fails"]:
                print("        %s" % f)
        print()
        print("  Before fixing the agent, ask whether the LABEL is right.")
        print("  Test: could you justify the label to someone who had never")
        print("  seen our output, using only Appendix A's routing table?")
        print("  If yes, the agent is wrong. If no, the label is.")
        print()
        # D0(b): group failures by the tool call that came immediately
        # before things went wrong. The turn that shows up most often is
        # the weak-step candidate.
        weak = Counter(r["record"].get("last_tool_before_end")
                       for r in failures)
        print("  WEAK-STEP CANDIDATES (tool call immediately before failure):")
        for tool, n in weak.most_common():
            print("      %-28s %d" % (tool, n))
    else:
        print("  Every trial passed the code check.")
        print("  THAT IS HALF THE CHECK. Work through the judgement queue")
        print("  before believing this number — and on the scripted backend")
        print("  it is a test of OUR HARNESS, not of an agent's judgement.")
    print()

    return {
        "backend": results[0]["record"]["backend"],
        "model": results[0]["record"].get("model"),
        "prompt_version": results[0]["record"]["prompt_version"],
        "call_mode": results[0]["record"]["call_mode"],
        "cases": len({r["case_id"] for r in results}),
        "trials": total,
        "passed": passed,
        "pass_rate": passed / total,
        "negative_trials": len(negs),
        "negative_passed": neg_passed,
        "negative_pass_rate": (neg_passed / len(negs)) if negs else None,
        "median_turns": statistics.median(turns),
        "worst_turns": max(turns),
        "hit_step_cap": sum(1 for r in results
                            if r["record"]["stopped_by"] == "step_cap"),
        "tokens_in": tokens_in,
        "tokens_out": sum(r["record"]["tokens_out"] for r in results),
        "cost_usd": round(cost, 6),
    }
