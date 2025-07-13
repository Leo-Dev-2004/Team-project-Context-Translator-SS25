import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import json
from detector import detect_terms
from filters import should_pass
from queue_manager import add_to_queue
from explanation_list import is_explained, mark_as_explained

# main einfach laufen lassen, die debugs zeigen an was passiert,
# und am ende wenn es durch alle sätze in test_samples durchgelaufen ist, gibts das finale ergebniss.
# Zum testen hier in main auf run drücken (domain und user role weiter unten customizen).
# main und test.py sind unabhängig voneinander.
# main ist besser zum testen da es das finale output gibt, und customization von den sentences, domain und user role erlaubt.
# sentences einfach in test_samples ändern.

def main(user_role=None):
    results = []

    with open("test_samples_andrew2.txt", "r") as f:
        sentences = f.readlines()

    for idx, sentence in enumerate(sentences):
        print(f"🔹 {sentence.strip()}")

        try:
            terms = detect_terms(sentence.strip(), user_role=user_role)
        except Exception as e:
            print(f"Error during detection: {e}")
            continue

        for term_obj in terms:
            term = term_obj["term"]
            confidence = term_obj["confidence"]

            print(f"Detected: {term} (confidence: {confidence})")

            if is_explained(term):
                print(f"Skipped: {term} already explained (within cooldown)")
                continue

            if not should_pass(confidence, term):
                print(f"Skipped: {term} failed filter (confidence too high or known/cooldown)")
                continue

            add_to_queue(term_obj)
            mark_as_explained(term)
            results.append({
                "id": len(results) + 1,
                "term": term,
                "context": sentence.strip(),
                "status": False
            })
            print(f"Queued: {term}")

    return results


if __name__ == "__main__":
    user_role = "Computer Science Student"        # Example: Computer Science Student (oder None)

    output = main(user_role=user_role)

    print("\nFinal Output:")
    print(json.dumps(output, indent=2))

    with open("output_queue.json", "w") as f:
        json.dump(output, f, indent=2)
    print("\nOutput gespeichert in 'output_queue.json'")
