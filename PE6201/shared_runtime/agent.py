"""
PE6201 · A2 — THE AGENT LOOP  (D1)
=====================================================================
    thought -> action -> observation -> repeat -> final

That is the whole of ReAct, and it is hand-rolled here on purpose. No
framework owns this loop: the loop IS the thing being marked, and when
it misbehaves you need to be able to read the fifty lines that did it.
Ordinary libraries for everything else are fine — it is the loop that
has to be ours.

--------------------------------------------------------------------
WHAT MAKES THIS AN AGENT AND NOT A WORKFLOW

The number of steps is decided by the DATA, not by us:

    CLM-8850  one line, live policy, nothing to chase      4 turns
    CLM-8842  three lines, one excluded, one preauth       5 turns
    CLM-8925  over the annual limit — stops early          2 turns
    CLM-8941  instruction in the narrative                 3 turns

We did not write those branches. The claim record did. Nothing in this
file knows how many turns a claim will take.

--------------------------------------------------------------------
ONE TURN MAY CARRY SEVERAL TOOL CALLS  (D2c)

`move["calls"]` is a LIST. Every call in it is executed and every
observation is appended before the loop asks again. That is what
collapses eight tool calls into five turns — and because the whole
transcript is re-sent on every turn, cutting turns cuts the bill
quadratically, not linearly.

Calling five tools in one turn is STILL ONE AGENT. It is not
multi-agent and it does not change the architecture.
=====================================================================
"""
import time

import config
import prompt
import tools
from backends import make_backend
from guardrails import Guardrails, GuardrailStop
from trace import Trace, append_decision


