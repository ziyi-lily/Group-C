"""
PE6201 · A2 — LLM-as-Judge for judgement_queue
Usage: python judge_queue.py
"""
import json
import urllib.request
import urllib.error
from datetime import datetime

# Prompt for API key interactively
INPUT_FILE = input("Enter your input file name: ").strip()
API_KEY = input("Enter your OpenRouter API key: ").strip()
if not API_KEY:
    raise SystemExit("API key cannot be empty. Aborting.")


MODEL = "poolside/laguna-xs-2.1"
BASE_URL = "https://openrouter.ai/api/v1/chat/completions"


def judge_case(case_data):
    prompt = (
        "You are an objective evaluator for a health-insurance claim processing system.\n"
        "For the following case, evaluate each item in 'must_record' based on the 'decision' and 'reason' fields.\n"
        "Return ONLY a raw JSON array of booleans corresponding to each item, in exact order.\n"
        "Do not add markdown, explanations, or extra text.\n\n"
        f"Decision: {case_data['decision']}\n"
        f"Reason: {case_data['reason']}\n"
        f"Must Record: {case_data['must_record']}\n\n"
        "Output format: [true, false, true, ...]"
    )
    
    messages = [{"role": "user", "content": prompt}]
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE_URL, data=data,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            content = result["choices"][0]["message"]["content"].strip()
            # Strip markdown code blocks if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.lower().startswith("json"):
                    content = content[4:]
            return json.loads(content)
    except Exception as e:
        print(f"API/Parse error for {case_data['case_id']}: {e}")
        return None

def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    queue = data.get("judgement_queue", [])
    if not queue:
        print("No judgement_queue found in the file.")
        return

    graded_at = datetime.now().isoformat()
    print(f"Judging {len(queue)} cases with {MODEL}...\n")

    for i, case in enumerate(queue, 1):
        print(f"[{i}/{len(queue)}] Judging {case['case_id']}...")
        verdicts = judge_case(case)
        
        if verdicts is None:
            print(f"Skipped due to API error.\n")
            continue
            
        if len(verdicts) != len(case["must_record"]):
            print(f"Verdicts length mismatch! Expected {len(case['must_record'])}, got {len(verdicts)}.\n")
            continue
            
        case["verdicts"] = verdicts
        case["graded_by"] = f"model: {MODEL}"
        case["graded_on"] = graded_at
        print(f"Done. Verdicts: {verdicts}\n")

    # Save updated results
    with open(INPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"Successfully updated {len(queue)} cases. Output saved to {INPUT_FILE}")

if __name__ == "__main__":
    main()
