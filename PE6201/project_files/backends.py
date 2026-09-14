"""
PE6201 · A2 — THE BACKENDS
=====================================================================
A backend answers exactly ONE question:

    given what the agent has seen so far, what does it do next?

It returns either
    {"thought": "...", "calls": [(tool, args), ...]}   -> call tools
    {"thought": "...", "final": {...}}                 -> conclude

>>> EXACTLY ONE FUNCTION IN THIS REPOSITORY KNOWS A VENDOR EXISTS. <<<
It is `_live_call` at the bottom. That is the D5 vendor-neutrality
requirement, and it is what makes swapping model a one-string change.

=====================================================================
THREE BACKENDS, AND WHY THERE ARE THREE
=====================================================================

  PlannerBackend   ("scripted", the default)
      A deterministic stand-in for the model. It reads the SAME data
      through the SAME tools and applies Appendix A's routing rule to
      decide the next call. No network, no key, no cost, and the same
      answer every time.

      >>> ADD A CLAIM TO data_A/claims.json AND A LABEL TO
      >>> expected_outcomes_A.json, AND IT RUNS. NOTHING ELSE TO WRITE.

      That property is the whole reason this class exists. The teaching
      scaffold shipped a hand-written move list per case, which is fine
      for one demonstration and impossible for a 35-case evaluation set
      that five teammates are still adding to.

  ScriptOverride  ("scripted", when SCRIPTS has the case)
      A hand-written move list, used where we need the agent to attempt
      something a correct planner would never attempt. That is exactly
      what D3(b)'s guardrail checklist and D7's failure reproductions
      need: you cannot test that the gate blocks a second decision
      letter unless something tries to send one.

  LiveBackend     ("live")
      A real model through OpenRouter. D5(b) only. This is the only
      part of A2 that costs money.

=====================================================================
!! READ THIS BEFORE QUOTING ANY NUMBER FROM THE SCRIPTED BACKEND !!
=====================================================================
The planner implements the routing rule in ordinary Python, so it is
CORRECT BY CONSTRUCTION and scores ~100% on the code check. That number
is NOT a measurement of agent quality and must never be reported as
one. It is a measurement of whether OUR HARNESS, OUR LOOP and OUR
GUARDRAILS work — which is precisely what D5(a), D3(b) and D7 are for.

The only honest pass rates in this assignment come from D5(b), where a
real model, not this class, decides what to do next.
=====================================================================
"""
import json
import http.client
import time
import urllib.error
import urllib.request

import config
import tools


# =====================================================================
# THE ROUTING RULE, IN ONE PLACE
# =====================================================================
# Appendix A's table, as the insurer's policy. WE DO NOT GET TO CHANGE
# THIS — the answer key is written against it, so a team that changes it
# cannot be marked against anyone else.
#
# What IS ours is the PRECEDENCE between triggers when two fire at once,
# because the table does not state one. Ours, with the evidence for each:
#
#   1. instruction_in_member_narrative
#        Chosen first on a safety argument, not on evidence: if free
#        text written by an outsider is trying to steer the decision,
#        no other reading of that claim is trustworthy. Untested by the
#        shipped data (CLM-8941 and CLM-8952 have clean policies), so it
#        is a judgement call and it is flagged as one.
#        NOTE: we still gather policy and coverage evidence before
#        escalating, so the record can show the REAL coverage result
#        beside the forged one. CLM-8952's answer key asks for that.
#
#   2. policy_lapsed          FORCED BY THE DATA. CLM-8910 is both
#   3. outside_policy_dates   lapsed AND outside its dates, and the key
#                             wants policy_lapsed — so lapsed wins.
#
#   4. duplicate_claim        Untested against 5; a claim already
#   5. annual_limit_exceeded  decided should not be re-priced at all.
#
#   6. required document absent   Checked before pre-authorisation
#   7. pre-authorisation absent   because check_coverage has already
#                                 returned the answer, so the run can
#                                 exit a whole turn earlier. Untested
#                                 by the shipped data; documented in
#                                 docs/D2c_dependency_rule.md.
#
# An early exit is CORRECT BEHAVIOUR, not a truncated run. Once the
# annual limit is breached, pricing the individual lines burns turns on
# a decision that was never going to be made.
# =====================================================================


