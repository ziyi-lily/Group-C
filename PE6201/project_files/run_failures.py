#!/usr/bin/env python3
"""
PE6201 · A2 — D7: TWO REPRODUCED FAILURES
=====================================================================
    python run_failures.py            both failures
    python run_failures.py 1          the loop-control failure only

Runs on the SCRIPTED BACKEND. No key, no network, no cost. A failure
built as a deletion from the working agent is deterministic by
construction — that is the whole point of building it that way — so
this reproduces for a marker, for ever, at zero cost.

--------------------------------------------------------------------
THE RULE THAT MAKES THIS COUNT

Each failure is built as a DELETION from the working agent — "the
working agent, minus X" — never as a separately written bad agent.
Putting X back must recover the behaviour. If you write a bad agent
from scratch you can never tell afterwards whether your fix worked or
the rewrite did.

Here, X is a named guardrail, switched off through
`run_case(disable_guards=...)`. The SAME code path runs either way;
the only difference is whether one `if` is allowed to fire.

--------------------------------------------------------------------
WHAT D7 ASKS US TO REPORT, FOR EACH FAILURE

  1  The instrumentation that found it. You cannot report a failure
     you had no way of noticing.
  2  The turn distribution across the WHOLE evaluation set — median,
     worst case, and how many runs hit the cap. One number is not a
     distribution.
  3  The fix, in the layer where it belongs, and WHY THE OTHER LAYERS
     WERE THE WRONG PLACE. That judgement is most of the mark.
  4  Before and after: turns, tokens, cost, AND PASS RATE. A cap that
     stops a runaway also truncates a legitimate long run — so show
     the pass rate did not fall.
=====================================================================
"""
import json
import os
import statistics
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
import tools

import config
from agent import run_case
from harness import load_cases, load_key, code_check, run_set

RULE = "-" * 70


def _bar(title):
    print()
    print("=" * 70)
    print("  " + title)
    print("=" * 70)


def _run_whole_set(disable_guards=(), max_turns=None):
    """The evaluation set, with a guardrail deleted.

    D7 point 4 needs the pass rate on the WHOLE set, not on the one
    case that loops — because the question a step cap has to answer is
    "did you also truncate a legitimate long run?".
    """
    key = load_key()
    cases = [c for c in load_cases() if c in key]
    records = []
    for cid in cases:
        expected = key[cid]
        trials = 3 if expected.get("expected_decision") in (
            "escalate", "request_document") else 1
        for _ in range(trials):
            rec = run_case(cid, log=False, disable_guards=disable_guards,
                           max_turns=max_turns)
            passed, _fails = code_check(rec, expected)
            records.append((rec, passed))
    turns = [r["turns"] for r, _ in records]
    return {
        "trials": len(records),
        "passed": sum(1 for _, p in records if p),
        "pass_rate": sum(1 for _, p in records if p) / len(records),
        "median_turns": statistics.median(turns),
        "worst_turns": max(turns),
        "hit_cap": sum(1 for r, _ in records if r["stopped_by"] == "step_cap"),
        "tokens_in": sum(r["tokens_in"] for r, _ in records),
        "cost_usd": sum(r["cost_usd"] for r, _ in records),
        "spread": Counter(turns),
    }


