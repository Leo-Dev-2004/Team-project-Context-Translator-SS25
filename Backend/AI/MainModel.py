import json
import requests
import os
import time

# === Config ===
INPUT_FILE = "output_queue.json"
OUTPUT_FILE = "output_explanations.json"
CACHE_FILE = "explanation_cache.json"
MODEL = "qwen3" 

# === Helper functions ===

def clean_output(text: str) -> str:
    """Säubert den Rohtext vom LLM."""
    return (
        text.replace("<think>", "")
            .replace("</think>", "")
            .replace("### Response:", "")
            .replace("**Explanation:**", "")
            .strip()
    )

def build_prompt(term: str, context: str) -> list:
    """Erstellt die Anfrage für das LLM."""
    return [
        {
            "role": "system",
            "content": "You are a helpful assistant explaining terms in simple, clear language."
        },
        {
            "role": "user",
            "content": f"""Please directly explain the term "{term}" in the following sentence:
"{context}"

Your answer must be a short, clear definition only. Do not include any reasoning, steps, or thoughts. Just the explanation in 1-2 sentences. /no_think."""
        }
    ]

def query_llm(messages: list, model=MODEL) -> str | None:
    try:
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={"model": model, "messages": messages, "stream": False}
        )
        response.raise_for_status()
        raw_response = response.json()["message"]["content"].strip()
        return clean_output(raw_response)
    except Exception as e:
        print(f"--> Fehler bei der LLM-Anfrage: {e}")
        return None

def update_entry(entry: dict, explanation: str):
    """Aktualisiert einen Eintrag mit der Erklärung und setzt den Status."""
    entry["explanation"] = explanation
    entry["status"] = True

# === Main processing function ===

def process_queue():
    """Liest die Warteschlange, verarbeitet neue Einträge und speichert die Ergebnisse."""
    
    # --- Load processing queue ---
    if not os.path.exists(INPUT_FILE):
        return
        
    try:
        with open(INPUT_FILE, "r", encoding='utf-8') as f:
            detection_queue = json.load(f)
    except json.JSONDecodeError:
        print(f"--> Fehler: '{INPUT_FILE}' ist keine valide JSON-Datei. Überspringe Durchlauf.")
        return

    # --- Load or create cache ---
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding='utf-8') as f:
            explanation_cache = json.load(f)
    else:
        explanation_cache = {}

    something_was_processed = False

    # --- Process each queue entry ---
    for entry in detection_queue:
        # Only process if not ready
        # .get() is more secure if status is missing
        if not entry.get("status", False):
            something_was_processed = True
            term = entry["term"]
            print(f"Verarbeite neuen Begriff: {term}")

            if term in explanation_cache:
                explanation = explanation_cache[term]
                print(f"-> Erklärung aus dem Cache für '{term}' geladen.")
            else:
                print(f"-> Fordere neue Erklärung für '{term}' vom LLM an...")
                messages = build_prompt(term, entry["context"])
                explanation = query_llm(messages)

                if explanation:
                    explanation_cache[term] = explanation
                    print(f"-> Erklärung generiert.")
                    # Save cache immediately to save progress
                    with open(CACHE_FILE, "w", encoding='utf-8') as f:
                        json.dump(explanation_cache, f, indent=2, ensure_ascii=False)
                else:
                    print(f"-> Konnte keine Erklärung für '{term}' erhalten. Überspringe.")
                    continue
            
            update_entry(entry, explanation)

    # --- Save final results list if changes were made ---
    if something_was_processed:
        with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
            json.dump(detection_queue, f, indent=2, ensure_ascii=False)
        print(f"\nFortschritt in '{OUTPUT_FILE}' gespeichert.")
    else:
        print("Keine neuen Aufgaben gefunden.")


# === Infinite loop ===

if __name__ == "__main__":
    print("Starting asynchronous explanation loop...")
    print(f"Surveiling: {INPUT_FILE}")
    
    while True:
        try:
            process_queue()
            # Wait 1 second between checks
            time.sleep(1)
        except KeyboardInterrupt:
            print("\nSkript wird beendet.")
            break
        except Exception as e:
            print(f"Unexpected error happened: {e}")
            print("Waiting for 30s and retrying ...")
            time.sleep(30)