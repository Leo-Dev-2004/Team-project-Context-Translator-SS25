import json
import httpx  # Use httpx for asynchronous HTTP requests
import os
import time
import aiofiles
import asyncio
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from ..models.UniversalMessage import UniversalMessage

# Setup logging
logger = logging.getLogger(__name__)

# === Config ===
# Centralized configuration for clarity and easy modification
OLLAMA_API_URL = "http://localhost:11434/api/chat"
LLAMA_MODEL = "llama3.2"
DETECTIONS_QUEUE_FILE = Path("Backend/AI/detections_queue.json")

class SmallModel:
    """
    Processes transcriptions to detect important terms and writes them to a file-based queue.
    This service is a PRODUCER; it is fully decoupled and does not interact with MainModel directly.
    """

    def __init__(self):
        # Using a single, reusable async HTTP client is more efficient
        self.http_client = httpx.AsyncClient(timeout=60.0)
        
        # A lock is essential to prevent race conditions when writing to the shared queue file
        self.queue_lock = asyncio.Lock()
        self.detections_queue_file = DETECTIONS_QUEUE_FILE

        # Filtering configuration
        self.confidence_threshold = 1  # Terms with confidence >= this are ignored 
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
        """
        Safely and aggressively extracts a JSON array from a raw LLM response.
        """
        try:
            # Find the start and end of the main JSON array
            start_index = content.find('[')
            end_index = content.rfind(']')

            if start_index != -1 and end_index != -1 and end_index > start_index:
                json_str = content[start_index : end_index + 1]
                return json.loads(json_str)
            
            # Fallback for individual objects if no array is found
            object_matches = re.findall(r"\{\s*\"term\".*?\}", content, re.DOTALL)
            if object_matches:
                return [json.loads(obj) for obj in object_matches]

            raise ValueError("No valid JSON array or object structure found in the response.")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to extract JSON. Error: {e}")
            logger.error(f"LLM returned non-JSON response: {content}")
            return []

    def should_pass_filters(self, confidence: float, term: str) -> bool:
        """Apply filtering logic. Note: high confidence terms are filtered OUT."""
        now = time.time()
        term_lower = term.lower()

        # High confidence terms are considered too common/simple to need an explanation
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
            response = await self.http_client.post(
                OLLAMA_API_URL,
                json={
                    "model": LLAMA_MODEL,
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
            logger.error(f"An unexpected error occurred during AI detection: {e}", exc_info=True)
            return None

    async def detect_terms_with_ai(self, sentence: str, user_role: Optional[str] = None) -> List[Dict]:
        """Use Ollama to detect important terms in the given sentence asynchronously."""
        context_intro = f"Mark the technical terms or words that might not be understood by a general audience in this sentence"
        if user_role:
            context_intro += f", considering the user is a '{user_role}'"
        context_intro += f": \"{sentence}\""

        prompt = f"""
Domain Term Extraction Prompt
{context_intro}
MOST IMPORTANTLY:
Extract technical or domain specific terms and return ONLY a valid JSON array of objects.
Do not return anything else — no markdown, no comments, no prose.
---
### EXAMPLE of a PERFECT RESPONSE ###
For an input sentence like "This sentence has no technical terms.", your entire output must be:
[]

For an input sentence like "This has a [TECHNICAL TERM] within it.", your entire output must be:
[
  {{
    "term": "VERY TECHNICAL TERM",
    "confidence": 0.94,
    "context": "This has a [TECHNICAL TERM] within it.",
    "timestamp": 1234567890
  }}
]
########################################
---
Output Format:
Return a JSON **array of objects**. Each object must have these keys:
- "term" (string)
- "confidence" (float): 0.01 (simple/common) to 0.99 (very technical/obscure)
- "context" (string): The full input sentence
- "timestamp" (int): A Unix timestamp
---
Repeat: the user's role is "{user_role}". Adjust the confidence and terms accordingly.
"""
        raw_response = await self._query_ollama_async(prompt)
        if not raw_response:
            return await self.detect_terms_fallback(sentence)

        now = int(time.time())
        raw_terms = self.safe_json_extract(raw_response)
        
        processed_terms = []
        for term_info in raw_terms:
            if isinstance(term_info, dict) and "term" in term_info:
                confidence = term_info.get("confidence")
                processed_terms.append({
                    "term": term_info.get("term", ""),
                    "timestamp": term_info.get("timestamp", now),
                    "confidence": round(confidence if isinstance(confidence, (int, float)) else 0.5, 2),
                    "context": term_info.get("context", sentence),
                })
        return processed_terms

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
        for pattern in patterns.values():
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            detected_terms.update(match.lower() for match in matches)
        
        now = int(time.time())
        return [
            {"term": term, "timestamp": now, "confidence": 0.3, "context": sentence}
            for term in detected_terms
        ]

    async def write_detection_to_queue(self, message: UniversalMessage, detected_terms: List[Dict]) -> bool:
        """Safely write detected terms to the file-based queue."""
        async with self.queue_lock:
            try:
                current_queue = []
                try:
                    async with aiofiles.open(self.detections_queue_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        if content.strip():
                            current_queue = json.loads(content)
                except FileNotFoundError:
                    logger.info("Detections queue file not found, creating a new one.")

                for term_data in detected_terms:
                    queue_entry = {
                        "id": str(uuid4()),
                        "term": term_data["term"],
                        "context": term_data["context"],
                       # "confidence": term_data["confidence"], #  Maybe not relevant
                        "timestamp": term_data["timestamp"],
                        "client_id": message.client_id,
                        "user_session_id": message.payload.get("user_session_id"),
                        "original_message_id": message.id,
                        "status": "pending",
                        "explannation": None
                    }
                        # Include confidence only when provided by producer (e.g., AI detection),
                        # manual requests may omit it deliberately.
                    if "confidence" in term_data and term_data["confidence"] is not None:
                        queue_entry["confidence"] = term_data["confidence"]

                    current_queue.append(queue_entry)

                temp_file = self.detections_queue_file.with_suffix('.tmp')
                async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(current_queue, indent=2, ensure_ascii=False))
                
                await asyncio.to_thread(os.replace, str(temp_file), str(self.detections_queue_file))
                logger.info(f"Successfully wrote {len(detected_terms)} detections to queue.")
                return True
            except Exception as e:
                logger.error(f"Error writing detections to queue: {e}", exc_info=True)
                return False

    async def process_message(self, message: UniversalMessage):
        """Processes a transcription, detects terms, and queues them for the MainModel."""
        if message.type != "stt.transcription":
            return  # Silently ignore messages it can't handle

        try:
            transcribed_text = message.payload.get("text", "")
            if not transcribed_text:
                logger.warning("Received empty transcription text.")
                return

            detected_terms = await self.detect_terms_with_ai(
                transcribed_text,
                message.payload.get("user_role")
            )
            if not detected_terms:
                logger.info(f"No terms found in transcription for client {message.client_id}")
                return

            filtered_terms = []
            for term_obj in detected_terms:
                if self.should_pass_filters(term_obj["confidence"], term_obj["term"]):
                    filtered_terms.append(term_obj)
                    self.cooldown_map[term_obj["term"].lower()] = time.time()
                    logger.info(f"Accepted term: '{term_obj['term']}' for client {message.client_id}")
            
            if filtered_terms:
                await self.write_detection_to_queue(message, filtered_terms)
        
        except Exception as e:
            logger.error(f"SmallModel failed to process message {message.id}: {e}", exc_info=True)