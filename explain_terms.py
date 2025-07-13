import requests

# Dummy queue of terms to explain
detection_queue = [
    {"id": 1, "term": "API", "context": "The API allows systems to communicate.", "status": False},
    {"id": 2, "term": "Machine Learning", "context": "Machine Learning improves predictions over time.", "status": False}
]

# Cache to avoid repeated LLM calls
explanation_cache = {}

# Build a helpful prompt
def build_prompt(term: str, context: str) -> list:
    return [
        {
            "role": "system",
            "content": "You are a helpful assistant explaining terms in simple, clear language."
        },
        {
            "role": "user",
            "content": f"""Explain the term "{term}" as it appears in the following context:
\"{context}\"

Audience: general business user
Length: max 2 sentences
Tone: neutral and clear"""
        }
    ]

# Use the /api/chat endpoint for newer Ollama
def query_llm(messages: list, model="qwen3") -> str | None:
    try:
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False
            }
        )
        response.raise_for_status()
        return response.json()["message"]["content"].strip()
    except Exception as e:
        print(f"Error querying LLM: {e}")
        return None

# Update the entry with the explanation
def update_entry(entry, explanation):
    entry["explanation"] = explanation
    entry["status"] = True

# Main loop
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
            else:
                print(f"Failed to get explanation for: {term}")
                continue

        update_entry(entry, explanation)

# Print results
print("\nFinal Results:")
for entry in detection_queue:
    explanation = entry.get("explanation", "No explanation available")
    print(f"{entry['term']}: {explanation}")

