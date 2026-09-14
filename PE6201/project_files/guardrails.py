"""
PE6201 · A2 — THE GUARDRAIL LAYER  (D3a)
=====================================================================
Four things, and NONE of them involves a model. That is the point, and
it is why D3(b)'s ten guardrail cases run on the scripted backend: they
test OUR CODE, and a model has no say in whether they fire.

    1. STEP CAP              stop after N turns
    2. BUDGET CEILING        stop after N tokens
    3. ACTION DE-DUPLICATION stop repeating an action already taken
    4. AUTONOMY GATE         hold the irreversible step for a human

MAKE THE STOP LOUD. The brief is blunt about this: "A cap that silently
returns an empty answer is worse than the loop — it converts a visible
cost problem into an invisible correctness problem." Every stop below
records WHY, at WHICH turn, and lands in the decision record.

--------------------------------------------------------------------
WHERE THE GATE SITS, AND WHY IT MATTERS

In front of the IRREVERSIBLE STEP. Not in front of the agent.

An agent gated as a whole is not an agent, it is a form: a human
approves every run, so nothing was automated and the only thing the
model saved was typing. Gating just `issue_decision_letter` leaves the
cheap, reversible, re-runnable claim work automatic and puts the human
exactly where the cost of being wrong is concentrated.
=====================================================================
"""


class GuardrailStop(Exception):
    """Raised when the code layer halts a run.

    Carries the reason so the decision record can say what stopped it
    and where. A guardrail that raises a bare exception tells you a run
    died; this one tells you which rule killed it.
    """

    def __init__(self, reason, detail="", turn=None):
        self.reason = reason
        self.detail = detail
        self.turn = turn
        super().__init__("%s: %s" % (reason, detail) if detail else reason)


class Guardrails:
    """One instance per run.

    NEVER share an instance between cases. A shared instance leaks
    `seen_actions` from one case into the next, and D4 requires every
    case to start from a clean state — a leaked de-duplication set would
    make case 2 fail because of something case 1 did.

    Each guard can be switched off individually. That is not a
    convenience: D7 requires each failure to be built as a DELETION from
    the working agent ("the working agent, minus X"), and putting X back
    must recover the behaviour. `disable` is how we delete X without
    editing this file, so the same code path is under test either way.
    """

    ALL_GUARDS = ("step_cap", "budget_ceiling", "duplicate_action",
                  "autonomy_gate")

    def __init__(self, max_turns, max_tokens, autonomy, disable=()):
        self.max_turns = max_turns
        self.max_tokens = max_tokens
        self.autonomy = autonomy
        self.disabled = set(disable)
        for name in self.disabled:
            if name not in self.ALL_GUARDS:
                raise ValueError("no such guardrail to disable: %r "
                                 "(known: %s)" % (name, ", ".join(self.ALL_GUARDS)))
        self.seen_actions = set()     # de-duplication memory, per run
        self.gated_calls = 0          # how many times the gate was reached
        self.fired = []               # every guardrail event, for the record

    def _on(self, guard):
        return guard not in self.disabled

    # ---- 1 · step cap ------------------------------------------------
    def check_turns(self, turn):
        """Stop a run that is not converging.

        The cap is derived from evidence in config.py: worst legitimate
        run plus one. A cap set from a round number is decoration —
        either it is so high it never fires, or it truncates good runs.
        """
        if not self._on("step_cap"):
            return
        if turn > self.max_turns:
            self._fire("step_cap", "reached the %d-turn cap" % self.max_turns,
                       turn)
            raise GuardrailStop(
                "step_cap",
                "hit the %d-turn cap without reaching a conclusion"
                % self.max_turns, turn)

    # ---- 2 · budget ceiling ------------------------------------------
    def check_budget(self, tokens_so_far, turn=None):
        """Stop a run that is converging too expensively.

        Distinct from the step cap: a run can stay inside six turns and
        still blow the budget if the observations are fat. This is the
        guard that catches an expensive turn, where the step cap catches
        a repetitive one.
        """
        if not self._on("budget_ceiling"):
            return
        if tokens_so_far > self.max_tokens:
            self._fire("budget_ceiling", "%d tokens" % tokens_so_far, turn)
            raise GuardrailStop(
                "budget_ceiling",
                "spent %d tokens, ceiling is %d" % (tokens_so_far,
                                                    self.max_tokens), turn)

    # ---- 3 · action de-duplication -----------------------------------
    def check_duplicate(self, tool, args, turn=None):
        """A loop has no memory of its own actions unless you give it one.

        THIS IS THAT MEMORY, and it is the guard D7's required loop
        failure deletes. Class 4's demonstration: 8 turns, no answer,
        1.6x the cost, and NO exception raised. It did not crash.
        Nothing failed. It burned money in a circle, and you only ever
        see that if you are counting.

        The signature includes the arguments on purpose. Calling
        check_coverage three times with three different codes is correct
        and must be allowed; calling it twice with the SAME code is the
        loop.
        """
        if not self._on("duplicate_action"):
            return
        signature = (tool, repr(sorted(args.items())))
        if signature in self.seen_actions:
            self._fire("duplicate_action", "%s repeated with identical "
                       "arguments" % tool, turn)
            raise GuardrailStop(
                "duplicate_action",
                "%s called again with identical arguments — the loop is not "
                "progressing" % tool, turn)
        self.seen_actions.add(signature)

    # ---- 4 · autonomy gate -------------------------------------------
    def gate(self, action_name, payload, approve=None, turn=None):
        """Called ONLY in front of the irreversible step.

        `approve` is a callable the harness supplies — the stand-in for
        the human operator. On the scripted backend it auto-approves so
        the run stays deterministic, and the record still shows the gate
        was reached and passed, which is what a marker looks for.

        Note it also counts how many times the gate was reached. "The
        gated action fired exactly once" is a code check in D4, and a
        run that reached the gate twice is a bug even if the decision
        came out right.
        """
        self.gated_calls += 1

        if not self._on("autonomy_gate"):
            self._fire("gate_bypassed", "%s (guard DISABLED — D7 only)"
                       % action_name, turn)
            return True

        if self.autonomy == "act":
            self._fire("gate_passed", "%s (autonomy=act)" % action_name, turn)
            return True
        if self.autonomy == "suggest":
            self._fire("gate_held", "%s (autonomy=suggest — a human performs "
                       "the irreversible step)" % action_name, turn)
            return False

        ok = bool(approve and approve(action_name, payload))
        self._fire("gate_%s" % ("passed" if ok else "held"),
                   "%s (autonomy=confirm)" % action_name, turn)
        return ok

    # ---- bookkeeping -------------------------------------------------
    def _fire(self, kind, detail, turn=None):
        self.fired.append({"guardrail": kind, "detail": detail, "turn": turn})
