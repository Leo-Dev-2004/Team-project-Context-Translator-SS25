import json

def check_entry(entry, i):
    required_fields = ["id", "term", "context", "status", "explanation"]

    # Check for missing fields
    for field in required_fields:
        if field not in entry:
            return f"❌ Entry {i}: Missing field '{field}'"

    explanation = str(entry["explanation"]).strip()
    term = str(entry["term"]).strip()

    # Check if explanation is empty
    if not explanation:
        return f"❌ Entry {i}: Explanation is empty"

    # Check status logic
    if not entry["status"]:
        return f"❌ Entry {i}: Status is false but explanation exists"

    # Too short explanations (< 15 characters)
    if len(explanation) < 15:
        return f"❌ Entry {i}: Explanation too short (<15 characters)"

    # Check if explanation is just the term
    if explanation.lower() == term.lower():
        return f"❌ Entry {i}: Explanation is just the term itself"

    return None  # All good

def validate_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Failed to load file: {e}")
        return

    print(f"\n🔍 Validating {path}...")
    failed = False

    for i, entry in enumerate(data, 1):
        error = check_entry(entry, i)
        if error:
            print(error)
            failed = True

    if not failed:
        print("✅ All entries are valid!")