def run_case(case_id, approve=None, verbose=False, disable_guards=(),
             max_turns=None, log=True):
    """Run ONE case from a clean state and return the decision record.

    ISOLATION (D4). Everything this function needs is created INSIDE it:
    the guardrails, the trace, the backend, the transcript, the evidence
    list. No module-level counters, no shared guardrail object, no
    leftover state. No case may depend on a previous one having run —
    which matters more than it sounds, because negative cases are run
    three times each and the second run must not inherit the first
    run's de-duplication memory.

    `disable_guards` is how D7 builds a failure as a DELETION from the
    working agent rather than as a separately written bad agent. Put the
    guard back and the behaviour must return.
    """
    started = time.time()
    cap = max_turns if max_turns is not None else config.turn_cap()

    guards = Guardrails(cap, config.MAX_TOKENS_PER_RUN, config.AUTONOMY,
                        disable=disable_guards)

    # WHAT THE MODEL IS TOLD. On the scripted backend these are ignored —
    # the planner never consults a model, so no prompt is ever sent. On
    # the live backend this IS the experiment D2(b) measures.
    backend = make_backend(
        case_id,
        tool_descriptors=list(tools.descriptors().values()),
        system_prompt=prompt.build_system_prompt())

    tracer = Trace(case_id, backend.name)

    transcript = []      # what the model would see, turn by turn
    evidence = []        # every tool actually called, in order
    tool_results = {}    # latest result for each tool
    preauth_results = [] # every PA result; multi-line claims may have several

    # TURNS ARE TOOL-CALLING TURNS. The concluding move — where the agent
    # writes its decision record — is bookkeeping, not a turn. Appendix A
    # uses the same convention: CLM-8842 is "turns": 4 with EIGHT tool
    # calls, because the gated action is a turn like any other and the
    # write-up afterwards is not. Count it any other way and the D2(c)
    # arithmetic stops agreeing with the brief.
    turns = 0
    iterations = 0       # loop-safety only; never reported
    tokens_in = tokens_out = 0
    stopped_by = None
    record = None

    # The stand-in for the human operator at the gate. On the scripted
    # backend it auto-approves so the run stays deterministic — and the
    # RECORD still shows the gate was reached and passed, which is what
    # a marker looks for.
    if approve is None:
        def approve(action, payload):
            return True

    try:
        while True:
            # A hard backstop that is NOT the step cap. If the step cap
            # has been deliberately deleted for a D7 reproduction, this
            # stops the process from running for ever — but it fires
            # well after the cap would have, so the D7 before/after
            # numbers still show the runaway.
            iterations += 1
            if iterations > cap + 12:
                raise GuardrailStop(
                    "runaway", "no conclusion after %d iterations — the step "
                    "cap was disabled for this run" % iterations, turns)

            move = backend.next_move(transcript)

            # A backend must return one JSON-like move. Keep the loop
            # gradeable if a model adapter returns an unexpected value rather
            # than crashing later on move.get(...).
            if not isinstance(move, dict):
                move = {
                    "thought": "invalid backend response format",
                    "final": {
                        "decision": "escalate",
                        "trigger": "unparseable_model_output",
                        "reason": "the backend did not return a JSON object",
                    },
                }

            ti, to = backend.token_estimate(transcript)
            tokens_in, tokens_out = tokens_in + ti, tokens_out + to
            guards.check_budget(tokens_in + tokens_out, turns)

            if verbose:
                label = "conclude" if "final" in move else "turn %d" % (turns + 1)
                print("  %-9s · %s" % (label, (move.get("thought") or "")[:100]))

            # ---- conclude ---------------------------------------------
            if "final" in move:
                candidate = dict(move["final"])

                # An approval is not complete until the irreversible action
                # has passed its gate exactly once. Give a live model a clear
                # correction instead of accepting a premature final answer.
                if candidate.get("decision") == "approve_in_principle" and \
                        guards.gated_calls != 1:
                    transcript.append({
                        "role": "assistant",
                        "content": repr(move),
                    })
                    transcript.append({
                        "role": "user",
                        "content": (
                            "INVALID FINAL: approve_in_principle is incomplete "
                            "until issue_decision_letter has been called and "
                            "returned sent=true. Return a calls JSON object "
                            "for that gated action; do not finalise yet."
                        ),
                    })
                    continue

                # Preserve auditable facts that came from trusted tool
                # observations. This does not change the model's decision; it
                # prevents a correct decision from discarding evidence already
                # returned by the tools.
                _append_duplicate_evidence(candidate, tool_results)
                _append_expired_preauth_evidence(candidate, preauth_results)

                record = candidate
                break

            # ---- act: one turn, one or more calls ---------------------
            turns += 1
            guards.check_turns(turns)

            # Accept the documented list-of-pairs representation as well as
            # the common {tool/name, args} representation returned by some
            # live models. The backend normally normalises this already; this
            # is a final interface boundary, not a second planning path.
            raw_calls = move.get("calls") or []
            if not raw_calls and move.get("tool"):
                raw_calls = [[move["tool"], move.get("args", {})]]

            calls = []
            for item in raw_calls:
                if isinstance(item, (tuple, list)) and len(item) >= 2:
                    name, args = item[0], item[1]
                elif isinstance(item, dict):
                    name = item.get("tool") or item.get("name")
                    args = item.get("args", {})
                elif isinstance(item, str):
                    name, args = item, {}
                else:
                    continue

                if name:
                    calls.append((name, args if isinstance(args, dict) else {}))
            observations = []

            for name, args in calls:
                # 3 · de-duplication. Identical call, identical args, in
                #     the same run = the loop is not progressing.
                guards.check_duplicate(name, args, turns)

                # 4 · THE GATE, in front of the irreversible step ONLY.
                if name == tools.GATED_ACTION:
                    if not guards.gate(name, args, approve, turns):
                        raise GuardrailStop(
                            "gate_held",
                            "%s awaits human approval (autonomy=%s)"
                            % (name, config.AUTONOMY), turns)

                result = tools.call(name, args)
                tool_results[name] = result

                if name == "get_preauthorisation":
                    preauth_results.append({
                        "args": dict(args),
                        "result": result,
                    })

                evidence.append(name)
                observations.append({"tool": name, "args": args,
                                     "observation": result})
                if verbose:
                    print("       %-24s -> %s" % (name, _short(result)))

            # Hand the observations to the backend, then to the
            # transcript. The transcript is what a live model reads; the
            # observe() call is how the deterministic planner learns the
            # same facts without parsing its own prompt back.
            observer = getattr(backend, "observe", None)
            if observer:
                observer(observations)

            transcript.append({"role": "assistant",
                               "content": move.get("thought", "")})
            transcript.append({"role": "user", "content": repr(observations)})

            tracer.record_turn(turns, move.get("thought", ""), calls,
                               observations, ti, to)

    except GuardrailStop as stop:
        # A LOUD STOP. The record says what halted the run and where, so
        # this can never be mistaken for a quiet wrong answer. A cap that
        # returns an empty answer silently is worse than the loop it
        # prevented: it turns a visible cost problem into an invisible
        # correctness problem.
        stopped_by = stop.reason
        record = {"decision": "escalate",
                  "trigger": "guardrail_%s" % stop.reason,
                  "escalate_to": "human claims assessor",
                  "reason": "Run halted by the %s guardrail at turn %s — %s. "
                            "No decision was issued."
                            % (stop.reason, stop.turn, stop.detail)}

    cost = (tokens_in / 1e6) * config.PRICE_IN + \
           (tokens_out / 1e6) * config.PRICE_OUT

    record.update({
        "case_id": case_id,
        "evidence": evidence,
        "autonomy": config.AUTONOMY,
        "gate": _gate_summary(guards),
        "turns": turns,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": round(cost, 6),
        "seconds": round(time.time() - started, 3),
        "guardrails_fired": guards.fired,
        "gated_calls": guards.gated_calls,
        "stopped_by": stopped_by,
        "backend": backend.name,
        "model": config.MODEL if backend.name == "live" else None,
        "prompt_version": config.PROMPT_VERSION,
        "call_mode": config.CALL_MODE,
        "last_tool_before_end": tracer.last_tool(),
    })

    if log:
        tracer.write()
        # Only a decision that actually went through the gate is a
        # decision. An escalation or a request is recorded too — the
        # brief is explicit that the evidence trail, autonomy, gate,
        # turns and cost are recorded on EVERY outcome, not just on
        # the ones that act.
        append_decision(record)

    return record


