"""
PE6201 · A2 — CONFIGURATION  (the vendor-neutral block, D5)
=====================================================================
EVERYTHING that knows which model we are talking to lives here and in
ONE function in backends.py (`_live_call`). Nowhere else. Switching
model is changing a string.  That is the D5 requirement.

    BACKEND = "scripted"   free, deterministic, no key, no network.
                           >>> THIS MUST BE THE DEFAULT IN WHAT WE
                           SUBMIT. <<< A marker clones the repository
                           and runs `python run_eval.py`. If numbers do
                           not come back, D5(a) has failed and
                           Technical Execution is capped.

    BACKEND = "live"       a real model through OpenRouter. Costs money.
                           Only D5(b), the model battery, needs this.

D3(b) the guardrail checklist, D5(a) the reproducible run, and D7 the
two failure reproductions ALL run scripted. Only the battery is live.
=====================================================================
"""
import os

# ─────────────────────────────────────────────────────────────────────
# THE THREE STRINGS. Change these, change nothing else.
# ─────────────────────────────────────────────────────────────────────
BACKEND = os.environ.get("A2_BACKEND", "scripted")   # "scripted" | "live"

MODEL = os.environ.get("A2_MODEL", "openai/gpt-4o-mini")   # live only
BASE_URL = "https://openrouter.ai/api/v1"

# The key NEVER goes in this file, and never into git.
#     Windows PowerShell :  $env:OPENROUTER_API_KEY = "sk-or-..."
#     bash / Colab       :  export OPENROUTER_API_KEY="sk-or-..."
API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

# ─────────────────────────────────────────────────────────────────────
# WHICH PROBLEM.  Our team chose A — health-insurance claim first
# response.  Problem B is not implemented in this repository.
# ─────────────────────────────────────────────────────────────────────
PROBLEM = "A"

# ─────────────────────────────────────────────────────────────────────
# WHICH PROMPT VERSION (D2b).  "v1" is the deliberately weaker set of
# tool descriptors; "v2" is the rewrite. The v1-vs-v2 comparison is run
# on ONE model with everything else held fixed — that is what makes the
# difference attributable to our writing rather than to the model.
# ─────────────────────────────────────────────────────────────────────
PROMPT_VERSION = os.environ.get("A2_PROMPT_VERSION", "v2")   # "v1" | "v2"

# ─────────────────────────────────────────────────────────────────────
# HOW THE AGENT GROUPS ITS CALLS (D2c).
#     "parallel"    independent calls are executed in ONE turn
#     "sequential"  one call per turn — the before-picture we measure
#                   the parallel saving against
# ─────────────────────────────────────────────────────────────────────
CALL_MODE = os.environ.get("A2_CALL_MODE", "parallel")   # "parallel" | "sequential"

# ─────────────────────────────────────────────────────────────────────
# GUARDRAIL LIMITS (D3a) — THE CODE LAYER.
#
# SET FROM EVIDENCE, NOT FROM A ROUND NUMBER. The brief is explicit:
# "If your median run is 4 turns and your worst legitimate run is 7, a
# step cap of 8 is defensible and a step cap of 30 is decoration."
#
# Our evidence, from the 15 shipped cases in parallel mode:
#     median legitimate run        4 turns
#     worst legitimate run         5 turns  (approve + a preauth to chase)
#     so the cap is                6 turns  (worst legitimate + 1)
#
# A 6-turn cap cannot truncate any run we have ever seen succeed, and it
# stops a runaway two turns after it stops making progress.
# Re-derive this number after the evaluation set grows — run
#     python run_eval.py --turn-distribution
# ─────────────────────────────────────────────────────────────────────
MAX_TURNS = int(os.environ.get("A2_MAX_TURNS", "6"))

# Sequential mode needs its own cap: the same work spread one-call-per-
# turn is up to 10 turns on a four-line claim. This is NOT a weaker
# guardrail, it is the same guardrail measured against a different
# grouping — and the gap between the two numbers is the D2(c) finding.
MAX_TURNS_SEQUENTIAL = int(os.environ.get("A2_MAX_TURNS_SEQ", "14"))

