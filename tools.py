
from pathlib import Path
import json


DATA_DIR = Path(__file__).resolve().parent / "data_A"

ALLOWED_TABLES = {
    "claims",
    "members",
    "policies",
    "hospitals",
    "procedures",
    "preauthorisations",
    "required_documents",
    "decided_claims",
}


def load_table(name):
    """Load one permitted Problem A JSON table."""

    if name not in ALLOWED_TABLES:
        raise ValueError(f"Unknown table: {name}")

    path = DATA_DIR / f"{name}.json"

    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        rows = json.load(file)

    if not isinstance(rows, list):
        raise ValueError(f"{name}.json must contain a JSON list")

    return rows


def find_one(rows, field, value):
    """Return the first matching row, or None."""

    return next(
        (row for row in rows if row.get(field) == value),
        None,
    )


def tool_result(ok, data=None, error=None):
    """Return a consistent structure from every tool."""

    result = {"ok": bool(ok)}

    if data is not None:
        result["data"] = data

    if error is not None:
        result["error"] = error

    return result


def lookup_policy(member_id):
    """Retrieve a member and the insurance policy linked to that member."""

    if not isinstance(member_id, str) or not member_id.strip():
        return tool_result(
            False,
            error={
                "code": "invalid_member_id",
                "message": "member_id must be a non-empty string",
            },
        )

    member_id = member_id.strip()

    members = load_table("members")
    member = find_one(members, "member_id", member_id)

    if member is None:
        return tool_result(
            False,
            error={
                "code": "member_not_found",
                "message": f"Member {member_id} was not found",
            },
        )

    policy_id = member.get("policy_id")

    if not policy_id:
        return tool_result(
            False,
            error={
                "code": "missing_policy_id",
                "message": f"Member {member_id} has no policy_id",
            },
        )

    policies = load_table("policies")
    policy = find_one(policies, "policy_id", policy_id)

    if policy is None:
        return tool_result(
            False,
            error={
                "code": "policy_not_found",
                "message": f"Policy {policy_id} was not found",
            },
        )

    annual_limit = policy.get("annual_limit")
    used_to_date = policy.get("used_to_date")

    if not isinstance(annual_limit, (int, float)):
        return tool_result(
            False,
            error={
                "code": "invalid_annual_limit",
                "message": f"Policy {policy_id} has an invalid annual_limit",
            },
        )

    if not isinstance(used_to_date, (int, float)):
        return tool_result(
            False,
            error={
                "code": "invalid_used_to_date",
                "message": f"Policy {policy_id} has an invalid used_to_date",
            },
        )

    policy_data = dict(policy)
    policy_data["remaining_limit"] = annual_limit - used_to_date

    return tool_result(
        True,
        data={
            "member": dict(member),
            "policy": policy_data,
        },
    )


def get_hospital_status(hospital_id):
    """Retrieve a hospital and its panel status."""

    if not isinstance(hospital_id, str) or not hospital_id.strip():
        return tool_result(
            False,
            error={
                "code": "invalid_hospital_id",
                "message": "hospital_id must be a non-empty string",
            },
        )

    hospital_id = hospital_id.strip()

    hospitals = load_table("hospitals")
    hospital = find_one(
        hospitals,
        "hospital_id",
        hospital_id,
    )

    if hospital is None:
        return tool_result(
            False,
            error={
                "code": "hospital_not_found",
                "message": f"Hospital {hospital_id} was not found",
            },
        )

    panel = hospital.get("panel")

    if not isinstance(panel, bool):
        return tool_result(
            False,
            error={
                "code": "invalid_panel_status",
                "message": f"Hospital {hospital_id} has an invalid panel status",
            },
        )

    return tool_result(
        True,
        data={
            "hospital_id": hospital["hospital_id"],
            "name": hospital.get("name"),
            "panel": panel,
            "country": hospital.get("country"),
        },
    )