# =====================================================================
# FAILURE 1 · LOOP CONTROL — the one D7 requires
# =====================================================================
def failure_1():
    _bar("D7 · FAILURE 1 — LOOP CONTROL   (deletion: action de-duplication)")

    print("""
  WHAT IT IS
  A loop has no memory of its own actions unless you give it one.
  Delete that memory and the agent re-reads what it already knows: same
  tool, same arguments, turn after turn, learning nothing.

  It does NOT crash. No exception is raised, no tool errors, no data is
  wrong. It just burns turns — and you only ever see that if you are
  counting.

  HOW IT IS STAGED
  backends.py, SCRIPTS["LOOP-8842"]: a hand-written move list where the
  agent re-reads the policy it has already read. The planner would
  never produce this, which is exactly why it is scripted — to prove a
  guard fires, something has to attempt the thing it guards against.
  The claim underneath is the real CLM-8842 and the tools do real
  lookups; only the model's moves are staged.
""")

    print(RULE)
    print("  1 · THE INSTRUMENTATION THAT FOUND IT")
    print(RULE)
    print("""
  agent.py records, per run: turns used, tokens in and out, estimated
  cost, whether a cap fired, and every tool call in order (trace.py).
  Without the turn and cost counters this failure is INVISIBLE — the
  run returns an answer, no exception is raised, and the only symptom
  is a larger bill at the end of the month.
""")

    before = run_case("LOOP-8842", log=False,
                      disable_guards=("duplicate_action",))
    after = run_case("LOOP-8842", log=False)

    print("  The trace is what makes it legible. With the guard deleted:")
    print("      tool sequence : %s" % " -> ".join(
        _tool_sequence("LOOP-8842", ("duplicate_action",))))
    print("      the same call, with the same arguments, %d times."
          % _repeat_count("LOOP-8842", ("duplicate_action",)))
    print()

    print(RULE)
    print("  2 · THE TURN DISTRIBUTION ACROSS THE WHOLE EVALUATION SET")
    print(RULE)
    healthy = _run_whole_set()
    print()
    print("      median            %s turns" % healthy["median_turns"])
    print("      worst case        %s turns" % healthy["worst_turns"])
    print("      hit the step cap  %d of %d trials"
          % (healthy["hit_cap"], healthy["trials"]))
    print("      spread            %s"
          % ", ".join("%d turns x%d" % (t, n)
                      for t, n in sorted(healthy["spread"].items())))
    print("""
      THIS IS WHERE THE CAP COMES FROM. Median 3, worst LEGITIMATE run
      5, so the cap is 6 — worst legitimate plus one. Not a round
      number: a cap of 30 would never fire, and a cap of 4 would
      truncate every claim that has a pre-authorisation to chase.
""")

    print(RULE)
    print("  3 · THE FIX, AND WHY THE OTHER TWO GUARDS WERE THE WRONG PLACE")
    print(RULE)
    print("""
  The fix belongs in the CODE LAYER, and specifically in action
  de-duplication. Not in the prompt, and not in the tool interface:

    NOT THE PROMPT     "do not repeat yourself" is re-billed on every
                       turn of every run, dies the moment we change
                       model, and is advice — a model that has already
                       lost the thread is exactly the model least
                       likely to follow it.

    NOT THE INTERFACE  lookup_policy is a correct tool returning a
                       correct answer. Nothing about its signature or
                       its return shape is wrong. There is nothing at
                       the interface to fix.

    THE CODE LAYER     the loop has state; the model does not. Only
                       the loop can know that this exact call already
                       happened. One `if`, paid for once.

  All three code-layer guards were measured on this same run:
""")

    variants = [
        ("all three guards active (the shipped agent)", ()),
        ("de-duplication DELETED", ("duplicate_action",)),
        ("de-duplication AND step cap DELETED",
         ("duplicate_action", "step_cap")),
        ("de-duplication AND budget ceiling DELETED",
         ("duplicate_action", "budget_ceiling")),
    ]
    print("  %-44s %7s %9s %11s" % ("configuration", "turns", "cost", "stopped by"))
    print("  " + "-" * 66)
    for label, disabled in variants:
        r = run_case("LOOP-8842", log=False, disable_guards=disabled)
        print("  %-44s %7d %9.6f %11s"
              % (label, r["turns"], r["cost_usd"], r["stopped_by"]))
    print("""
  READ THAT TABLE, BECAUSE IT IS THE ANSWER TO "WHICH ONE CAUGHT IT".

  De-duplication caught it at turn 3 — the FIRST repeat, the earliest
  any guard could — and its message names the actual fault:
  "lookup_policy called again with identical arguments, the loop is
  not progressing."

  The step cap also stopped the run, but not until turn 7, having
  spent %.1fx the cost. And what it reports is "hit the cap without
  reaching a conclusion" — true, but it is a symptom. It tells you the
  run failed; it does not tell you why. It is a BACKSTOP, not a
  diagnosis, and a backstop that fires four turns later costs more
  than twice as much.

  The budget ceiling never fired at all. At 60,000 tokens it is far
  above anything this loop burns — it exists to catch a DIFFERENT
  failure: a run that stays inside its turn budget but drags fat
  observations along with it. Wrong instrument for this fault, and the
  row proves it: deleting it changes nothing.

  >>> NOW READ ROW THREE AGAIN, BECAUSE IT IS THE WHOLE LESSON. <<<
  With de-duplication AND the step cap both deleted, `stopped by` is
  None. Nothing stopped it. No exception was raised, no tool errored,
  no data was wrong — the run simply walked to the end of its moves,
  produced no answer, and cost 3.9x the shipped agent. That is Class
  4's finding reproduced exactly: it did not crash, nothing failed, it
  burned money in a circle. THE ONLY REASON WE CAN SEE IT AT ALL IS
  THAT WE ARE COUNTING.

  So: all three guards are worth having, they catch different things,
  and only one of them both stops this failure early AND names it.
""" % (_cost_ratio()))

    print(RULE)
    print("  4 · BEFORE AND AFTER")
    print(RULE)
    print()
    print("  On the staged case:")
    print("  %-24s %12s %12s %10s" % ("", "BEFORE", "AFTER", "CHANGE"))
    print("  " + "-" * 62)
    print("  %-24s %12d %12d %9.2fx"
          % ("turns", before["turns"], after["turns"],
             after["turns"] / before["turns"]))
    print("  %-24s %12d %12d %9.2fx"
          % ("input tokens", before["tokens_in"], after["tokens_in"],
             after["tokens_in"] / before["tokens_in"]))
    print("  %-24s %12.6f %12.6f %9.2fx"
          % ("cost US$", before["cost_usd"], after["cost_usd"],
             after["cost_usd"] / before["cost_usd"]))
    print("  %-24s %12s %12s" % ("stopped by", before["stopped_by"],
                                 after["stopped_by"]))
    print("  %-24s %12s %12s"
          % ("reached a conclusion", "no", "no — but LOUDLY"))

    print("""
  Note what did NOT change: neither run reaches a good answer, because
  the staged move list never contains one. That is honest. What changed
  is that the failure now costs %.0f%% less and ARRIVES NAMED. The stop
  is loud: the decision record carries decision=escalate,
  trigger=guardrail_duplicate_action, and a reason saying which
  guardrail halted it at which turn.

  A cap that silently returned an empty answer would be WORSE than the
  loop — it converts a visible cost problem into an invisible
  correctness problem.
""" % (100 * (1 - after["cost_usd"] / before["cost_usd"])))

    print("  AND THE PART THAT ACTUALLY MATTERS — did the guards truncate")
    print("  any LEGITIMATE run? The whole evaluation set, both ways:")
    print()
    loose = _run_whole_set(disable_guards=("duplicate_action", "step_cap"),
                           max_turns=99)
    print("  %-30s %14s %14s" % ("", "GUARDS OFF", "GUARDS ON"))
    print("  " + "-" * 60)
    print("  %-30s %14d %14d" % ("trials", loose["trials"], healthy["trials"]))
    print("  %-30s %13.1f%% %13.1f%%"
          % ("PASS RATE", 100 * loose["pass_rate"],
             100 * healthy["pass_rate"]))
    print("  %-30s %14s %14s" % ("median turns", loose["median_turns"],
                                 healthy["median_turns"]))
    print("  %-30s %14s %14s" % ("worst-case turns", loose["worst_turns"],
                                 healthy["worst_turns"]))
    print("  %-30s %14d %14d" % ("hit the step cap", loose["hit_cap"],
                                 healthy["hit_cap"]))
    verdict = ("unchanged — the guards cost us nothing"
               if abs(loose["pass_rate"] - healthy["pass_rate"]) < 1e-9
               else "!! THE GUARDS TRUNCATED A GOOD RUN — investigate !!")
    print()
    print("  PASS RATE: %s" % verdict)
    print("""
  That is the claim D7 point 4 asks for, and it is the one teams skip:
  the step cap stops a runaway AND leaves every legitimate run intact,
  because it was set from the measured distribution rather than picked.
""")
    return {"healthy": healthy, "before": before, "after": after}


