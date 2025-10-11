import httpx
import asyncio
import logging
from typing import List, Dict, Optional
import json

logger = logging.getLogger(__name__)


class OllamaClient:
    """Minimal resilient client for local Ollama server.

    - Lazily detects whether the server expects /api/generate or /api/chat
    - Normalizes responses to return the assistant text content string when possible
    """

    def __init__(self, base: str = "http://127.0.0.1:11434"):
        self.base = base.rstrip('/')
        self._client = httpx.AsyncClient(timeout=60.0)
        self._detected: Optional[str] = None
        self._lock = asyncio.Lock()

    async def detect_endpoint(self) -> str:
        """Detect best endpoint: tries /api/generate then /api/chat.
        Returns 'generate' or 'chat' or 'unknown'."""
        async with self._lock:
            if self._detected:
                return self._detected

            # Try /api/generate
            try:
                url = f"{self.base}/api/generate"
                # Force non-streaming to avoid NDJSON for detection probes
                payload = {"model": "llama3.2", "prompt": "ping", "stream": False}
                r = await self._client.post(url, json=payload)
                if r.status_code != 404:
                    logger.info("Detected Ollama endpoint: /api/generate (status %s)", r.status_code)
                    self._detected = 'generate'
                    return self._detected
            except Exception:
                logger.debug("/api/generate probe failed", exc_info=True)

            # Try /api/chat
            try:
                url = f"{self.base}/api/chat"
                payload = {"model": "llama3.2", "messages": [{"role": "user", "content": "ping"}], "stream": False}
                r = await self._client.post(url, json=payload)
                if r.status_code != 404:
                    logger.info("Detected Ollama endpoint: /api/chat (status %s)", r.status_code)
                    self._detected = 'chat'
                    return self._detected
            except Exception:
                logger.debug("/api/chat probe failed", exc_info=True)

            logger.warning("Could not autodetect Ollama endpoint, falling back to 'generate'")
            self._detected = 'generate'
            return self._detected

    async def _extract_text(self, data: Dict) -> Optional[str]:
        """Try common response shapes to extract assistant text."""
        try:
            if not isinstance(data, dict):
                return None
            # Ollama generate/chat common top-level field
            if 'response' in data and isinstance(data['response'], str):
                return data['response']
            if 'message' in data and isinstance(data['message'], dict) and 'content' in data['message']:
                return data['message']['content']
            if 'choices' in data and isinstance(data['choices'], list) and len(data['choices']) > 0:
                first = data['choices'][0]
                # choice.message.content
                if isinstance(first, dict):
                    if 'message' in first and isinstance(first['message'], dict) and 'content' in first['message']:
                        return first['message']['content']
                    if 'text' in first:
                        return first['text']
            # fallback common keys
            if 'result' in data and isinstance(data['result'], dict) and 'content' in data['result']:
                return data['result']['content']
        except Exception:
            logger.debug("Failed to extract assistant text", exc_info=True)
        return None

    async def request(self, model: str = 'llama3.2', messages: Optional[List[Dict]] = None, prompt: Optional[str] = None) -> Optional[str]:
        """Unified request: if messages passed, prefer chat; if prompt passed, prefer generate.
        Autodetects server flavor on first call."""
        kind = await self.detect_endpoint()
        try:
            if kind == 'chat' and messages is not None:
                url = f"{self.base}/api/chat"
                payload = {"model": model, "messages": messages, "stream": False}
                r = await self._client.post(url, json=payload)
                r.raise_for_status()
                data = r.json()
                text = await self._extract_text(data)
                return text if text is not None else json_dumps_short(data)

            # For generate endpoint, convert messages -> prompt if needed
            if kind == 'generate':
                url = f"{self.base}/api/generate"
                if prompt is None and messages is not None:
                    prompt = _messages_to_prompt(messages)
                # Force non-streaming so we get a single JSON document instead of NDJSON stream
                payload = {"model": model, "prompt": prompt, "stream": False}
                r = await self._client.post(url, json=payload)
                r.raise_for_status()
                # Some Ollama versions still respond with NDJSON even when stream=False; handle gracefully
                ctype = r.headers.get('Content-Type', '')
                if 'application/x-ndjson' in ctype or '\n' in (r.text or ''):
                    text = _parse_ndjson_text(r.text)
                    if text:
                        return text
                    # Fallback to best-effort parse of the last JSON object
                    try:
                        lines = [ln for ln in (r.text or '').splitlines() if ln.strip()]
                        if lines:
                            data = json.loads(lines[-1])
                            text = await self._extract_text(data)
                            if text is not None:
                                return text
                    except Exception:
                        logger.debug("Failed to parse NDJSON fallback", exc_info=True)
                # Normal JSON
                data = r.json()
                text = await self._extract_text(data)
                return text if text is not None else json_dumps_short(data)

            # Unknown: try chat first, then generate
            if messages is not None:
                try:
                    url = f"{self.base}/api/chat"
                    r = await self._client.post(url, json={"model": model, "messages": messages, "stream": False})
                    r.raise_for_status()
                    data = r.json()
                    text = await self._extract_text(data)
                    return text if text is not None else json_dumps_short(data)
                except Exception:
                    pass
            if prompt is not None:
                url = f"{self.base}/api/generate"
                r = await self._client.post(url, json={"model": model, "prompt": prompt})
                r.raise_for_status()
                data = r.json()
                text = await self._extract_text(data)
                return text if text is not None else json_dumps_short(data)

        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Ollama request error: {e}")
        except Exception as e:
            logger.error(f"Unexpected Ollama error: {e}", exc_info=True)
        return None


def _messages_to_prompt(messages: List[Dict]) -> str:
    parts = []
    for m in messages:
        role = m.get('role', 'user')
        content = m.get('content', '')
        parts.append(f"[{role}] {content}")
    return "\n".join(parts)


def json_dumps_short(obj) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return str(obj)


# Module-level client instance for easy reuse
ollama_client = OllamaClient()


def _parse_ndjson_text(text: Optional[str]) -> Optional[str]:
    """Parse Ollama NDJSON stream and return concatenated assistant text.
    Handles both generate-style {response: "...", done: bool} and chat-style shapes.
    """
    if not text:
        return None
    parts: List[str] = []
    try:
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            # Generate stream shape
            if isinstance(obj, dict):
                if 'response' in obj and isinstance(obj.get('response'), str):
                    parts.append(obj['response'])
                # Some chat-like streams may include message chunks
                msg = obj.get('message')
                if isinstance(msg, dict) and isinstance(msg.get('content'), str):
                    parts.append(msg['content'])
        combined = ''.join(parts).strip()
        return combined or None
    except Exception:
        logger.debug("Failed to parse NDJSON text", exc_info=True)
        return None