def get_preauthorisation(member_id, procedure_code, date_of_service):
    """Find a pre-authorisation and check whether it is valid on the service date."""

    from datetime import date

    inputs = {
        "member_id": member_id,
        "procedure_code": procedure_code,
        "date_of_service": date_of_service,
    }

    for field, value in inputs.items():
        if not isinstance(value, str) or not value.strip():
            return tool_result(
                False,
                error={
                    "code": f"invalid_{field}",
                    "message": f"{field} must be a non-empty string",
                },
            )

    member_id = member_id.strip()
    procedure_code = procedure_code.strip()
    date_of_service = date_of_service.strip()

    try:
        service_date = date.fromisoformat(date_of_service)
    except ValueError:
        return tool_result(
            False,
            error={
                "code": "invalid_date_of_service",
                "message": "date_of_service must use YYYY-MM-DD format",
            },
        )

    authorisations = load_table("preauthorisations")

    matches = [
        row for row in authorisations
        if row.get("member_id") == member_id
        and row.get("procedure_code") == procedure_code
    ]

    if not matches:
        return tool_result(
            True,
            data={
                "found": False,
                "valid_on_service_date": False,
                "status": "not_found",
                "member_id": member_id,
                "procedure_code": procedure_code,
                "date_of_service": date_of_service,
                "preauthorisation": None,
            },
        )

    dated_matches = []

    for row in matches:
        try:
            valid_from = date.fromisoformat(row["valid_from"])
            valid_to = date.fromisoformat(row["valid_to"])
        except (KeyError, TypeError, ValueError):
            return tool_result(
                False,
                error={
                    "code": "invalid_preauthorisation_dates",
                    "message": (
                        f"Pre-authorisation {row.get('preauth_id')} "
                        "contains invalid dates"
                    ),
                },
            )

        dated_matches.append((row, valid_from, valid_to))

        if valid_from <= service_date <= valid_to:
            return tool_result(
                True,
                data={
                    "found": True,
                    "valid_on_service_date": True,
                    "status": "valid",
                    "member_id": member_id,
                    "procedure_code": procedure_code,
                    "date_of_service": date_of_service,
                    "preauthorisation": dict(row),
                },
            )

    latest_row, latest_from, latest_to = max(
        dated_matches,
        key=lambda item: item[2],
    )

    if service_date > latest_to:
        status = "expired"
    elif service_date < latest_from:
        status = "not_yet_valid"
    else:
        status = "no_valid_authorisation"

    return tool_result(
        True,
        data={
            "found": True,
            "valid_on_service_date": False,
            "status": status,
            "member_id": member_id,
            "procedure_code": procedure_code,
            "date_of_service": date_of_service,
            "preauthorisation": dict(latest_row),
        },
    )


def check_coverage(
    policy_id,
    procedure_code,
    date_of_service,
    attached_documents,
):
    """Check policy and procedure facts for one claim line."""

    from datetime import date

    text_inputs = {
        "policy_id": policy_id,
        "procedure_code": procedure_code,
        "date_of_service": date_of_service,
    }

    for field, value in text_inputs.items():
        if not isinstance(value, str) or not value.strip():
            return tool_result(
                False,
                error={
                    "code": f"invalid_{field}",
                    "message": f"{field} must be a non-empty string",
                },
            )

    if not isinstance(attached_documents, list):
        return tool_result(
            False,
            error={
                "code": "invalid_attached_documents",
                "message": "attached_documents must be a list",
            },
        )

    policy_id = policy_id.strip()
    procedure_code = procedure_code.strip()
    date_of_service = date_of_service.strip()

    try:
        service_date = date.fromisoformat(date_of_service)
    except ValueError:
        return tool_result(
            False,
            error={
                "code": "invalid_date_of_service",
                "message": "date_of_service must use YYYY-MM-DD format",
            },
        )

    policies = load_table("policies")
    policy = find_one(policies, "policy_id", policy_id)

    if policy is None:
        return tool_result(
            False,
            error={
                "code": "policy_not_found",
                "message": f"Policy {policy_id} was not found",
            },
        )

    procedures = load_table("procedures")
    procedure = find_one(
        procedures,
        "code",
        procedure_code,
    )

    if procedure is None:
        return tool_result(
            False,
            error={
                "code": "procedure_not_found",
                "message": f"Procedure {procedure_code} was not found",
            },
        )

    try:
        policy_start = date.fromisoformat(policy["start_date"])
        policy_end = date.fromisoformat(policy["end_date"])
    except (KeyError, TypeError, ValueError):
        return tool_result(
            False,
            error={
                "code": "invalid_policy_dates",
                "message": f"Policy {policy_id} contains invalid dates",
            },
        )

    within_policy_dates = (
        policy_start <= service_date <= policy_end
    )

    exclusions = policy.get("exclusions", [])

    if not isinstance(exclusions, list):
        return tool_result(
            False,
            error={
                "code": "invalid_exclusions",
                "message": f"Policy {policy_id} has invalid exclusions",
            },
        )

    exclusion = next(
        (
            item for item in exclusions
            if item.get("code") == procedure_code
        ),
        None,
    )

    document_rules = load_table("required_documents")
    document_rule = find_one(
        document_rules,
        "procedure_code",
        procedure_code,
    )

    required_document = (
        document_rule.get("document")
        if document_rule is not None
        else None
    )

    document_present = (
        True
        if required_document is None
        else required_document in attached_documents
    )

    policy_active = policy.get("status") == "active"
    excluded = exclusion is not None

    policy_eligible = (
        policy_active
        and within_policy_dates
        and not excluded
    )

    return tool_result(
        True,
        data={
            "policy_id": policy_id,
            "procedure_code": procedure_code,
            "date_of_service": date_of_service,
            "policy_status": policy.get("status"),
            "within_policy_dates": within_policy_dates,
            "procedure_description": procedure.get("description"),
            "requires_preauth": procedure.get("requires_preauth"),
            "excluded": excluded,
            "exclusion_rule": (
                exclusion.get("rule")
                if exclusion is not None
                else None
            ),
            "required_document": required_document,
            "document_present": document_present,
            "policy_eligible": policy_eligible,
        },
    )