def _tool_sequence(case_id, disabled):
    """Read the tool order straight out of the instrumentation."""
    from trace import Trace  # noqa: F401  (documents where this comes from)
    import agent
    seq = []
    original = agent.tools.call

    def spy(name, args):
        seq.append(name)
        return original(name, args)

    agent.tools.call = spy
    try:
        run_case(case_id, log=False, disable_guards=disabled)
    finally:
        agent.tools.call = original
    return seq


def _repeat_count(case_id, disabled):
    seq = _tool_sequence(case_id, disabled)
    return max(Counter(seq).values())


def _cost_ratio():
    a = run_case("LOOP-8842", log=False,
                 disable_guards=("duplicate_action",))["cost_usd"]
    b = run_case("LOOP-8842", log=False)["cost_usd"]
    return a / b


# =====================================================================
# FAILURE 2 · A DIFFERENT LAYER — owned by the descriptors strand
# =====================================================================
def failure_2():
    """Reproduce the expired-PA information-loss failure."""
    _bar("D7 · FAILURE 2 — TOOL INTERFACE")

    case_id = "CLM-8894"
    original_version = config.PROMPT_VERSION

    def evidence_check(record):
        """Check the three facts required by this case's answer key."""
        reason = record.get("reason", "")
        checks = {
            "names_PA_5640": "PA-5640" in reason,
            "records_expiry_2026_05_31": "2026-05-31" in reason,
            "explains_not_authorised": "does not authorise" in reason.lower(),
        }
        return all(checks.values()), checks
    
    original_tool = tools.REGISTRY["get_preauthorisation"]

    try:
        # Keep the V2 prompt and every other condition fixed.
        config.PROMPT_VERSION = "v2"

        # BEFORE: delete only the structured PA interface.
        tools.REGISTRY["get_preauthorisation"] = (
            tools.get_preauthorisation_v1
        )
        before = run_case(case_id, log=False)

        # AFTER: restore only the structured PA interface.
        tools.REGISTRY["get_preauthorisation"] = (
            tools.get_preauthorisation_v2
        )
        after = run_case(case_id, log=False)

    finally:
        tools.REGISTRY["get_preauthorisation"] = original_tool
        config.PROMPT_VERSION = original_version

    expected = load_key()[case_id]
    before_code_pass, before_code_fails = code_check(before, expected)
    after_code_pass, after_code_fails = code_check(after, expected)
    before_evidence_pass, before_evidence = evidence_check(before)
    after_evidence_pass, after_evidence = evidence_check(after)

    print("""
  FAILURE DEFINITION

  CLM-8894 contains procedure 29881, which requires
  pre-authorisation. PA-5640 belongs to the correct member and
  procedure, but expired on 2026-05-31 before the service date
  2026-09-09.

  The required result is request_document. The decision record must
  also state that PA-5640 was found, record its expiry date, and
  explain why it does not authorise this claim.

  DELETION FROM THE WORKING AGENT

  V2 is the working interface:

      {found, preauth, expired_candidate}

  V1 deletes that structured result and returns only a valid PA row or
  None. Therefore, an expired matching PA becomes indistinguishable
  from a PA that never existed.
""")

    print(RULE)
    print("  BEFORE — V1 ROW-OR-NONE INTERFACE")
    print(RULE)
    print("  decision          : %s" % before.get("decision"))
    print("  code check        : %s" %
          ("PASS" if before_code_pass else "FAIL"))
    print("  evidence check    : %s" %
          ("PASS" if before_evidence_pass else "FAIL"))
    print("  reason            : %s" % before.get("reason"))
    print("  required evidence : %s" % before_evidence)

    print()
    print(RULE)
    print("  AFTER — V2 STRUCTURED INTERFACE")
    print(RULE)
    print("  decision          : %s" % after.get("decision"))
    print("  code check        : %s" %
          ("PASS" if after_code_pass else "FAIL"))
    print("  evidence check    : %s" %
          ("PASS" if after_evidence_pass else "FAIL"))
    print("  reason            : %s" % after.get("reason"))
    print("  required evidence : %s" % after_evidence)

    print()
    print(RULE)
    print("  BEFORE AND AFTER MEASUREMENTS")
    print(RULE)
    print("  %-24s %12s %12s" % ("measure", "V1 BEFORE", "V2 AFTER"))
    print("  " + "-" * 50)
    print("  %-24s %12s %12s" %
          ("decision", before.get("decision"), after.get("decision")))
    print("  %-24s %12s %12s" %
          ("code check",
           "PASS" if before_code_pass else "FAIL",
           "PASS" if after_code_pass else "FAIL"))
    print("  %-24s %12s %12s" %
          ("evidence check",
           "PASS" if before_evidence_pass else "FAIL",
           "PASS" if after_evidence_pass else "FAIL"))
    print("  %-24s %12d %12d" %
          ("turns", before["turns"], after["turns"]))
    print("  %-24s %12d %12d" %
          ("input tokens", before["tokens_in"], after["tokens_in"]))
    print("  %-24s %12d %12d" %
          ("output tokens", before["tokens_out"], after["tokens_out"]))
    print("  %-24s %12.6f %12.6f" %
          ("cost US$", before["cost_usd"], after["cost_usd"]))

    print("""
  INTERPRETATION

  The ordinary code check passes both versions because both reach the
  broad request_document outcome. However, V1 fails the evidence check:
  it says that no pre-authorisation was found even though PA-5640
  exists.

  V2 passes because expired_candidate preserves PA-5640 and its
  validity dates. The final record can therefore explain that PA-5640
  existed but expired on 2026-05-31.

  CORRECT FIX LAYER

  This fix belongs in the TOOL INTERFACE. The information was discarded
  before the model received it.

  It does not belong in the prompt layer because a prompt cannot
  reconstruct a PA identifier and expiry date that the tool returned
  as None.

  It does not belong in the loop-control layer because the agent did
  not repeat actions, exceed a cap, or fail to conclude. It reached a
  confident but insufficiently evidenced answer.
""")

    result = {
        "experiment": "D7_failure_2_tool_interface",
        "measured_on": datetime.now(timezone(timedelta(hours=8))).date().isoformat(),
        "case_id": case_id,
        "deleted_component": "structured get_preauthorisation return shape",
        "expected": expected,
        "before_v1": {
            "record": before,
            "code_check_passed": before_code_pass,
            "code_check_failures": before_code_fails,
            "evidence_check_passed": before_evidence_pass,
            "evidence_checks": before_evidence,
        },
        "after_v2": {
            "record": after,
            "code_check_passed": after_code_pass,
            "code_check_failures": after_code_fails,
            "evidence_check_passed": after_evidence_pass,
            "evidence_checks": after_evidence,
        },
        "fix_layer": "tool_interface",
        "result": ("V1 loses the expired PA evidence; "
                   "V2 restores the required evidence."),
    }

    results_directory = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(results_directory, exist_ok=True)
    output_path = os.path.join(
        results_directory, "d7_failure_2_tool_interface.json")

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(result, file, indent=2, ensure_ascii=False)

    print("  Saved reproducible result to:")
    print("  %s" % output_path)
    return result


def main(argv):
    if config.BACKEND != "scripted":
        print("\n  D7 runs SCRIPTED. It needs no key and it must reproduce for")
        print("  a marker. Live tokens are for D5(b) only.\n")
        return 1
    print()
    print(config.summary())

    which = argv[1] if len(argv) > 1 else None
    if which in (None, "1"):
        failure_1()
    if which in (None, "2"):
        failure_2()
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
