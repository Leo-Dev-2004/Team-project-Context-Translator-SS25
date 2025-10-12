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
from ..dependencies import get_settings_manager_instance

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
        self.confidence_threshold = 0.6  # Terms with confidence < this are ignored 
        self.cooldown_seconds = 300
        self.known_terms = {
            # Basic articles, pronouns, prepositions, conjunctions
            "a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "do", "for",
            "from", "has", "have", "he", "her", "his", "i", "if", "in", "into", "is", "it",
            "its", "me", "my", "no", "not", "of", "on", "or", "our", "she", "so", "that",
            "the", "their", "them", "then", "there", "these", "they", "this", "to", "too",
            "up", "us", "was", "we", "were", "what", "when", "where", "which", "who",
            "will", "with", "would", "you", "your", "been", "being", "did", "does", "had",
            "having", "how", "than", "those", "also", "just", "such", "yet", "only", "any",
            "each", "few", "most", "other", "some", "because", "while", "about", "before",
            "after", "again", "against", "between", "both", "once", "during", "over",
            "under", "out", "off", "very", "same", "all", "another", "whoever",
            "whichever", "whomever", "whom", "whilst", "perhaps", "random", "randomized",
            
            # Common technical terms that shouldn't be explained
            "login", "system", "module", "process", "service", "function", "model",
            "input", "output", "data", "rate", "code", "structure", "operation", "performance",
            "memory", "network", "flow", "solution", "platform", "application", "tool",
            "resource", "logic", "signal", "protocol", "instance", "modular", "password",
            "user", "error", "file", "program", "install", "update", "run", "command",
            "website", "page", "link", "browser", "button", "web", "account", "credentials",
            "access", "secure", "permission", "number", "chart", "email", 
            
            # Common verbs that were incorrectly detected
            "need", "uses", "shows", "implementing", "increase", "optimize", "better",
            "make", "get", "set", "put", "take", "give", "find", "work", "create",
            "build", "develop", "test", "check", "use", "run", "start", "stop",
            
            # Common nouns that aren't technical
            "time", "way", "day", "year", "work", "life", "part", "place", "case",
            "point", "government", "company", "group", "problem", "fact", "hand",
            "right", "thing", "world", "information", "office", "home", "money",
            "business", "service", "health", "community", "name", "team", "area"
            "access", "secure", "permission", "number", "chart", "email",
            
            # Small talk and conversational fillers
            "hello", "hi", "hey", "goodbye", "bye", "thanks", "thank", "please", "sorry",
            "excuse", "pardon", "well", "ok", "okay", "right", "sure", "yes", "yeah", "yep",
            "no", "nah", "nope", "maybe", "perhaps", "actually", "really", "quite", "pretty",
            "kind", "sort", "like", "you know", "i mean", "basically", "essentially",
            "obviously", "clearly", "definitely", "probably", "certainly", "absolutely",
            "exactly", "totally", "completely", "perfectly", "generally", "usually",
            "typically", "normally", "commonly", "frequently", "often", "sometimes",
            "occasionally", "rarely", "seldom", "never", "always", "forever",
            
            # Time and sequence words
            "now", "today", "yesterday", "tomorrow", "soon", "later", "earlier", "first",
            "second", "third", "last", "final", "next", "previous", "current", "recent",
            "past", "future", "present", "since", "until", "before", "after", "during",
            
            # Quantifiers and modifiers
            "much", "many", "more", "most", "less", "least", "enough", "too", "quite",
            "rather", "fairly", "somewhat", "slightly", "extremely", "incredibly",
            "amazingly", "surprisingly", "unfortunately", "fortunately", "hopefully",
            
            # Common verbs that rarely need explanation
            "go", "get", "make", "take", "come", "see", "look", "know", "think", "feel",
            "want", "need", "try", "use", "work", "play", "help", "ask", "tell", "say",
            "speak", "talk", "listen", "hear", "read", "write", "learn", "teach", "show",
            "find", "give", "bring", "put", "keep", "leave", "start", "stop", "continue",
            "finish", "complete", "begin", "end", "open", "close", "turn", "move", "stay",
            
            # Common adjectives
            "good", "bad", "big", "small", "new", "old", "long", "short", "high", "low",
            "fast", "slow", "hot", "cold", "warm", "cool", "easy", "hard", "simple",
            "difficult", "important", "interesting", "boring", "fun", "nice", "great",
            "wonderful", "terrible", "awful", "amazing", "incredible", "beautiful", "ugly",
            
            # Prompt contamination words (commonly appear during silence)
            "domain", "extract", "technical", "terms", "sentence", "confidence", "json",
            "array", "objects", "context", "timestamp", "response", "example", "perfect",
            "format", "keys", "string", "float", "int", "output", "prompt", "user", "role"
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

    def _get_domain_examples(self, domain: Optional[str]) -> str:
        """Generate domain-specific examples to help the AI understand what terms to extract."""
        if not domain or not domain.strip():
            return """
- Technology: API, database, machine learning, cybersecurity, blockchain
- Business: revenue stream, stakeholder, ROI, market segmentation, supply chain
- Science: hypothesis, methodology, peer review, statistical significance, genome
- Medicine: diagnosis, treatment, pathology, pharmaceutical, clinical trial
- Finance: portfolio, derivative, liquidity, hedge fund, cryptocurrency
- Engineering: algorithm, optimization, architecture, infrastructure, scalability"""
        
        domain_lower = domain.strip().lower()
        
        # Domain-specific example mappings
        domain_examples = {
            "technology": "API, database, machine learning, cybersecurity, blockchain, microservices, DevOps, containerization, REST, GraphQL",
            "software": "algorithm, debugging, refactoring, deployment, version control, continuous integration, unit testing, design patterns",
            "business": "revenue stream, stakeholder, ROI, market segmentation, supply chain, business intelligence, KPI, value proposition",
            "finance": "portfolio, derivative, liquidity, hedge fund, cryptocurrency, asset allocation, risk management, compound interest",
            "medicine": "diagnosis, treatment, pathology, pharmaceutical, clinical trial, symptoms, prognosis, immunotherapy, radiology",
            "science": "hypothesis, methodology, peer review, statistical significance, genome, experiment, research, analysis, variable",
            "engineering": "optimization, architecture, infrastructure, scalability, load balancing, fault tolerance, system design",
            "education": "curriculum, pedagogy, assessment, learning objectives, differentiated instruction, scaffolding, rubric",
            "marketing": "brand awareness, conversion rate, customer acquisition, segmentation, attribution, funnel, retention",
            "healthcare": "patient care, medical records, treatment plan, healthcare provider, insurance, telemedicine, preventive care",
            "legal": "jurisdiction, litigation, contract law, compliance, intellectual property, due diligence, statute of limitations"
        }
        
        # Find matching domain examples
        for key, examples in domain_examples.items():
            if key in domain_lower or domain_lower in key:
                return f"- {domain.title()}: {examples}"
        
        # Default fallback with general examples
        return f"""
- Technology: API, database, machine learning, cybersecurity, blockchain
- Business: revenue stream, stakeholder, ROI, market segmentation, supply chain  
- Science: hypothesis, methodology, peer review, statistical significance, genome
- {domain.title()}: [domain-specific technical terms that would need explanation]"""

    def should_pass_filters(self, confidence: float, term: str, context_sentence: str = "") -> bool:
        """Apply filtering logic with adaptive thresholds based on conversation type."""
        now = time.time()
        term_lower = term.lower()

        # Check if term is in known terms blacklist
        if term_lower in self.known_terms:
            logger.debug(f"Filtered: '{term}' - known common term")
            return False
            
        # Check cooldown
        if term_lower in self.cooldown_map and now - self.cooldown_map[term_lower] < self.cooldown_seconds:
            time_ago = int(now - self.cooldown_map[term_lower])
            logger.debug(f"Filtered: '{term}' - in cooldown ({time_ago}s ago)")
            return False

        # Adaptive confidence threshold based on conversation type
        adaptive_threshold = self._get_adaptive_threshold(context_sentence)
        
        if confidence < adaptive_threshold:
            logger.debug(f"Filtered: '{term}' - confidence too low ({confidence} < {adaptive_threshold}) for context type")
            return False
            
        return True

    def _get_adaptive_threshold(self, sentence: str) -> float:
        """Calculate adaptive confidence threshold based on conversation content."""
        if not sentence:
            return self.confidence_threshold
            
        sentence_lower = sentence.lower()
        
        # Check for high technical content indicators (advanced/complex terms)
        advanced_technical_indicators = [
            "implement", "algorithm", "neural network", "machine learning", "artificial intelligence", 
            "blockchain", "cryptocurrency", "data science", "optimization", "methodology", "hypothesis"
        ]
        
        # Check for moderate technical content indicators
        moderate_technical_indicators = [
            "database", "server", "api", "protocol", "framework", "authentication", 
            "encryption", "deployment", "architecture", "analytics"
        ]
        
        # Check for casual conversation indicators  
        casual_indicators = [
            "enjoyed", "interesting", "workshop", "class", "meeting", "presentation",
            "project", "team", "colleague", "experience", "learned", "discussed",
            "planning", "thinking", "considering", "wondering", "recently", "yesterday"
        ]
        
        # Count indicators
        advanced_count = sum(1 for indicator in advanced_technical_indicators if indicator in sentence_lower)
        moderate_count = sum(1 for indicator in moderate_technical_indicators if indicator in sentence_lower)
        casual_count = sum(1 for indicator in casual_indicators if indicator in sentence_lower)
        
        # Adaptive threshold logic
        if advanced_count >= 1:
            # High technical content - use stricter threshold
            return self.confidence_threshold + 0.1  # 0.7
        elif moderate_count >= 1 and casual_count == 0:
            # Pure technical content - use normal threshold
            return self.confidence_threshold  # 0.6
        elif casual_count >= 1:
            # Casual conversation - use more permissive threshold
            return max(0.5, self.confidence_threshold - 0.1)  # 0.5
        else:
            # Unknown content type - use normal threshold
            return self.confidence_threshold  # 0.6

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
        """Perform AI-based term detection with the LLM. Uses global settings for domain if not provided."""
        # Get domain from SettingsManager if not provided
        if not domain:
            settings_manager = get_settings_manager_instance()
            if settings_manager:
                domain = settings_manager.get_setting("domain", "")
                
        context_intro = f"Mark the technical terms or words that might not be understood by a general audience in this sentence"
        if user_role:
            context_intro += f", considering the user is a '{user_role}'"
        if domain and domain.strip():
            context_intro += f", in the context of '{domain.strip()}'"
        context_intro += f": \"{sentence}\""

        prompt = f"""
Domain Term Extraction Prompt
{context_intro}

CRITICAL FILTERING RULES:
1. IGNORE small talk, greetings, fillers (hello, hi, okay, well, you know, etc.)
2. IGNORE basic common words (the, and, but, very, really, etc.)  
3. IGNORE prompt-related words (extract, technical, terms, confidence, json, etc.)
4. IGNORE generic tech words without domain specificity (system, data, process, etc.)
5. PRIORITIZE genuinely technical, domain-specific, or specialized terms
6. If the input seems to be silence, empty, or contains prompt fragments, return []

ADAPTIVE EXTRACTION STRATEGY:
- If sentence contains clear technical/domain terms: Extract ONLY high-confidence technical terms
- If sentence is mostly casual/small talk: Extract 1-2 moderately interesting words to maintain user engagement
- NEVER extract pure greetings or fillers, but consider contextually relevant words

DOMAIN-SPECIFIC EXAMPLES:
{self._get_domain_examples(domain)}

CONFIDENCE SCORING (0.01-0.99):
- 0.90-0.99: Highly technical/specialized terms needing explanation (neural network, backpropagation, cryptocurrency)
- 0.70-0.89: Moderately technical terms (algorithm, database, authentication)
- 0.50-0.69: Somewhat technical but commonly known (website, email, password)
- 0.01-0.49: Common/basic terms (should rarely be extracted unless in casual conversation)

Extract technical or domain specific terms and return ONLY a valid JSON array of objects.
Do not return anything else — no markdown, no comments, no prose.
{f"Focus on terms relevant to: {domain.strip()}" if domain and domain.strip() else ""}
---
### EXAMPLE RESPONSES ###

Technical conversation example:
Input: "We implemented a neural network using backpropagation."
Output:
[
  {{
    "term": "neural network",
    "confidence": 0.92,
    "context": "We implemented a neural network using backpropagation.",
    "timestamp": 1234567890
  }},
  {{
    "term": "backpropagation", 
    "confidence": 0.89,
    "context": "We implemented a neural network using backpropagation.",
    "timestamp": 1234567890
  }}
]

Casual conversation with some interesting terms:
Input: "I really enjoyed that photography workshop last weekend."
Output:
[
  {{
    "term": "photography workshop",
    "confidence": 0.65,
    "context": "I really enjoyed that photography workshop last weekend.",
    "timestamp": 1234567890
  }}
]

Pure small talk example:
Input: "Hi there, how are you doing today?"
Output: []

Silence/contamination example:
Input: "extract technical terms"
Output: []
########################################
---
Output Format:
Return a JSON **array of objects**. Each object must have these keys:
- "term" (string): The technical term
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
        
        # Enhanced patterns for better technical term detection - more specific patterns
        patterns = {
            'ml_ai_terms': r'\b(?:machine learning|neural network|artificial intelligence|deep learning|algorithm|backpropagation|gradient descent|overfitting|underfitting|regression|classification|clustering|reinforcement learning|supervised learning|unsupervised learning|convolutional|transformer|lstm|rnn|cnn)\b',
            'tech_terms': r'\b(?:API|REST|GraphQL|microservices|database|server|authentication|encryption|blockchain|cloud computing|docker|kubernetes|DevOps|CI/CD|framework|library|HTTP|HTTPS|TCP|UDP|JSON|XML|SQL|NoSQL|webhook|endpoint)\b',
            'programming_terms': r'\b(?:inheritance|polymorphism|encapsulation|recursion|debugging|refactoring|version control|repository|commit|pull request|merge|branch|async|await|callback|middleware|dependency injection)\b',
            'business_terms': r'\b(?:ROI|KPI|scalability|monetization|business model|value proposition|market penetration|customer acquisition|stakeholder)\b',
            'academic_terms': r'\b(?:hypothesis|methodology|qualitative|quantitative|peer review|literature review|systematic review|meta-analysis|statistical significance|correlation|causation|validity|reliability)\b',
            'specific_acronyms': r'\b(?:API|SQL|JSON|XML|HTTP|HTTPS|REST|TCP|UDP|CPU|GPU|RAM|SSD|HDD|URL|URI|CSS|HTML|JS|AWS|GCP|AI|ML|DL|NLP|CNN|RNN|LSTM|GRU|SVM|KNN|PCA|SVD|BERT|GPT|RPA|ETL|CRUD|ACID|BASE|SOLID|DRY|KISS|YAGNI)\b',
            'technical_compounds': r'\b(?:end.?point|data.?set|work.?flow|frame.?work|time.?stamp|name.?space|class.?name|file.?name|user.?name|pass.?word|data.?base|web.?site|soft.?ware|hard.?ware|middle.?ware|firm.?ware|open.?source|source.?code)\b'

        }
        
        detected_terms = set()
        
        for category, pattern in patterns.items():
            matches = re.findall(pattern, sentence, re.IGNORECASE)
            for match in matches:
                # More strict filtering - only add terms that are not common words
                term_clean = match.lower().strip()
                if (term_clean not in self.known_terms and 
                    len(term_clean) > 2 and 
                    not term_clean.isdigit() and
                    term_clean not in ['the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'way', 'who', 'boy', 'did', 'its', 'let', 'put', 'say', 'she', 'too', 'use']):
                    detected_terms.add(match)
        
        # Filter out any terms that are in our known_terms blacklist
        filtered_terms = {term for term in detected_terms if term not in self.known_terms}
        
        now = int(time.time())
        result_terms = []
        
        for term in detected_terms:
            # Assign confidence based on term characteristics - be more conservative
            confidence = 0.3  # Start lower, let the filtering decide
            term_lower = term.lower()
            
            if any(tech_word in term_lower for tech_word in ['api', 'machine learning', 'neural', 'algorithm', 'backpropagation', 'gradient descent']):
                confidence = 0.8  # Higher confidence for specific technical terms
            elif any(tech_word in term_lower for tech_word in ['database', 'server', 'framework', 'authentication', 'encryption']):
                confidence = 0.7  # Medium-high for common tech terms
            elif term.isupper() and len(term) >= 3 and term in ['API', 'SQL', 'JSON', 'XML', 'HTTP', 'HTTPS', 'REST']:
                confidence = 0.9  # Very high for well-known tech acronyms
            elif len(term) > 15:  # Very long words are likely technical
                confidence = 0.6
            elif term.isupper() and len(term) >= 3:  # Other acronyms
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
            
            # Additional filtering for silence contamination and low-quality transcriptions
            text_lower = transcribed_text.lower().strip()
            
            # Skip very short transcriptions that are likely noise
            if len(text_lower.split()) < 2:
                logger.debug(f"SmallModel: Skipped short transcription: '{transcribed_text}'")
                return
                
            # Check for prompt contamination patterns
            prompt_indicators = [
                "extract technical terms", "domain term extraction", "confidence float",
                "json array", "timestamp int", "output format", "perfect response"
            ]
            if any(indicator in text_lower for indicator in prompt_indicators):
                logger.debug(f"SmallModel: Detected prompt contamination, skipping: '{transcribed_text}'")
                return
            
            # Check for repetitive patterns that suggest transcription errors during silence
            words = text_lower.split()
            if len(set(words)) == 1 and len(words) > 3:  # Same word repeated
                logger.debug(f"SmallModel: Detected repetitive pattern, likely silence error: '{transcribed_text}'")
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
                if self.should_pass_filters(term_obj["confidence"], term_obj["term"], transcribed_text):
                    filtered_terms.append(term_obj)
                    self.cooldown_map[term_obj["term"].lower()] = time.time()
                    logger.info(f"Accepted term: '{term_obj['term']}' (confidence: {term_obj['confidence']}) for client {message.client_id}")
            
            if filtered_terms:
                # IMMEDIATE FEEDBACK: Send detection notification to frontend right away
                await self.send_immediate_detection_notification(message, filtered_terms)
                
                # BACKGROUND PROCESSING: Queue for detailed explanation generation
                await self.write_detection_to_queue(message, filtered_terms)
        
        except Exception as e:
            logger.error(f"SmallModel failed to process message {message.id}: {e}", exc_info=True)