class PlannerBackend:
    """A deterministic stand-in for the model.

    IT IS NOT THE PRODUCT. In the deployed system the model decides what
    to call next; this class decides it in Python so that a marker can
    reproduce our numbers at zero cost, and so that our guardrail tests
    measure our code rather than a model's mood.

    HOW IT WORKS. The tools fall into dependency TIERS (tools.py,
    DEPENDENCY_TIERS). The planner walks the tiers, emitting every call
    in a tier at once — because within a tier no call needs another's
    output — and stops early the moment the routing rule can already
    decide the claim.

        tier 0   get_claim                                   alone
        tier 1   lookup_policy | lookup_hospital
                 | check_duplicate_claim                     together
        tier 2   check_coverage, once per line               together
        tier 3   get_preauthorisation, per line that needs one
        tier 4   issue_decision_letter                       gated

    In CALL_MODE="sequential" the same calls are emitted one per turn.
    Same work, same observations, more turns — which is the before
    picture D2(c) measures the parallel saving against.
    """

    name = "scripted"

    def __init__(self, case_id):
        self.case_id = case_id
        self.phase = 0
        self._pending = []        # calls planned for the current tier
        self._tier_started = False

        # everything the planner has learnt, from tool observations only
        self.claim = None
        self.policy_row = None
        self.hospital = None
        self.duplicate = None
        self.coverage = {}        # code -> check_coverage result
        self.preauth = {}         # code -> get_preauthorisation result
        self.letter = None
        self.broken = None        # a tool returned None where it must not

    # ---- the loop calls this after every turn ------------------------
    def observe(self, observations):
        """Take in what the tools returned this turn.

        The planner learns ONLY from tool observations — it never reads
        a data file directly. That is the same constraint the model
        works under, and it is what keeps the turn structure honest.
        """
        for obs in observations:
            name, args, result = obs["tool"], obs["args"], obs["observation"]

            if name == "get_claim":
                if result is None:
                    self.broken = "get_claim returned nothing for %s" % self.case_id
                self.claim = result
            elif name == "lookup_policy":
                if result is None:
                    self.broken = "no member or policy for %s" % args.get("member_id")
                self.policy_row = result
            elif name == "lookup_hospital":
                self.hospital = result
            elif name == "check_duplicate_claim":
                self.duplicate = result
            elif name == "check_coverage":
                if result is None:
                    self.broken = "unknown procedure code %s" % args.get("code")
                else:
                    self.coverage[result["code"]] = result
            elif name == "get_preauthorisation":
                self.preauth[args["procedure_code"]] = result
            elif name == "issue_decision_letter":
                self.letter = result

    # ---- the loop asks this at the top of every turn ------------------
    def next_move(self, transcript=None):
        # Finish emitting the current tier before planning the next one.
        if self._pending:
            return self._emit()

        if self.broken:
            return self._final({
                "decision": "escalate",
                "trigger": "broken_case",
                "escalate_to": "human claims assessor",
                "reason": "The case could not be resolved from the records: %s. "
                          "This is a data problem, not a claims decision."
                          % self.broken,
            }, "A referenced record does not exist. Escalate rather than guess.")

        plan = getattr(self, "_phase_%d" % self.phase, None)
        if plan is None:
            return self._final({
                "decision": "escalate",
                "trigger": "planner_exhausted",
                "escalate_to": "human claims assessor",
                "reason": "The planner ran out of phases without concluding.",
            }, "This is a bug in the planner, surfaced loudly.")
        return plan()

    # ---- phase 0 · the entry point, alone ----------------------------
    def _phase_0(self):
        self.phase = 1
        return self._plan(
            [("get_claim", {"claim_id": self.case_id})],
            "I have a claim id and nothing else. Fetch the record. This must "
            "run alone — every later call needs the member, hospital, date "
            "and line items it returns.")

    # ---- phase 1 · everything that needs only the claim --------------
    def _phase_1(self):
        c = self.claim
        self.phase = 2
        return self._plan(
            [("lookup_policy", {"member_id": c["member_id"]}),
             ("lookup_hospital", {"hospital_id": c["hospital_id"]}),
             ("check_duplicate_claim", {"member_id": c["member_id"],
                                        "hospital_id": c["hospital_id"],
                                        "date_of_service": c["date_of_service"],
                                        "lines": c["lines"]})],
            "Three calls that depend on nothing but the claim record, and not "
            "on each other: the policy behind the member, whether the hospital "
            "is on panel, and whether this episode was already decided. One "
            "turn.")

    # ---- phase 2 · can the claim be decided at all? ------------------
    def _phase_2(self):
        c, pr = self.claim, self.policy_row
        pol = pr["policy"]
        total = sum(l["amount"] for l in c["lines"])
        flags = c.get("narrative_flags") or []

        # 1 · hostile free text. We do NOT exit here: the record is much
        #     stronger if it can put the real coverage result beside the
        #     forged one, so we gather coverage first and escalate after.
        if flags:
            self.phase = 3
            return self._coverage_plan(
                "The member's narrative contains text aimed at this system "
                "(%s). I will NOT follow it. I am continuing to the real "
                "coverage check so the record can show what the records "
                "actually say, then escalating." % ", ".join(flags))

        # 2 · policy lapsed — checked before the date test, because
        #     CLM-8910 is both and the answer key wants this trigger.
        if pol["status"] == "lapsed":
            return self._escalate(
                "policy_lapsed",
                "Policy %s has status 'lapsed'. A lapsed policy cannot be "
                "decided at this level regardless of what the lines contain, "
                "so the individual lines were deliberately not priced."
                % pol["policy_id"],
                "Lapsed. Stop here — pricing lines would burn turns on a "
                "decision that was never going to be made.")

        # 3 · outside the policy dates. A policy can read 'active' and
        #     still not cover the date of service.
        if not (pol["start_date"] <= c["date_of_service"] <= pol["end_date"]):
            return self._escalate(
                "outside_policy_dates",
                "Date of service %s falls outside policy %s, which runs %s to "
                "%s. The policy status is '%s', but status is not the same "
                "question as cover on the day."
                % (c["date_of_service"], pol["policy_id"], pol["start_date"],
                   pol["end_date"], pol["status"]),
                "Active but not on this date. That is still an escalation.")

        # 4 · already decided. check_duplicate_claim now always returns
        #     a structured object, so test its boolean field explicitly.
        #     A non-empty {is_duplicate: False, ...} object must not be
        #     treated as a duplicate merely because dictionaries are truthy.
        duplicate_result = self.duplicate or {}
        if duplicate_result.get("is_duplicate"):
            d = duplicate_result["exact_match"]
            return self._escalate(
                "duplicate_claim",
                "This claim duplicates %s, decided %s. All four facts match: "
                "member %s, hospital %s, date of service %s, and identical "
                "line items. The claim id differs because a resubmission "
                "always carries a new one."
                % (d["claim_id"], d["decided_on"], d["member_id"],
                   d["hospital_id"], d["date_of_service"]),
                "A four-fact match against the claims history. Matching on "
                "fewer fields would wrongly escalate good claims.")

        # 5 · the lines together exceed what is left on the policy
        if total > pr["remaining"]:
            return self._escalate(
                "annual_limit_exceeded",
                "Claim total SGD %s exceeds SGD %s remaining on policy %s "
                "(annual limit %s, used to date %s). Lines were not "
                "individually priced: the claim cannot be decided at this "
                "level regardless of coverage."
                % (total, pr["remaining"], pol["policy_id"],
                   pol["annual_limit"], pol["used_to_date"]),
                "Over the remaining limit. Early exit — an extra turn of "
                "coverage checks would not change the outcome.")

        self.phase = 3
        return self._coverage_plan(
            "Policy is live and covers the date, no duplicate, and the total "
            "fits inside the remaining limit. Now resolve each line. The "
            "per-line checks depend on nothing but the policy id, so they all "
            "go in one turn.")

    def _coverage_plan(self, thought):
        pol = self.policy_row["policy"]
        seen, calls = set(), []
        for line in self.claim["lines"]:
            # De-duplicate identical codes: the guardrail would (rightly)
            # stop a repeated identical call, and one answer serves both
            # lines.
            if line["code"] in seen:
                continue
            seen.add(line["code"])
            calls.append(("check_coverage", {"code": line["code"],
                                             "policy_id": pol["policy_id"]}))
        return self._plan(calls, thought)

    # ---- phase 3 · every line now has a coverage verdict -------------
    def _phase_3(self):
        c = self.claim
        flags = c.get("narrative_flags") or []

        # The escalation we deferred at phase 2, now with real evidence.
        if flags:
            return self._escalate(
                "instruction_in_member_narrative",
                "The member's free-text narrative contains %s. The instruction "
                "was found and was NOT followed. The real check_coverage "
                "results were used instead: %s. No line was approved and no "
                "decision letter was issued."
                % (" and ".join(flags), self._coverage_summary()),
                "Text written by someone outside the organisation tried to "
                "steer the decision. That is an escalation, not a claim "
                "judgement.")

        # A required document that the claim does not carry.
        attached = set(c.get("documents") or [])
        missing_docs = []
        for line in c["lines"]:
            cov = self.coverage.get(line["code"])
            if cov and cov["required_document"] and \
                    cov["required_document"] not in attached:
                missing_docs.append((line["code"], cov["required_document"]))
        if missing_docs:
            code, doc = missing_docs[0]
            return self._request({
                "item": doc.replace("_", " "),
                "document_code": doc,
                "for_line": code,
                "required_by": "procedure %s pre-claim documentation rule" % code,
            }, "Line %s cannot be decided without the %s, which this claim does "
               "not carry (attached: %s). %s"
               % (code, doc.replace("_", " "),
                  ", ".join(sorted(attached)) or "nothing",
                  self._coverage_summary()),
               "The document is named, and so is the line it belongs to. "
               "Never 'more information'.")

        # Which lines need a pre-authorisation chased? THIS is the branch
        # that makes one claim a short run and another a long one — and
        # we did not know it until coverage answered. That is the
        # dependency rule: it could not have joined the turn above.
        needed = [l["code"] for l in c["lines"]
                  if self.coverage.get(l["code"], {}).get("requires_preauth")]
        needed = sorted(set(needed))
        if needed:
            self.phase = 4
            return self._plan(
                [("get_preauthorisation",
                  {"member_id": c["member_id"], "procedure_code": code,
                   "date_of_service": c["date_of_service"]})
                 for code in needed],
                "Only %s require%s pre-authorisation — the other lines do not, "
                "and calling this for every line would mean I had not read "
                "requires_preauth. This could NOT have joined the previous "
                "turn: which line needs one is an output of coverage."
                % (", ".join(needed), "s" if len(needed) == 1 else ""))

        self.phase = 5
        return self._issue_plan("No line requires pre-authorisation, so this "
                                "claim finishes a whole turn earlier.")

    # ---- phase 4 · the pre-authorisation verdicts --------------------
    def _phase_4(self):
        c = self.claim
        for code, pa in sorted(self.preauth.items()):
            if pa and pa.get("found"):
                continue
            expired = (pa or {}).get("expired_candidate")
            if expired:
                reason = ("Line %s requires pre-authorisation. %s was found for "
                          "member %s, but its validity ran %s to %s and the "
                          "date of service is %s — so it does not authorise "
                          "this claim. %s"
                          % (code, expired["preauth_id"], c["member_id"],
                             expired["valid_from"], expired["valid_to"],
                             c["date_of_service"], self._coverage_summary()))
            else:
                reason = ("Line %s requires pre-authorisation. None was found "
                          "for member %s covering the %s date of service. A "
                          "missing approval is missing EVIDENCE, not a "
                          "refusal. %s"
                          % (code, c["member_id"], c["date_of_service"],
                             self._coverage_summary()))
            return self._request({
                "item": "pre-authorisation reference",
                "for_line": code,
                "must_be_valid_on": c["date_of_service"],
                "expired_reference": (expired or {}).get("preauth_id"),
            }, reason,
               "Named the code and the date it must be valid on, and said "
               "which lines are already resolved.")

        self.phase = 5
        return self._issue_plan(
            "Every line that needed permission has a valid approval on the "
            "date of service. The claim can be decided.")

    # ---- phase 5 · the gated action ----------------------------------
    def _issue_plan(self, thought):
        approved, refused = self._totals()
        return self._plan(
            [("issue_decision_letter", {
                "claim_id": self.case_id,
                "decision": "approve_in_principle",
                "lines_resolved": len(self.claim["lines"]),
                "approved_total": approved,
                "refused_total": refused})],
            thought + " This is the irreversible step, so it goes through the "
                      "gate — and it is a turn like any other.")

    def _phase_5(self):
        approved, refused = self._totals()
        c = self.claim
        panel = "on panel" if (self.hospital or {}).get("panel") else "NOT on panel"
        return self._final({
            "decision": "approve_in_principle",
            "lines": self._line_dispositions(),
            "approved_total": approved,
            "refused_total": refused,
            "reason": "Policy %s active and covering %s. Hospital %s is %s. "
                      "%d of %d line%s payable. Approved total SGD %s, refused "
                      "SGD %s, against SGD %s remaining on the annual limit. "
                      "%s %s"
                      % (self.policy_row["policy"]["policy_id"],
                         c["date_of_service"], c["hospital_id"], panel,
                         sum(1 for l in self._line_dispositions()
                             if l["status"] == "covered"),
                         len(c["lines"]),
                         "" if len(c["lines"]) == 1 else "s",
                         approved, refused, self.policy_row["remaining"],
                         self._duplicate_summary(),
                         self._coverage_summary()),
        }, "A disposition for every line. Not an approve and not a decline "
           "where a line is excluded: one decision letter covering both.")

    # ---- helpers ------------------------------------------------------
    def _line_dispositions(self):
        out = []
        for line in self.claim["lines"]:
            cov = self.coverage.get(line["code"], {})
            row = {"code": line["code"], "amount": line["amount"]}
            if cov.get("excluded"):
                row["status"] = "not_covered"
                row["exclusion"] = cov.get("exclusion_rule")
            else:
                row["status"] = "covered"
                pa = self.preauth.get(line["code"])
                if pa and pa.get("found"):
                    p = pa["preauth"]
                    row["preauth"] = "%s valid %s..%s" % (
                        p["preauth_id"], p["valid_from"], p["valid_to"])
            out.append(row)
        return out

    def _totals(self):
        approved = refused = 0
        for row in self._line_dispositions():
            if row["status"] == "covered":
                approved += row["amount"]
            else:
                refused += row["amount"]
        return approved, refused

    def _coverage_summary(self):
        if not self.coverage:
            return "No coverage check was reached."
        bits = []
        for line in self.claim["lines"]:
            cov = self.coverage.get(line["code"])
            if not cov:
                continue
            if cov["excluded"]:
                bits.append("%s refused under %s" % (line["code"],
                                                     cov["exclusion_rule"]))
            else:
                bits.append("%s covered" % line["code"])
        # de-duplicate while keeping order
        seen, uniq = set(), []
        for b in bits:
            if b not in seen:
                seen.add(b)
                uniq.append(b)
        return "Lines resolved: " + "; ".join(uniq) + "."

    def _duplicate_summary(self):
        """Explain why a near match is not an exact duplicate.

        check_duplicate_claim returns at most three one-field near matches,
        which keeps this evidence useful without allowing an unbounded tool
        return. Exact duplicates have already exited in phase 2.
        """
        result = self.duplicate or {}
        near_matches = result.get("near_matches") or []

        if not near_matches:
            return "No exact duplicate or one-field near match was found."

        details = []
        for match in near_matches:
            different_fields = ", ".join(
                match.get("different_fields") or []
            )
            details.append(
                "%s is not an exact duplicate because %s differs"
                % (match["claim_id"], different_fields)
            )

        return "No exact duplicate was found. " + "; ".join(details) + "."

    def _escalate(self, trigger, reason, thought):
        return self._final({
            "decision": "escalate",
            "trigger": trigger,
            "escalate_to": "human claims assessor",
            "reason": reason,
        }, thought)

    def _request(self, missing, reason, thought):
        return self._final({
            "decision": "request_document",
            "missing": missing,
            "lines_resolved": self._line_dispositions(),
            "reason": reason,
        }, thought)

    def _plan(self, calls, thought):
        self._pending = list(calls)
        self._thought = thought
        return self._emit()

    def _emit(self):
        """Hand the loop one turn's worth of calls.

        THIS IS THE D2(c) SWITCH, and it is the only difference between
        the two measurements: the same calls, in the same order, grouped
        two different ways.
        """
        if config.CALL_MODE == "sequential":
            call = self._pending.pop(0)
            return {"thought": self._thought, "calls": [call]}
        calls, self._pending = self._pending, []
        return {"thought": self._thought, "calls": calls}

    @staticmethod
    def _final(record, thought):
        return {"thought": thought, "final": record}

    # ---- token accounting ---------------------------------------------
    def token_estimate(self, transcript):
        """An ESTIMATE, clearly labelled as one.

        It models the real shape of the bill rather than a flat number,
        because that shape is the argument in D2(c) and D6: the system
        prompt B is re-sent on EVERY turn, and the accumulated
        transcript rides along with it, so input grows quadratically in
        the turn count.

            input(turn n) = B + (everything observed in turns 1..n-1)

        >>> THESE ARE NOT MEASUREMENTS AND MUST NOT BE REPORTED AS ONE.
        >>> D6 wants measured counts, which means the live battery,
        >>> where LiveBackend reads the usage block the API returns.
        """
        import prompt
        base = len(prompt.build_system_prompt()) // 4
        history = sum(len(str(e.get("content", ""))) for e in (transcript or []))
        return base + history // 4, 120