def _normalise_lines(lines):
    """Create an order-independent representation of claim lines."""

    if not isinstance(lines, list):
        return None

    normalised = []

    for line in lines:
        if not isinstance(line, dict):
            return None

        code = line.get("code")
        amount = line.get("amount")

        if code is None or not isinstance(amount, (int, float)):
            return None

        normalised.append((str(code), amount))

    return sorted(normalised)


def _find_decided_claim_match(claim):
    """Find a prior decision matching all four duplicate-claim facts."""

    claim_lines = _normalise_lines(claim.get("lines"))

    if claim_lines is None:
        return None

    decided_claims = load_table("decided_claims")

    for prior in decided_claims:
        same_member = (
            prior.get("member_id") == claim.get("member_id")
        )
        same_hospital = (
            prior.get("hospital_id") == claim.get("hospital_id")
        )
        same_date = (
            prior.get("date_of_service")
            == claim.get("date_of_service")
        )
        same_lines = (
            _normalise_lines(prior.get("lines")) == claim_lines
        )

        if (
            same_member
            and same_hospital
            and same_date
            and same_lines
        ):
            return prior

    return None


def get_claim(claim_id):
    """Retrieve a claim, calculate totals, and check decided history."""

    if not isinstance(claim_id, str) or not claim_id.strip():
        return tool_result(
            False,
            error={
                "code": "invalid_claim_id",
                "message": "claim_id must be a non-empty string",
            },
        )

    claim_id = claim_id.strip()
    claims = load_table("claims")
    claim = find_one(claims, "claim_id", claim_id)

    if claim is None:
        return tool_result(
            False,
            error={
                "code": "claim_not_found",
                "message": f"Claim {claim_id} was not found",
            },
        )

    claim_data = dict(claim)
    lines = claim_data.get("lines", [])

    if not isinstance(lines, list):
        return tool_result(
            False,
            error={
                "code": "invalid_claim_lines",
                "message": f"Claim {claim_id} has invalid lines data",
            },
        )

    claim_total = 0

    for line in lines:
        amount = line.get("amount")

        if not isinstance(amount, (int, float)):
            return tool_result(
                False,
                error={
                    "code": "invalid_line_amount",
                    "message": f"Claim {claim_id} contains an invalid amount",
                },
            )

        claim_total += amount

    prior_match = _find_decided_claim_match(claim)

    claim_data["line_count"] = len(lines)
    claim_data["claim_total"] = claim_total
    claim_data["is_duplicate_of_decided_claim"] = (
        prior_match is not None
    )
    claim_data["prior_decision_match"] = (
        dict(prior_match)
        if prior_match is not None
        else None
    )

    return tool_result(True, data=claim_data)


