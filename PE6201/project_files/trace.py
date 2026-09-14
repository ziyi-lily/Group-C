"""
PE6201 · A2 — INSTRUMENTATION
=====================================================================
INSTRUMENTATION IS NOT OPTIONAL, and it is not something you add later.

D6's cost model and D7's loop failure both need numbers captured WHILE
THE RUN HAPPENED. A team that bolts instrumentation on afterwards has
to re-run the whole live battery to get them — which on a US$10 key is
a real problem, not a tidiness one.

The brief's definition of "instrumented", from the FAQ: per run, record
turns used, tokens in and out, estimated cost, whether a cap fired, and
which tools were called in order. Everything below exists to satisfy
that sentence.

WHY IT MATTERS FOR D7. A runaway loop raises no exception. It does not
crash and nothing fails — it just costs more. The ONLY way to notice it
is to be counting, and the only way to prove you noticed it rather than
assumed it is to hand a marker the counts.
=====================================================================
"""
import json
import os
import time

import config


def _ensure_log_dir():
    os.makedirs(config.LOG_DIR, exist_ok=True)


class Trace:
    """The flight recorder for ONE run.

    Created inside run_case() and thrown away when the run ends — same
    isolation rule as the guardrails. Nothing here is shared between
    cases.
    """

    def __init__(self, case_id, backend_name):
        self.case_id = case_id
        self.backend = backend_name
        self.started = time.time()
        self.turns = []          # one entry per turn, in order
        self.tool_sequence = []  # every tool name, in call order

    def record_turn(self, turn_no, thought, calls, observations,
                    tokens_in, tokens_out):
        """One pass around the loop.

        `calls` is a LIST because a turn may carry several tool calls —
        that is D2(c). Storing the list rather than a single name is
        what lets compare_parallel.py show sequential against parallel
        on the same evaluation set.
        """
        self.turns.append({
            "turn": turn_no,
            "thought": thought,
            "calls": [{"tool": name, "args": args} for name, args in calls],
            "observations": observations,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        })
        self.tool_sequence.extend(name for name, _ in calls)

    def last_tool(self):
        """Which tool call came immediately before things went wrong.

        D0(b) asks us to find the weak step by grouping FAILING runs by
        the tool that preceded the failure — "the turn that shows up
        most often before a wrong outcome is your candidate". This is
        the field that makes that grouping possible.
        """
        return self.tool_sequence[-1] if self.tool_sequence else None

    def as_dict(self):
        return {
            "case_id": self.case_id,
            "backend": self.backend,
            "seconds": round(time.time() - self.started, 3),
            "turn_count": len(self.turns),
            "tool_sequence": self.tool_sequence,
            "last_tool_before_end": self.last_tool(),
            "turns": self.turns,
        }

    def write(self, filename="traces.jsonl"):
        """Append this run's full trace to logs/.

        One JSON object per line, so the file can be grown across a
        whole battery and read back with two lines of Python.
        """
        _ensure_log_dir()
        path = os.path.join(config.LOG_DIR, filename)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(self.as_dict(), default=str) + "\n")
        return path


def append_decision(record, filename="decisions.jsonl"):
    """THE OUTPUT OF THE GATED ACTION — the whole write, and the whole
    deliverable.

    Look at what is NOT in here: no letter text, no greeting, no
    recipient, no policy summary, no template. Nothing is sent anywhere.
    This record IS what the system produced, and it is the thing that
    gets marked: WHICH decision, on WHAT evidence, after WHICH gate, at
    WHAT cost.
    """
    _ensure_log_dir()
    path = os.path.join(config.LOG_DIR, filename)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\n")
    return path