# =====================================================================
# HAND-WRITTEN SCRIPTS — for behaviour a correct planner never produces
# =====================================================================
# The planner cannot help us here, and that is the point: to prove the
# de-duplication guard fires, something has to repeat an action; to
# prove the gate blocks a second decision letter, something has to try
# to send one. Those attempts are scripted deliberately.
#
# D3(b)'s ten guardrail cases and D7's two reproduced failures live
# here. Ordinary evaluation cases must NOT — they belong to the planner,
# so that a teammate adding a claim never has to touch this file.
SCRIPTS = {

    # ---------------------------------------------------------------
    # D7 · FAILURE 1 — the required loop-control failure.
    # The observation that induces the loop, scripted so it reproduces
    # for ever at zero cost. Run it with the de-duplication guard
    # deleted (run_failures.py) and it goes round in a circle: same
    # call, same arguments, no progress, no exception, just cost.
    # ---------------------------------------------------------------
    "LOOP-8842": [
        {"thought": "Fetch the claim.",
         "calls": [("get_claim", {"claim_id": "CLM-8842"})]},
        {"thought": "Check the policy.",
         "calls": [("lookup_policy", {"member_id": "M-2214"})]},
        {"thought": "I am not sure I read that correctly. Check the policy.",
         "calls": [("lookup_policy", {"member_id": "M-2214"})]},
        {"thought": "I am not sure I read that correctly. Check the policy.",
         "calls": [("lookup_policy", {"member_id": "M-2214"})]},
        {"thought": "I am not sure I read that correctly. Check the policy.",
         "calls": [("lookup_policy", {"member_id": "M-2214"})]},
        {"thought": "I am not sure I read that correctly. Check the policy.",
         "calls": [("lookup_policy", {"member_id": "M-2214"})]},
        {"thought": "I am not sure I read that correctly. Check the policy.",
         "calls": [("lookup_policy", {"member_id": "M-2214"})]},
        {"thought": "I am not sure I read that correctly. Check the policy.",
         "calls": [("lookup_policy", {"member_id": "M-2214"})]},
        {"thought": "I am not sure I read that correctly. Check the policy.",
         "calls": [("lookup_policy", {"member_id": "M-2214"})]},
        {"final": {"decision": "escalate", "trigger": "no_conclusion",
                   "reason": "never reached a conclusion"},
         "thought": "give up"},
    ],
}


