import asyncio
import json
import logging
import time
import aiofiles
import re
import httpx
from pathlib import Path
from typing import Dict, Any, List, Optional
from uuid import uuid4

from ..models.UniversalMessage import UniversalMessage, ErrorTypes

logger = logging.getLogger(__name__)

class SmallModel:
    """
    Processes transcriptions to detect important terms and writes them to a file-based queue.
    This service is a PRODUCER; it does not interact with MainModel directly.
    """

    def __init__(self):
        self.detections_queue_file = Path("Backend/AI/detections_queue.json")
        self.confidence_threshold = 0.9
        self.cooldown_seconds = 300
        self.known_terms = {
            "a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "do", "for",
            "from", "has", "have", "he", "her", "his", "i", "if", "in", "into", "is", "it",
            "its", "me", "my", "no", "not", "of", "on", "or", "our", "she", "so", "that",
            "the", "their", "them", "then", "there", "these", "they", "this", "to", "too",
            "up", "us", "was", "we", "were", "what", "when", "where", "which", "who",
            "will", "with", "would", "you", "your", "been", "being", "did", "does", "had",
            "having", "how", "than", "those", "also", "just", "such", "yet", "only", "any",
            "each", "few", "most", "other", "some", "because", "while", "about", "before",
            "after", "again", "against", "between", "both", "once", "during", "over",
            "under", "out", "off", "very", "same", "all", "each", "another", "whoever",
            "whichever", "whomever", "whom", "whilst", "perhaps", "random", "randomized",
            "login", "system", "module", "process", "service", "function", "model",
            "input", "output", "data", "rate", "code", "structure", "operation", "performance",
            "memory", "network", "flow", "solution", "platform", "application", "tool",
            "resource", "logic", "signal", "protocol", "instance", "modular", "password",
            "user", "error", "file", "program", "install", "update", "run", "command",
            "website", "page", "link", "browser", "button", "web", "account", "credentials",
            "access", "secure", "permission", "number", "chart", "email"
        }
        self.cooldown_map = {}
        self.detections_queue_file.parent.mkdir(parents=True, exist_ok=True)
        logger.info("SmallModel initialized and ready to produce detections.")

    def safe_json_extract(self, content: str) -> List[Dict]:
        """Safely extract JSON from LLM response."""
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
            logger.error(f"Failed to extract JSON: {e}")
            return []

    def should_pass_filters(self, confidence: float, term: str) -> bool:
        """Apply filtering logic to determine if a term should be processed."""
        now = time.time()
        term_lower = term.lower()

        if confidence >= self.confidence_threshold:
            logger.debug(f"Filtered: '{term}' - confidence too high ({confidence})")
            return False
        if term_lower in self.known_terms:
            logger.debug(f"Filtered: '{term}' - known common term")
            return False
        if term_lower in self.cooldown_map and now - self.cooldown_map[term_lower] < self.cooldown_seconds:
            time_ago = int(now - self.cooldown_map[term_lower])
            logger.debug(f"Filtered: '{term}' - in cooldown ({time_ago}s ago)")
            return False
        return True

    async def _query_ollama_async(self, prompt: str) -> Optional[str]:
        """Asynchronously queries the Ollama server to avoid blocking the event loop."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "http://localhost:11434/api/chat",
                    json={
                        "model": "llama3.2",
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False
                    }
                )
                response.raise_for_status()
                return response.json()['message']['content']
        except httpx.RequestError as e:
            logger.error(f"Ollama query failed (HTTP request error): {e}")
            return None
        except Exception as e:
            logger.error(f"Error during AI detection: {e}", exc_info=True)
            return None

    async def detect_terms_with_ai(self, sentence: str, user_role: Optional[str] = None) -> List[Dict]:
        """Use Ollama/llama3.2 to detect important terms in the given sentence asynchronously."""
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

What Does "May Not Be Understood by a General Audience" Mean?
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
- They include numeric or technical suffixes (e.g., "2.0", "4K", "802.11ac")

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

"confidence" = how likely an average person (non-expert) would ALREADY understand this term without needing explanation.

0.9 = common and familiar
0.2 = domain specific, obscure, or technical

Do NOT interpret "confidence" as how confident you are that this is a technical term.
Lower confidence = needs explanation.
Higher confidence = simple, familiar, everyday.

Examples of **lower-confidence** technical terms:
- "OAuth 2.0" → 0.25
- "PostgreSQL" → 0.40
- "JWT" → 0.30
- "register allocation" → 0.30

Examples of **high-confidence** terms (don't include unless justified):
- "email", "file", "login", "text" → 0.75 to 0.95

---

Final Notes:
- Always return a JSON array — no markdown, prose, or explanation.
- If no technical terms are present, return `[]` and nothing else.
Adjust confidence dynamically based on `user_role`:
- If the user is a beginner or student, assume lower prior knowledge.
- If the user is a professor or expert, assume more familiarity.
This should affect both which terms are included and their confidence levels.

---

Repeat: the user's role is "{user_role}". Adjust the confidence accordingly:
- If the user is a professor or expert, exclude common terms and raise confidence.
- If the user is a beginner or student, include simpler terms and lower the confidence score.
"""

        raw_response = await self._query_ollama_async(prompt)
        if not raw_response:
            return await self.detect_terms_fallback(sentence)

        now = int(time.time())
        raw_terms = self.safe_json_extract(raw_response)
        
        return [
            {
                "term": term_info.get("term", ""),
                "timestamp": term_info.get("timestamp", now),
                "confidence": round(term_info.get("confidence", 0.5), 2),
                "context": term_info.get("context", sentence),
                "status": "pending",
                "explanation": None
            }
            for term_info in raw_terms
        ]

    async def detect_terms_fallback(self, sentence: str) -> List[Dict]:
        """Fallback detection using basic patterns when AI is unavailable."""
        logger.info("Using fallback detection method")
        patterns = {
            'technical_terms': r'\b(?:API|database|server|client|authentication|encryption|algorithm|framework|protocol)\b',
            'business_terms': r'\b(?:revenue|profit|strategy|market|customer|stakeholder|ROI|KPI|budget)\b',
            'academic_terms': r'\b(?:hypothesis|methodology|analysis|research|study|theory|experiment|conclusion)\b',
            'complex_words': r'\b\w{14,}\b'
        }
        detected_terms = set()
        text_lower = sentence.lower()
        for category, pattern in patterns.items():
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                detected_terms.add(match.lower())
        now = int(time.time())
        return [
            {"term": term, "timestamp": now, "confidence": 0.3, "context": sentence, "status": "pending", "explanation": None}
            for term in detected_terms
        ]

    async def write_detection_to_queue(self, message: UniversalMessage, detected_terms: List[Dict]) -> bool:
        """Write detected terms to file-based queue for MainModel processing."""
        try:
            current_queue = []
            if self.detections_queue_file.exists():
                async with aiofiles.open(self.detections_queue_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    if content.strip():
                        current_queue = json.loads(content)
            
            for term_data in detected_terms:
                current_queue.append({
                    "id": str(uuid4()),
                    "term": term_data["term"], "context": term_data["context"], "confidence": term_data["confidence"],
                    "timestamp": term_data["timestamp"], "client_id": message.client_id,
                    "user_session_id": message.payload.get("user_session_id"),
                    "original_message_id": message.id, "status": "pending", "explanation": None
                })

            temp_file = self.detections_queue_file.with_suffix('.tmp')
            async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(current_queue, indent=2, ensure_ascii=False))
            
            import os
            os.replace(str(temp_file), str(self.detections_queue_file))

            logger.info(f"Successfully wrote {len(detected_terms)} detections to queue for client {message.client_id}")
            return True
        except Exception as e:
            logger.error(f"Error writing detections to queue: {e}", exc_info=True)
            return False

    async def process_message(self, message: UniversalMessage):
        """Processes a transcription message, detects terms, and writes them to the detection queue."""
        if message.type != "stt.transcription":
            return # Silently ignore messages it can't handle
        
        try:
            transcribed_text = message.payload.get("text", "")
            user_role = message.payload.get("user_role", None)

            if not transcribed_text:
                logger.warning("Received empty transcription text.")
                return

            detected_terms = await self.detect_terms_with_ai(transcribed_text, user_role)
            if not detected_terms:
                logger.info(f"No terms found in transcription for client {message.client_id}")
                return

            filtered_terms = []
            for term_obj in detected_terms:
                term = term_obj["term"]
                confidence = term_obj["confidence"]
                if self.should_pass_filters(confidence, term):
                    filtered_terms.append(term_obj)
                    self.cooldown_map[term.lower()] = time.time()
                    logger.info(f"Accepted term: '{term}' for client {message.client_id}")

            if filtered_terms:
                await self.write_detection_to_queue(message, filtered_terms)
        
        except Exception as e:
            logger.error(f"SmallModel failed to process message {message.id}: {e}", exc_info=True)