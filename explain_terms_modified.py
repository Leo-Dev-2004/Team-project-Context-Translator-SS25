import json
import requests
import os

# === Config ===
INPUT_FILE = "input_terms.json"
OUTPUT_FILE = "output_explanations.json"
CACHE_FILE = "explanation_cache.json"
MODEL = "qwen3"

# === Load input ===
if not os.path.exists(INPUT_FILE):
    print(f"Input file '{INPUT_FILE}' not found.")
    exit(1)

with open(INPUT_FILE, "r") as f:
    detection_queue = json.load(f)

# === Load or create cache ===
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r") as f:
        explanation_cache = json.load(f)
else:
    explanation_cache = {}

# === Prompt builder ===
def build_prompt(term: str, context: str) -> list:
    return [
        {
            "role": "system",
            "content": "You are a helpful assistant explaining terms in simple, clear language."
        },
        {
            "role": "user",
            "content": f"""Please directly explain the term "{term}" in the following sentence:
\"{context}\"

Your answer must be a short, clear definition only. Do not include any reasoning, steps, or thoughts. Just the explanation in 1-2 sentences. /no_think."""
        }
    ]

# === Ask the local LLM ===
def query_llm(messages: list, model=MODEL) -> str | None:
    try:
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={"model": model, "messages": messages, "stream": False}
        )
        response.raise_for_status()
        return response.json()["message"]["content"].strip()
    except Exception as e:
        print(f"Error querying LLM: {e}")
        return None

# === Save to cache file ===
def save_cache():
    with open(CACHE_FILE, "w") as f:
        json.dump(explanation_cache, f, indent=2)

# === Update a queue entry with the explanation ===
def update_entry(entry, explanation):
    entry["explanation"] = explanation
    entry["status"] = True

# === Process each term ===
for entry in detection_queue:
    if not entry["status"]:
        term = entry["term"]

        if term in explanation_cache:
            explanation = explanation_cache[term]
            print(f"Using cached explanation for: {term}")
        else:
            messages = build_prompt(term, entry["context"])
            explanation = query_llm(messages)

            if explanation:
                explanation_cache[term] = explanation
                print(f"Generated explanation for: {term}")
                save_cache()
            else:
                print(f"Failed to get explanation for: {term}")
                continue

        update_entry(entry, explanation)

# === Save final results ===
with open(OUTPUT_FILE, "w") as f:
    json.dump(detection_queue, f, indent=2)

print(f"\n✅ Explanations written to '{OUTPUT_FILE}'")
print(f"🧠 Cache saved to '{CACHE_FILE}'")