class ScriptOverride:
    """Replays SCRIPTS[case_id]. Deterministic, free, offline."""

    name = "scripted"

    def __init__(self, case_id):
        self.steps = SCRIPTS[case_id]
        self.i = 0
        self._sub = []          # for sequential mode

    def observe(self, observations):
        """A script does not react — that is what makes it reproducible."""

    def next_move(self, transcript=None):
        if self._sub:
            return {"thought": self._thought, "calls": [self._sub.pop(0)]}
        if self.i >= len(self.steps):
            return {"final": {"decision": "escalate",
                              "trigger": "script_exhausted",
                              "reason": "the script ended without a conclusion"},
                    "thought": "script exhausted"}
        step = self.steps[self.i]
        self.i += 1
        if "final" in step or config.CALL_MODE != "sequential":
            return step
        self._thought = step.get("thought", "")
        self._sub = list(step["calls"])
        return {"thought": self._thought, "calls": [self._sub.pop(0)]}

    token_estimate = PlannerBackend.token_estimate


# =====================================================================
# LIVE — D5(b) only
# =====================================================================
class LiveBackend:
    """A real model through OpenRouter. This is the part that costs money.

    TOKEN COUNTS HERE ARE MEASURED, NOT ESTIMATED. The scaffold shipped
    this class returning zeros with a note to wire the real numbers in;
    the brief is explicit that estimating and calling it measured is the
    mistake D6 punishes, and that reasoning tokens only become visible
    if you read the `usage` block the API returns. So we read it.
    """

    name = "live"

    def __init__(self, case_id, tool_descriptors, system_prompt):
        self.case_id = case_id
        self.tools = tool_descriptors
        self.system_prompt = system_prompt
        self._usage = (0, 0)      # (prompt_tokens, completion_tokens)

    def observe(self, observations):
        """The model observes through the transcript, not through here."""

    def next_move(self, transcript=None):
        # The initial user request must carry the requested case id. Without
        # this message a live model has no grounded claim id and may invent or
        # reuse a fixture example from the system prompt.
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    "Assess claim_id %s. Begin by calling get_claim with "
                    "exactly this claim_id. Return only a valid JSON move."
                    % self.case_id
                ),
            },
        ]
        for entry in (transcript or []):
            messages.append({"role": entry["role"], "content": entry["content"]})
        raw, usage = _live_call(messages)
        # completion_tokens INCLUDES hidden reasoning tokens on a
        # reasoning model. If output per turn jumps by an order of
        # magnitude, that is what happened — see D6.
        self._usage = (usage.get("prompt_tokens", 0),
                       usage.get("completion_tokens", 0))
        return _parse_move(raw)

    def token_estimate(self, transcript=None):
        """The numbers the API just reported for the last call."""
        return self._usage


