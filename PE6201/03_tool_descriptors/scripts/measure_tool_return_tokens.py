import json
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import tiktoken

PE6201_ROOT = Path(__file__).resolve().parents[2]
SHARED_RUNTIME = PE6201_ROOT / "shared_runtime"
if str(SHARED_RUNTIME) not in sys.path:
    sys.path.insert(0, str(SHARED_RUNTIME))

import config
import tools


# The repository's default model is gpt-4o-mini.
ENCODING = tiktoken.get_encoding("o200k_base")


def count_tokens(result):
    """Count tokens in the representation returned to the agent."""
    return len(ENCODING.encode(repr(result)))


def load_json(path):
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def summarise(name, results):
    counts = [count_tokens(result) for result in results]

    print(
        f"{name:<28}"
        f"calls={len(counts):>3}  "
        f"mean={statistics.mean(counts):>6.2f}  "
        f"median={statistics.median(counts):>5.1f}  "
        f"min={min(counts):>3}  "
        f"max={max(counts):>3}  "
        f"total={sum(counts):>5}"
    )

    return {
        "calls": len(counts),
        "mean": round(statistics.mean(counts), 2),
        "median": statistics.median(counts),
        "minimum": min(counts),
        "maximum": max(counts),
        "total": sum(counts),
    }


def get_preauthorisation_v1(
    member_id,
    procedure_code,
    date_of_service,
    preauthorisations,
):
    """
    V1 return shape:
    Return the valid pre-authorisation row, otherwise return None.

    This loses the difference between:
    1. no authorisation exists; and
    2. one exists but has expired.
    """
    for preauth in preauthorisations:
        same_member = preauth["member_id"] == member_id
        same_procedure = preauth["procedure_code"] == procedure_code

        if not same_member or not same_procedure:
            continue

        valid_on_date = (
            preauth["valid_from"]
            <= date_of_service
            <= preauth["valid_to"]
        )

        if valid_on_date:
            return preauth

    return None


