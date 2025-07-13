import json
import time
import ollama
import re

def safe_json_extract(content: str) -> list: # die ist dafür da das sicher ein JSON am ende rauskommt (müll entsorger)
    try:
        content = re.sub(r"```(?:json)?", "", content).strip()

        array_match = re.search(r"\[\s*{.*?}\s*.*?\]", content, re.DOTALL)
        if array_match:
            return json.loads(array_match.group(0))

        object_matches = re.findall(r"\{\s*\"term\".*?\}", content, re.DOTALL)
        if object_matches:
            return [json.loads(obj) for obj in object_matches]

        raise ValueError("No valid JSON structure found.")
    except Exception as e:
        print("Failed to extract JSON:", e)
        return []

def detect_terms(sentence: str, user_role: str = None) -> list[dict]:
    context_intro = "Mark the technical terms or words that might not be understood by a general audience in this sentence"
    if user_role:
        context_intro += f", considering the user is a '{user_role}'"
    context_intro += f": \"{sentence}\""

    prompt = f"""
Domain Term Extraction Prompt

{context_intro}

MOST IMPORTANTLY:  
Extract technical or domain specific terms from the following sentence ONLY if it has any, and return ONLY a JSON array.  
Do not return anything else — no markdown, no comments.

---

Goal:  
Extract technical, domain-specific, or uncommon/difficult words or phrases from the sentence (if they exist) — specifically those that might not be immediately understood by a general audience. The focus is on identifying terms that carry specialized meaning in professional, academic, or technical contexts.

What Does “May Not Be Understood by a General Audience” Mean?  
General audience = people without formal education or experience in the topic area (e.g., students, laypeople, non-specialists).  
Include terms if:
- They require background knowledge to understand
- They are acronyms, standards, or jargon
- They are domain-specific verbs, adjectives, protocols, frameworks, or measurements

---

What Counts as a Phrase?  
Extract phrases as a **single `term`** if:
- They represent a unified domain-specific concept
- Their meaning is lost if words are split
- They include numeric or technical suffixes (e.g., “2.0”, “4K”, “802.11ac”)

Extract as:
- "natural language processing"
- "TLS 1.3"
- "public key infrastructure"
- "JSON Web Token"

Do NOT split into:
- "OAuth" and "2.0"
- "neural" and "network"

- If you have already extracted a word, but you see that word in combination with other words, you need to extract it in combination (as a phrase).
Example: if you have already extracted the term "API", but you then see "RESTful API", you MUST extract "RESTful API" as a whole. 
---

Output Format:  
Return a JSON **array of objects**. Each object must have:

- `term` (string): The word or phrase  
- `confidence` (float): Between 0.0 and 0.99 — lower means more confusing to non-experts  
- `context` (string): The full input sentence  
- `timestamp` (int): A Unix timestamp

Important:
- Do **not** return markdown (```json)
- Do **not** include explanations or intro text
- Only return a **raw JSON array**

---

Confidence Scoring Rules:

“confidence” = how likely an average person (non-expert) would ALREADY understand this term without needing explanation.

0.9 = common and familiar  
0.2 = domain specific, obscure, or technical

Do NOT interpret “confidence” as how confident you are that this is a technical term.
Lower confidence = needs explanation.
Higher confidence = simple, familiar, everyday.

Examples of **lower-confidence** technical terms:
- “OAuth 2.0” → 0.25  
- “PostgreSQL” → 0.40  
- “JWT” → 0.30  
- “register allocation” → 0.30

Examples of **high-confidence** terms (don't include unless justified):
- “email”, “file”, “login”, “text” → 0.75 to 0.95

---

Examples:

Input:  
"The compiler uses register allocation to optimize code execution."

Output:  
[
  {{
    "term": "register allocation",
    "confidence": 0.30,
    "context": "The compiler uses register allocation to optimize code execution.",
    "timestamp": 1723848238
  }}
]

Input:  
"Users authenticate via OpenID Connect using ID tokens."

Output:  
[
  {{
    "term": "OpenID Connect",
    "confidence": 0.20,
    "context": "Users authenticate via OpenID Connect using ID tokens.",
    "timestamp": 1723848238
  }},
  {{
    "term": "ID tokens",
    "confidence": 0.40,
    "context": "Users authenticate via OpenID Connect using ID tokens.",
    "timestamp": 1723848238
  }}
]

---

Final Notes:
- Always return a JSON array — no markdown, prose, or explanation.
- If no technical terms are present, return `[]` and nothing else.
Adjust confidence dynamically based on `user_role`:
- If the user is a beginner or student, assume lower prior knowledge.
- If the user is a professor or expert, assume more familiarity.
This should affect both which terms are included and their confidence levels.

---

Examples:

// For a Professor
{{
  "sentence": "The function uses an array to store user data.",
  "user_role": "Professor of Computer Science"
}}
[
// No terms flagged; assumes familiarity
]

// For a School Student
{{
  "sentence": "The function uses an array to store user data.",
  "user_role": "School Student"
}}
[
  {{
    "term": "array",
    "confidence": 0.25,
    "context": "...",
    "timestamp": 1723848238
  }}
]

---

Repeat: the user's role is "{user_role}". Adjust the confidence accordingly:
- If the user is a professor or expert, exclude common terms and raise confidence.
- If the user is a beginner or student, include simpler terms and lower the confidence score.
"""

    response = ollama.chat(
        model="llama3.2",
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.1, "reset": True}
    )

    raw = response['message']['content']
    now = int(time.time())
    raw_terms = safe_json_extract(raw)

    enriched_terms = []
    for term_info in raw_terms:
        enriched_terms.append({
            "term": term_info.get("term", ""),
            "timestamp": term_info.get("timestamp", now),
            "confidence": round(term_info.get("confidence", 0.5), 2),
            "context": term_info.get("context", sentence),
            "status": "pending",
            "explanation": None
        })

    return enriched_terms