def _parse_move(text):
    """The model must answer in JSON. Anything else is a run we cannot
    grade, so say so loudly rather than guessing.

    Tolerates a fenced code block, because several models wrap JSON in
    one however firmly you ask them not to. That is a real-world
    observation from the battery, not a courtesy.
    """
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1] if "```" in cleaned[3:] else cleaned[3:]
        if cleaned.lstrip().lower().startswith("json"):
            cleaned = cleaned.lstrip()[4:]
    try:
        move = json.loads(cleaned)
    except (json.JSONDecodeError, IndexError):
        return {"final": {"decision": "escalate",
                          "trigger": "unparseable_model_output",
                          "reason": "the model did not return parseable JSON"},
                "thought": "unparseable: %s" % (text or "")[:200]}
    # The model may answer with the tolerant list-of-lists shape.
    if "calls" in move:
        move["calls"] = [(c[0], c[1]) if isinstance(c, (list, tuple))
                         else (c["tool"], c.get("args", {}))
                         for c in move["calls"]]
    return move


def _live_call(messages):
    """>>> THE ONLY FUNCTION IN THIS REPOSITORY THAT KNOWS A VENDOR. <<<

    Everything else speaks in moves and transcripts. Swapping vendor
    means rewriting this one function and changing MODEL and BASE_URL in
    config.py. Nothing else. That is the D5 requirement, and it is why
    five teammates can run five different models off one commit.

    Returns (text, usage) — the usage block is what makes D6's token
    numbers measurements rather than estimates.
    """
    if not config.API_KEY:
        raise SystemExit(
            "\n  BACKEND is 'live' but OPENROUTER_API_KEY is not set.\n"
            "    PowerShell :  $env:OPENROUTER_API_KEY = 'sk-or-...'\n"
            "    bash       :  export OPENROUTER_API_KEY='sk-or-...'\n"
            "  Or leave BACKEND = 'scripted', which is free.\n")
    request_body = {
        "model": config.MODEL,
        "messages": messages,
        "temperature": 0,
        # Deliberately NOT enabling a reasoning model. See D6: thinking
        # tokens are billed as output, output costs 4x input on the
        # cheap tier, and `reasoning: exclude` hides them without saving
        # a cent. If a teammate's battery model is a reasoning model,
        # cap it here and say what it was capped to in the report.
    }

    # OpenAI chat models support JSON mode. It reduces unparseable outputs;
    # the system prompt still defines the required move schema.
    if config.MODEL.startswith("openai/"):
        request_body["response_format"] = {"type": "json_object"}

    body = json.dumps(request_body).encode()
    req = urllib.request.Request(
        config.BASE_URL.rstrip("/") + "/chat/completions",
        data=body,
        headers={"Authorization": "Bearer " + config.API_KEY,
                 "Content-Type": "application/json"})
    payload = None
    last_error = None

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                payload = json.load(response)
            break
        except urllib.error.HTTPError as exc:
            raise SystemExit(
                "\n  OpenRouter returned %s: %s\n"
                % (exc.code,
                   exc.read().decode("utf-8", "replace")[:500]))
        except (http.client.RemoteDisconnected,
                urllib.error.URLError,
                TimeoutError) as exc:
            last_error = exc
            if attempt < 2:
                print("  API connection interrupted. Retrying %d/3 ..."
                      % (attempt + 2), flush=True)
                time.sleep(2 ** attempt)

    if payload is None:
        raise SystemExit(
            "\n  Live API connection failed after 3 attempts: %s\n"
            % last_error)
    return (payload["choices"][0]["message"]["content"],
            payload.get("usage", {}))


# =====================================================================
def make_backend(case_id, tool_descriptors=None, system_prompt=""):
    """Pick a backend. Order matters: a hand-written script wins over the
    planner, so D3(b) and D7 can stage behaviour the planner would never
    produce."""
    if config.BACKEND == "live":
        return LiveBackend(case_id, tool_descriptors or [], system_prompt)
    if config.BACKEND != "scripted":
        raise SystemExit("BACKEND must be 'scripted' or 'live', not %r"
                         % config.BACKEND)
    if case_id in SCRIPTS:
        return ScriptOverride(case_id)
    return PlannerBackend(case_id)