VALID_DECISIONS = {
    "approve_in_principle",
    "request_document",
    "escalate",
}

DECISIONS_PATH = (
    Path(__file__).resolve().parent / "decisions.jsonl"
)


def _load_decision_log():
    """Load existing JSONL decision records."""

    if not DECISIONS_PATH.exists():
        return []

    records = []

    with DECISIONS_PATH.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on decisions.jsonl line "
                    f"{line_number}"
                ) from exc

            if not isinstance(record, dict):
                raise ValueError(
                    f"Decision record on line {line_number} "
                    "must be a JSON object"
                )

            records.append(record)

    return records


def issue_decision_letter(
    claim_id,
    decision,
    reason,
    evidence,
    operator_confirmed=False,
    turns=None,
    cost_usd=None,
):
    """Record one confirmed first-response decision."""

    from datetime import datetime, timezone

    if not isinstance(claim_id, str) or not claim_id.strip():
        return tool_result(
            False,
            error={
                "code": "invalid_claim_id",
                "message": "claim_id must be a non-empty string",
            },
        )

    claim_id = claim_id.strip()

    if decision not in VALID_DECISIONS:
        return tool_result(
            False,
            error={
                "code": "invalid_decision",
                "message": (
                    f"decision must be one of "
                    f"{sorted(VALID_DECISIONS)}"
                ),
            },
        )

    if not isinstance(reason, str) or not reason.strip():
        return tool_result(
            False,
            error={
                "code": "invalid_reason",
                "message": "reason must be a non-empty string",
            },
        )

    if (
        not isinstance(evidence, list)
        or not evidence
        or not all(
            isinstance(item, str) and item.strip()
            for item in evidence
        )
    ):
        return tool_result(
            False,
            error={
                "code": "invalid_evidence",
                "message": (
                    "evidence must be a non-empty list "
                    "of non-empty strings"
                ),
            },
        )

    if not isinstance(operator_confirmed, bool):
        return tool_result(
            False,
            error={
                "code": "invalid_confirmation",
                "message": "operator_confirmed must be a boolean",
            },
        )

    if (
        turns is not None
        and (
            isinstance(turns, bool)
            or not isinstance(turns, int)
            or turns < 0
        )
    ):
        return tool_result(
            False,
            error={
                "code": "invalid_turns",
                "message": "turns must be a non-negative integer",
            },
        )

    if (
        cost_usd is not None
        and (
            isinstance(cost_usd, bool)
            or not isinstance(cost_usd, (int, float))
            or cost_usd < 0
        )
    ):
        return tool_result(
            False,
            error={
                "code": "invalid_cost",
                "message": "cost_usd must be a non-negative number",
            },
        )

    claim_result = get_claim(claim_id)

    if not claim_result["ok"]:
        return claim_result

    if not operator_confirmed:
        return tool_result(
            False,
            error={
                "code": "awaiting_operator_confirmation",
                "message": (
                    "BLOCKED: awaiting operator confirmation"
                ),
            },
        )

    try:
        existing_records = _load_decision_log()
    except ValueError as exc:
        return tool_result(
            False,
            error={
                "code": "invalid_decision_log",
                "message": str(exc),
            },
        )

    already_recorded = any(
        record.get("case_id") == claim_id
        or record.get("claim_id") == claim_id
        for record in existing_records
    )

    if already_recorded:
        return tool_result(
            False,
            error={
                "code": "decision_already_exists",
                "message": (
                    "BLOCKED: duplicate - "
                    "a decision already exists"
                ),
            },
        )

    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "case_id": claim_id,
        "decision": decision,
        "reason": reason.strip(),
        "evidence": [item.strip() for item in evidence],
        "autonomy": "confirm",
        "operator_confirmed": True,
        "turns": turns,
        "cost_usd": cost_usd,
    }

    DECISIONS_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with DECISIONS_PATH.open("a", encoding="utf-8") as file:
        file.write(
            json.dumps(record, ensure_ascii=False) + "\n"
        )

    return tool_result(
        True,
        data={
            "status": "recorded",
            "record": record,
        },
    )