MAX_TOKENS_PER_RUN = int(os.environ.get("A2_MAX_TOKENS", "60000"))   # budget ceiling

# ─────────────────────────────────────────────────────────────────────
# AUTONOMY SETTING (D3a). The gate goes in front of the IRREVERSIBLE
# STEP, not in front of the agent as a whole.
#
#   suggest  the agent proposes; a human does the irreversible step
#   confirm  the agent does everything EXCEPT the irreversible step,
#            which waits for a human yes
#   act      the agent completes the irreversible step itself
#
# WE CHOSE "confirm", and the defence is in docs/D3_autonomy.md:
# issuing a decision letter tells a member "approved in principle", and
# walking that back is expensive. But the claim work either side of it
# is cheap and reversible, so gating the whole agent would throw away
# the automation without buying any extra safety.
# ─────────────────────────────────────────────────────────────────────
AUTONOMY = os.environ.get("A2_AUTONOMY", "confirm")   # "suggest"|"confirm"|"act"

# ─────────────────────────────────────────────────────────────────────
# WHERE THE DATA IS.
# Fails LOUDLY with instructions rather than returning something wrong.
# A silent wrong path here is the failure the data guide warns about:
# every tool returns nothing and the run still looks fine.
# ─────────────────────────────────────────────────────────────────────
HERE = os.path.dirname(os.path.abspath(__file__))

_CANDIDATES = [
    os.environ.get("A2_DATA", ""),
    os.path.join(HERE, "A2_reference_data"),
    os.path.join(HERE, "..", "A2_reference_data"),
]


def data_root():
    """Find the folder that holds data_A/."""
    for c in _CANDIDATES:
        if c and os.path.isdir(os.path.join(c, "data_%s" % PROBLEM)):
            return os.path.abspath(c)
    raise SystemExit(
        "\n  Could not find the reference data.\n"
        "  I looked for a folder containing data_%s/ in:\n" % PROBLEM
        + "".join("    %s\n" % os.path.abspath(c) for c in _CANDIDATES if c)
        + "\n  Fix it either way:\n"
        "    1. put A2_reference_data/ inside this repository, or\n"
        "    2. set A2_DATA to point at it\n")


LOG_DIR = os.path.join(HERE, "logs")

# ─────────────────────────────────────────────────────────────────────
# PRICES, US dollars per MILLION tokens — section 7 of the brief, the
# cheap tier. RE-CHECK THESE against the vendor page before quoting them
# in the report: quoting a price nobody verified is exactly what D6 is
# marked on.
# ─────────────────────────────────────────────────────────────────────
PRICE_IN = 0.10
PRICE_OUT = 0.40

# ─────────────────────────────────────────────────────────────────────
# COST MODEL INPUTS (D6) — Problem A's figures, from Appendix A.
# ─────────────────────────────────────────────────────────────────────
MONTHLY_VOLUME = 8000            # claims per month
FAILURE_HOURLY_RATE = 38.0       # US$/h, claims assessor
FAILURE_MINUTES = 12             # minutes per escalated claim
FAILURE_COST = FAILURE_HOURLY_RATE * FAILURE_MINUTES / 60.0   # US$7.60


def summary():
    """One line, printed at the top of every run, so nobody ever has to
    guess which backend produced the numbers they are looking at."""
    where = ("FREE, deterministic" if BACKEND == "scripted"
             else "LIVE — this costs money")
    model = "(no model)" if BACKEND == "scripted" else MODEL
    return ("BACKEND=%s  %s  |  PROBLEM=%s  |  model=%s  |  prompt=%s  |  "
            "calls=%s  |  cap=%d turns  |  autonomy=%s"
            % (BACKEND, where, PROBLEM, model, PROMPT_VERSION, CALL_MODE,
               turn_cap(), AUTONOMY))


def turn_cap():
    """The step cap that applies to the CURRENT call mode."""
    return MAX_TURNS_SEQUENTIAL if CALL_MODE == "sequential" else MAX_TURNS
