import json
import requests
import os
import time
import aiofiles
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from ..models.UniversalMessage import UniversalMessage, ErrorTypes

# === Config ===
INPUT_FILE = "Backend/AI/detections_queue.json"
OUTPUT_FILE = "Backend/AI/explanations_queue.json"
CACHE_FILE = "Backend/AI/explanation_cache.json"
MODEL = "llama3.2"
COOLDOWN_SECONDS = 300

# Setup logging
logger = logging.getLogger(__name__)

class MainModel:
    """
    AI-powered explanation model using qwen3 that reads detected terms from file queue,
    generates explanations, and writes them back to explanation queue for client delivery.
    """

    def __init__(self):
        self.detections_queue_file = Path(INPUT_FILE)
        self.explanations_queue_file = Path(OUTPUT_FILE)
        self.cache_file = Path(CACHE_FILE)

        # Explanation cooldown tracking (from explanation_list.py.txt)
        self.explained_terms = {}

        # Ensure queue directories exist
        self.detections_queue_file.parent.mkdir(parents=True, exist_ok=True)
        self.explanations_queue_file.parent.mkdir(parents=True, exist_ok=True)

        logger.info("MainModel initialized with qwen3 explanation generation and file queue integration.")

    def clean_output(self, text: str) -> str:
        """Clean raw text from LLM responses."""
        return (
            text.replace("<think>", "")
                .replace("</think>", "")
                .replace("### Response:", "")
                .replace("**Explanation:**", "")
                .strip()
        )

    def is_explained(self, term: str) -> bool:
        """Return True only if term was explained within cooldown window."""
        now = time.time()
        term = term.lower()
        if term in self.explained_terms:
            last_time = self.explained_terms[term]
            if now - last_time < COOLDOWN_SECONDS:
                return True
        return False

    def mark_as_explained(self, term: str):
        """Mark a term as explained with the current timestamp."""
        self.explained_terms[term.lower()] = time.time()

    def build_prompt(self, term: str, context: str, user_role: Optional[str] = None) -> List[Dict]:
        """Build the prompt for LLM explanation generation."""
        role_context = ""
        if user_role:
            role_context = f" The user is a '{user_role}', so adjust your explanation accordingly."

        return [
            {
                "role": "system",
                "content": f"You are a helpful assistant explaining technical terms in simple, clear language.{role_context}"
            },
            {
                "role": "user",
                "content": f"""Please directly explain the term "{term}" as used in this context:
"{context}"

Provide a clear, concise explanation in 1-2 sentences. Focus on what the term means and why it's important. Do not include reasoning or thought processes."""
            }
        ]

    async def query_llm(self, messages: List[Dict], model: str = MODEL) -> Optional[str]:
        """Query the LLM for term explanations."""
        try:
            response = requests.post(
                "http://localhost:11434/api/chat",
                json={"model": model, "messages": messages, "stream": False},
                timeout=60  # Increase timeout for qwen3 (can be slow)
            )
            response.raise_for_status()
            raw_response = response.json()["message"]["content"].strip()
            return self.clean_output(raw_response)
        except Exception as e:
            logger.error(f"Error querying LLM: {e}")
            return None

    async def load_cache(self) -> Dict[str, str]:
        """Load explanation cache from file."""
        if self.cache_file.exists():
            try:
                async with aiofiles.open(self.cache_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    if content.strip():
                        return json.loads(content)
            except Exception as e:
                logger.error(f"Error loading cache: {e}")
        return {}

    async def save_cache(self, cache: Dict[str, str]):
        """Save explanation cache to file atomically."""
        try:
            temp_file = self.cache_file.with_suffix('.tmp')
            async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(cache, indent=2, ensure_ascii=False))

            # Atomic move
            import os
            os.replace(str(temp_file), str(self.cache_file))
        except Exception as e:
            logger.error(f"Error saving cache: {e}")

    async def write_explanation_to_queue(self, explanation_entry: Dict) -> bool:
        """Write explanation to output queue for client delivery."""
        try:
            # Read current explanations queue
            current_queue = []
            if self.explanations_queue_file.exists():
                async with aiofiles.open(self.explanations_queue_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    if content.strip():
                        current_queue = json.loads(content)

            # Add new explanation
            current_queue.append(explanation_entry)

            # Write back to file atomically
            temp_file = self.explanations_queue_file.with_suffix('.tmp')
            async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(current_queue, indent=2, ensure_ascii=False))

            # Atomic move
            import os
            os.replace(str(temp_file), str(self.explanations_queue_file))

            logger.info(f"Successfully wrote explanation to queue for client {explanation_entry.get('client_id')}")
            return True

        except Exception as e:
            logger.error(f"Error writing explanation to queue: {e}", exc_info=True)
            return False

    async def process_detections_queue(self):
        """Process detected terms from SmallModel and generate explanations."""
        try:
            # Load detections queue
            if not self.detections_queue_file.exists():
                return

            async with aiofiles.open(self.detections_queue_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                if not content.strip():
                    return

            detection_queue = json.loads(content)
            if not detection_queue:
                return

            # Load cache
            explanation_cache = await self.load_cache()

            processed_entries = []
            something_was_processed = False

            # Process each detection
            for entry in detection_queue:
                if entry.get("status", "") != "pending":
                    continue

                term = entry["term"]
                context = entry["context"]
                client_id = entry.get("client_id")
                user_session_id = entry.get("user_session_id")

                logger.info(f"Processing term: '{term}' for client {client_id}")

                # Check explanation cooldown
                if self.is_explained(term):
                    logger.debug(f"Term '{term}' recently explained, skipping")
                    continue

                explanation = None

                # Check cache first
                if term in explanation_cache:
                    explanation = explanation_cache[term]
                    logger.info(f"Loaded explanation for '{term}' from cache")
                else:
                    # Generate new explanation
                    logger.info(f"Generating new explanation for '{term}'")
                    user_role = entry.get("user_role")
                    messages = self.build_prompt(term, context, user_role)
                    explanation = await self.query_llm(messages)

                    if explanation:
                        explanation_cache[term] = explanation
                        await self.save_cache(explanation_cache)
                        logger.info(f"Generated and cached explanation for '{term}'")
                    else:
                        logger.warning(f"Failed to generate explanation for '{term}'")
                        continue

                if explanation:
                    # Create explanation entry for output queue
                    explanation_entry = {
                        "id": str(uuid4()),
                        "term": term,
                        "explanation": explanation,
                        "context": context,
                        "timestamp": int(time.time()),
                        "client_id": client_id,
                        "user_session_id": user_session_id,
                        "original_detection_id": entry.get("id"),
                        "status": "ready_for_delivery",
                        "confidence": entry.get("confidence", 0.5)  # Default confidence if not provided
                    }

                    # Write to explanations queue
                    success = await self.write_explanation_to_queue(explanation_entry)
                    if success:
                        # Mark as explained and processed
                        self.mark_as_explained(term)
                        entry["status"] = "processed"
                        entry["explanation"] = explanation
                        processed_entries.append(entry)
                        something_was_processed = True

                        logger.info(f"Successfully processed term '{term}' for client {client_id}")

            # Update detections queue to mark processed items
            if something_was_processed:
                # Write updated detections queue back
                temp_file = self.detections_queue_file.with_suffix('.tmp')
                async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(detection_queue, indent=2, ensure_ascii=False))

                import os
                os.replace(str(temp_file), str(self.detections_queue_file))
                logger.info(f"Updated detections queue with {len(processed_entries)} processed entries")

        except Exception as e:
            logger.error(f"Error processing detections queue: {e}", exc_info=True)


    async def run_continuous_processing(self):
        """Run continuous processing loop for detected terms."""
        logger.info("Starting MainModel continuous processing...")
        logger.info(f"Monitoring: {self.detections_queue_file}")

        while True:
            try:
                await self.process_detections_queue()
                # Wait 2 seconds between checks
                await asyncio.sleep(2)
            except KeyboardInterrupt:
                logger.info("MainModel processing stopped by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error in MainModel: {e}", exc_info=True)
                logger.info("Waiting 30s before retry...")
                await asyncio.sleep(30)


if __name__ == "__main__":
    import logging

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    main_model = MainModel()

    try:
        asyncio.run(main_model.run_continuous_processing())
    except KeyboardInterrupt:
        logger.info("MainModel shutdown complete")