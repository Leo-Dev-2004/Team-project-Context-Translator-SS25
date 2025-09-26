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

# Performance configuration
AI_TIMEOUT_SECONDS = int(os.getenv("SMALLMODEL_AI_TIMEOUT", "10"))  # Configurable AI timeout
BATCH_DELAY_SECONDS = float(os.getenv("SMALLMODEL_BATCH_DELAY", "0.5"))  # Configurable batch delay

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

        # Import outgoing queue for immediate notifications
        from ..core.Queues import queues
        self.outgoing_queue = queues.outgoing

        # Batching for improved performance
        self.detection_batch = []
        self.batch_timeout = None
        self.batch_delay = BATCH_DELAY_SECONDS  # seconds to collect terms before sending batch

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

    async def send_immediate_detection_notification(self, message: UniversalMessage, detected_terms: List[Dict]):
        """
        Send immediate detection notification to frontend while processing continues in background.
        This provides instant user feedback showing detected terms without waiting for explanations.
        """
        try:
            if not detected_terms:
                return

            # Create immediate notification with detected terms (without explanations)
            detection_notification = UniversalMessage(
                type="detection.immediate",
                payload={
                    "detected_terms": [
                        {
                            "term": term_data["term"],
                            "confidence": term_data.get("confidence", 0.5),
                            "context": term_data["context"],
                            "timestamp": term_data["timestamp"],
                            "status": "detected",  # Status: detected -> processing -> explained
                            "explanation": None  # Will be filled in later
                        }
                        for term_data in detected_terms
                    ],
                    "original_message_id": message.id,
                    "processing_status": "terms_detected"
                },
                client_id=message.client_id,
                origin="SmallModel",
                destination="frontend"
            )

            # Send immediately to frontend via outgoing queue
            await self.outgoing_queue.enqueue(detection_notification)
            
            logger.info(f"Sent immediate detection notification with {len(detected_terms)} terms to client {message.client_id}")
            
        except Exception as e:
            logger.error(f"Error sending immediate detection notification: {e}", exc_info=True)

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

    async def detect_terms_with_ai(self, sentence: str, user_role: Optional[str] = None, domain: Optional[str] = None) -> List[Dict]:
        """Use Ollama to detect important terms in the given sentence asynchronously."""
        # Use configurable timeout for faster fallback
        ai_timeout = AI_TIMEOUT_SECONDS
        
        try:
            # Try AI detection with timeout
            detection_task = asyncio.create_task(self._perform_ai_detection(sentence, user_role, domain))
            ai_result = await asyncio.wait_for(detection_task, timeout=ai_timeout)
            
            if ai_result:
                logger.info(f"AI detection completed for: {sentence[:50]}...")
                return ai_result
                
        except asyncio.TimeoutError:
            logger.warning(f"AI detection timed out after {ai_timeout}s, using fallback detection")
        except Exception as e:
            logger.error(f"AI detection failed: {e}, using fallback detection")
        
        # Use fast fallback detection
        logger.info(f"Using fallback detection for: {sentence[:50]}...")
        return await self.detect_terms_fallback(sentence)
    
    async def _perform_ai_detection(self, sentence: str, user_role: Optional[str] = None, domain: Optional[str] = None) -> List[Dict]:
        """Perform AI-based term detection with the LLM."""
        context_intro = f"Mark the technical terms or words that might not be understood by a general audience in this sentence"
        if user_role:
            context_intro += f", considering the user is a '{user_role}'"
        if domain and domain.strip():
            context_intro += f", in the context of '{domain.strip()}'"
        context_intro += f": \"{sentence}\""

        prompt = f"""
Domain Term Extraction Prompt
{context_intro}
MOST IMPORTANTLY:
Extract technical or domain specific terms and return ONLY a valid JSON array of objects.
Do not return anything else — no markdown, no comments, no prose.
{f"Focus on terms relevant to: {domain.strip()}" if domain and domain.strip() else ""}
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
{f"Domain context: {domain.strip()}. " if domain and domain.strip() else ""}Repeat: the user's role is "{user_role}". Adjust the confidence and terms accordingly.
"""
        raw_response = await self._query_ollama_async(prompt)
        if not raw_response:
            return []

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
        logger.info("Using enhanced fallback detection method")
        
        # Enhanced patterns for better technical term detection
        patterns = {
            'ml_ai_terms': r'\b(?:machine learning|neural network|artificial intelligence|deep learning|algorithm|model|training|dataset|backpropagation|gradient descent|overfitting|underfitting|regression|classification|clustering|reinforcement learning|supervised learning|unsupervised learning)\b',
            'tech_terms': r'\b(?:API|REST|GraphQL|microservices|database|server|client|authentication|encryption|blockchain|cloud computing|docker|kubernetes|DevOps|CI/CD|framework|library|protocol|HTTP|HTTPS|TCP|UDP|JSON|XML|SQL|NoSQL)\b',
            'programming_terms': r'\b(?:function|variable|object|class|method|inheritance|polymorphism|encapsulation|recursion|iteration|debugging|refactoring|version control|git|repository|commit|pull request|merge|branch)\b',
            'business_terms': r'\b(?:revenue|profit|strategy|market research|customer acquisition|stakeholder|ROI|KPI|budget|scalability|monetization|business model|value proposition|market penetration)\b',
            'academic_terms': r'\b(?:hypothesis|methodology|qualitative|quantitative|analysis|research|peer review|literature review|systematic review|meta-analysis|statistical significance|correlation|causation|validity|reliability)\b',
            'complex_words': r'\b\w{12,}\b',  # Words with 12+ characters
            'acronyms': r'\b[A-Z]{2,6}\b'  # 2-6 letter acronyms
        }
        
        detected_terms = set()
        text_lower = sentence.lower()
        
        for category, pattern in patterns.items():
            matches = re.findall(pattern, sentence, re.IGNORECASE)
            for match in matches:
                # Filter out common words and improve confidence based on category
                if match.lower() not in self.known_terms and len(match) > 2:
                    detected_terms.add(match)
        
        now = int(time.time())
        result_terms = []
        
        for term in detected_terms:
            # Assign confidence based on term characteristics
            confidence = 0.4  # default fallback confidence
            term_lower = term.lower()
            
            if any(tech_word in term_lower for tech_word in ['api', 'machine', 'neural', 'algorithm', 'learning']):
                confidence = 0.7  # Higher confidence for obvious technical terms
            elif len(term) > 15:  # Very long words are likely technical
                confidence = 0.6
            elif term.isupper() and len(term) >= 3:  # Acronyms
                confidence = 0.5
                
            result_terms.append({
                "term": term, 
                "timestamp": now, 
                "confidence": confidence, 
                "context": sentence
            })
        
        logger.info(f"Fallback detection found {len(result_terms)} terms")
        return result_terms

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
                        "domain": term_data.get("domain", ""),  # Include domain context
                        "explanation_style": term_data.get("explanation_style", "detailed"),  # Include explanation style
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
            if not transcribed_text or not transcribed_text.strip():
                logger.warning(f"SmallModel: Blocked empty transcription from client {message.client_id}.")
                return

            detected_terms = await self.detect_terms_with_ai(
                transcribed_text,
                message.payload.get("user_role"),
                message.payload.get("domain")  # Pass domain context from transcription message
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
                # IMMEDIATE FEEDBACK: Send detection notification to frontend right away
                await self.send_immediate_detection_notification(message, filtered_terms)
                
                # BACKGROUND PROCESSING: Queue for detailed explanation generation
                await self.write_detection_to_queue(message, filtered_terms)
        
        except Exception as e:
            logger.error(f"SmallModel failed to process message {message.id}: {e}", exc_info=True)