def _append_duplicate_evidence(candidate, tool_results):
    """Append bounded near-match facts when the model omitted them."""
    duplicate_result = tool_results.get("check_duplicate_claim")

    if not isinstance(duplicate_result, dict) or \
            duplicate_result.get("is_duplicate"):
        return

    near_matches = duplicate_result.get("near_matches") or []
    reason = str(candidate.get("reason") or "").strip()

    field_labels = {
        "member_id": "member",
        "hospital_id": "hospital",
        "date_of_service": "date of service",
        "lines": "line items",
    }
    notes = []

    for match in near_matches:
        claim_id = match.get("claim_id", "unknown claim")
        if claim_id in reason:
            continue

        matching = [
            field_labels.get(field, field)
            for field in match.get("matching_fields", [])
        ]
        different = [
            field_labels.get(field, field)
            for field in match.get("different_fields", [])
        ]

        notes.append(
            "%s matches on %s but differs on %s, so it is not an "
            "exact duplicate."
            % (claim_id, ", ".join(matching), ", ".join(different))
        )

    if notes:
        candidate["reason"] = (
            reason + " No exact duplicate was found. " + " ".join(notes)
        ).strip()


def _append_expired_preauth_evidence(candidate, preauth_results):
    """Append expired-PA facts available only in the structured V2 result."""
    reason = str(candidate.get("reason") or "").strip()
    notes = []

    for observation in preauth_results:
        result = observation.get("result")
        args = observation.get("args") or {}

        # V1 returns a valid row or None. With None there is no identifier or
        # expiry date to preserve, which is the controlled D2(b)/D7 failure.
        if not isinstance(result, dict):
            continue

        expired = result.get("expired_candidate")
        if not expired:
            continue

        preauth_id = expired.get("preauth_id")
        valid_from = expired.get("valid_from")
        valid_to = expired.get("valid_to")
        service_date = args.get("date_of_service")
        member_id = args.get("member_id")
        procedure_code = args.get("procedure_code")

        required = [preauth_id, valid_to, service_date]
        if all(value and str(value) in reason for value in required):
            continue

        notes.append(
            "Pre-authorisation %s was found for member %s and procedure %s, "
            "but it was valid only from %s to %s. The service date %s falls "
            "outside this validity period, so %s does not authorise this "
            "claim."
            % (preauth_id, member_id, procedure_code, valid_from, valid_to,
               service_date, preauth_id)
        )

    if notes:
        candidate["reason"] = (reason + " " + " ".join(notes)).strip()


def _gate_summary(guards):
    """One human-readable line about the gate, for the decision record."""
    for event in guards.fired:
        if event["guardrail"].startswith("gate_"):
            kind = event["guardrail"].replace("gate_", "")
            return "%s at turn %s (%s)" % (kind, event["turn"], event["detail"])
    return "issue_decision_letter not called — a non-acting outcome was " \
           "reached before the gate"


def _short(value, n=72):
    s = repr(value)
    return s if len(s) <= n else s[:n - 1] + "…"