def main():
    data_root = Path(config.data_root())
    data_a = data_root / "data_A"

    claims = load_json(data_a / "claims.json")
    members = {
        row["member_id"]: row
        for row in load_json(data_a / "members.json")
    }
    procedures = {
        row["code"]: row
        for row in load_json(data_a / "procedures.json")
    }
    preauthorisations = load_json(
        data_a / "preauthorisations.json"
    )

    expected_outcomes = {
        row["case_id"]: row
        for row in load_json(
            data_root / "expected_outcomes_A.json"
        )
    }

    tool_results = {
        "get_claim": [],
        "lookup_policy": [],
        "lookup_hospital": [],
        "check_coverage": [],
        "get_preauthorisation_v2": [],
        "check_duplicate_claim": [],
        "issue_decision_letter": [],
    }

    pa_v1_results = []
    pa_v2_results = []
    pa_case_rows = []

    for claim in claims:
        claim_id = claim["claim_id"]
        member_id = claim["member_id"]
        hospital_id = claim["hospital_id"]
        date_of_service = claim["date_of_service"]
        lines = claim["lines"]

        claim_result = tools.get_claim(claim_id)
        tool_results["get_claim"].append(claim_result)

        policy_result = tools.lookup_policy(member_id)
        tool_results["lookup_policy"].append(policy_result)

        hospital_result = tools.lookup_hospital(hospital_id)
        tool_results["lookup_hospital"].append(
            hospital_result
        )

        policy_id = members[member_id]["policy_id"]

        approved_total = 0
        refused_total = 0

        for line in lines:
            code = line["code"]
            amount = line["amount"]

            coverage_result = tools.check_coverage(
                code,
                policy_id,
            )

            tool_results["check_coverage"].append(
                coverage_result
            )

            if coverage_result["excluded"]:
                refused_total += amount
            else:
                approved_total += amount

            if procedures[code]["requires_preauth"]:
                v1_result = get_preauthorisation_v1(
                    member_id,
                    code,
                    date_of_service,
                    preauthorisations,
                )

                v2_result = tools.get_preauthorisation(
                    member_id,
                    code,
                    date_of_service,
                )

                pa_v1_results.append(v1_result)
                pa_v2_results.append(v2_result)

                tool_results[
                    "get_preauthorisation_v2"
                ].append(v2_result)

                pa_case_rows.append(
                    {
                        "claim_id": claim_id,
                        "procedure_code": code,
                        "v1_tokens": count_tokens(v1_result),
                        "v2_tokens": count_tokens(v2_result),
                    }
                )

        duplicate_result = tools.check_duplicate_claim(
            member_id,
            hospital_id,
            date_of_service,
            lines,
        )

        tool_results["check_duplicate_claim"].append(
            duplicate_result
        )

        expected = expected_outcomes[claim_id]
        decision = expected["expected_decision"]

        confirmation_result = tools.issue_decision_letter(
            claim_id=claim_id,
            decision=decision,
            lines_resolved=len(lines),
            approved_total=approved_total,
            refused_total=refused_total,
        )

        tool_results["issue_decision_letter"].append(
            confirmation_result
        )

    print()
    print("=" * 86)
    print("CURRENT V2 TOOL RETURN TOKEN MEASUREMENTS")
    print("=" * 86)
    print("Tokenizer: o200k_base")
    print("Serialisation: repr(result)")
    print("Fixture set: 38 Problem A claims")
    print()

    all_tool_summary = {}

    for tool_name, results in tool_results.items():
        all_tool_summary[tool_name] = summarise(
            tool_name,
            results,
        )

    print()
    print("=" * 86)
    print("GET_PREAUTHORISATION V1 VERSUS V2")
    print("=" * 86)
    print()

    v1_summary = summarise(
        "get_preauthorisation V1",
        pa_v1_results,
    )

    v2_summary = summarise(
        "get_preauthorisation V2",
        pa_v2_results,
    )

    print()
    difference = (
        v2_summary["mean"] - v1_summary["mean"]
    )

    print(
        "Mean difference: "
        f"{difference:+.2f} tokens per call"
    )

    print()
    print("Per-case results:")
    print(
        f"{'Claim':<12}"
        f"{'Procedure':<12}"
        f"{'V1 tokens':>12}"
        f"{'V2 tokens':>12}"
    )
    print("-" * 48)

    for row in pa_case_rows:
        print(
            f"{row['claim_id']:<12}"
            f"{row['procedure_code']:<12}"
            f"{row['v1_tokens']:>12}"
            f"{row['v2_tokens']:>12}"
        )

    clm_8894 = next(
        (
            row
            for row in pa_case_rows
            if row["claim_id"] == "CLM-8894"
        ),
        None,
    )

    if clm_8894:
        print()
        print("CLM-8894 failure evidence:")
        print(
            "V1 returned None: "
            f"{clm_8894['v1_tokens']} token"
        )
        print(
            "V2 preserved expired PA-5640: "
            f"{clm_8894['v2_tokens']} tokens"
        )

    results_directory = Path(__file__).resolve().parent.parent / "results"
    results_directory.mkdir(exist_ok=True)

    output = {
        "measured_on": datetime.now(timezone(timedelta(hours=8))).date().isoformat(),
        "tokenizer": "o200k_base",
        "serialisation": "repr(result)",
        "fixture_claims": len(claims),
        "current_v2_tools": all_tool_summary,
        "preauthorisation_rewrite": {
            "v1": v1_summary,
            "v2": v2_summary,
            "mean_difference": round(difference, 2),
            "per_case": pa_case_rows,
        },
    }

    output_path = (
        results_directory
        / "d2b_tool_token_measurements.json"
    )

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print(f"Saved measurement results to: {output_path}")


if __name__ == "__main__":
    main()
