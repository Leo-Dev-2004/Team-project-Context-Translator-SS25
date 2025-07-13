import json
from fastapi import FastAPI
from pydantic import BaseModel
from detector import detect_terms
from filters import should_pass
from queue_manager import add_to_queue
from explanation_list import is_explained, mark_as_explained

# Um mit curl also mit der API zu testen 2 comamnd prompts öffnen und:
# Im 1. "python -m uvicorn api:app --reload"
# Im 2. "curl -X POST http://127.0.0.1:8000/detect -H "Content-Type: application/json" -d "{\"sentence\": \"The model uses backpropagation and dropout.\", \"domain\": \"Machine Learning\", \"user_role\": \"Beginner\"}""
# Die eingaben in curl sind random beispiele.

app = FastAPI()

class DetectionRequest(BaseModel):
    sentence: str
    user_role: str | None = None

@app.post("/detect")
def detect(request: DetectionRequest):
    results = []
    sentence = request.sentence.strip()

    try:
        terms = detect_terms(sentence, user_role=request.user_role)
    except Exception as e:
        return {"error": str(e)}

    for term_obj in terms:
        term = term_obj["term"]
        confidence = term_obj["confidence"]

        if is_explained(term):
            continue

        if not should_pass(confidence, term):
            continue

        add_to_queue(term_obj)
        mark_as_explained(term)

        results.append({
            "id": len(results) + 1,
            "term": term,
            "context": sentence,
            "status": False
        })

    with open("output_queue.json", "w") as f:
        json.dump(results, f, indent=2)

    return results
