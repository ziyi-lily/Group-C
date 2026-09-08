from pathlib import Path
from tempfile import TemporaryDirectory
import importlib
import tools


def run_tests():
    importlib.reload(tools)

    claim = tools.get_claim("CLM-8842")
    assert claim["ok"] is True
    assert claim["data"]["claim_total"] == 2480

    policy = tools.lookup_policy("M-2214")
    assert policy["ok"] is True
    assert policy["data"]["policy"]["policy_id"] == "POL-3310"

    hospital = tools.get_hospital_status("H-330")
    assert hospital["ok"] is True
    assert hospital["data"]["hospital_id"] == "H-330"

    preauth = tools.get_preauthorisation(
        "M-2214", "62480", "2026-09-02"
    )
    assert preauth["ok"] is True
    assert preauth["data"]["status"] == "valid"

    coverage = tools.check_coverage(
        "POL-3310",
        "62480",
        "2026-09-02",
        ["itemised_bill", "discharge_summary"],
    )
    assert coverage["ok"] is True
    assert coverage["data"]["requires_preauth"] is True
    assert coverage["data"]["document_present"] is True

    original_path = tools.DECISIONS_PATH

    with TemporaryDirectory() as temporary_directory:
        tools.DECISIONS_PATH = (
            Path(temporary_directory) / "decisions.jsonl"
        )

        try:
            blocked = tools.issue_decision_letter(
                claim_id="CLM-8842",
                decision="approve_in_principle",
                reason="Integration test",
                evidence=["POL-3310", "CLM-8842"],
                operator_confirmed=False,
            )
            assert blocked["ok"] is False
            assert (
                blocked["error"]["code"]
                == "awaiting_operator_confirmation"
            )

            recorded = tools.issue_decision_letter(
                claim_id="CLM-8842",
                decision="approve_in_principle",
                reason="Integration test",
                evidence=["POL-3310", "CLM-8842"],
                operator_confirmed=True,
            )
            assert recorded["ok"] is True

            duplicate = tools.issue_decision_letter(
                claim_id="CLM-8842",
                decision="approve_in_principle",
                reason="Duplicate integration test",
                evidence=["POL-3310", "CLM-8842"],
                operator_confirmed=True,
            )
            assert duplicate["ok"] is False
            assert (
                duplicate["error"]["code"]
                == "decision_already_exists"
            )

        finally:
            tools.DECISIONS_PATH = original_path

    print("PASS: all six tools passed.")
    print("PASS: confirmation gate works.")
    print("PASS: duplicate write protection works.")


if __name__ == "__main__":
    run_tests()
