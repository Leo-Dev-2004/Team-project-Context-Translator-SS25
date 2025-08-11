# Backend/core/session_manager.py

import logging
import random
import string
from typing import Optional, Dict, Set

logger = logging.getLogger(__name__)

def generate_session_code(length: int = 6) -> str:
    """Generiert einen zufälligen alphanumerischen Code."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

class SessionManager:
    def __init__(self):
        self._active_session: Optional[Dict] = None
        logger.info("SessionManager initialized.")

    def create_session(self, creator_client_id: str) -> Optional[str]:
        """Erstellt eine neue Session, wenn noch keine aktiv ist."""
        if self._active_session:
            logger.warning(f"Client {creator_client_id} tried to create a session, but one is already active.")
            return None # Es läuft bereits eine Session

        code = generate_session_code()
        self._active_session = {
            "code": code,
            "creator": creator_client_id,
            "participants": {creator_client_id} # Ein Set für eindeutige Teilnehmer
        }
        logger.info(f"Session '{code}' created by {creator_client_id}.")
        return code

    def join_session(self, joiner_client_id: str, code: str) -> bool:
        """Fügt einen Client zu einer bestehenden Session hinzu."""
        if not self._active_session or self._active_session["code"] != code:
            logger.warning(f"Client {joiner_client_id} failed to join session with code '{code}'.")
            return False
        
        self._active_session["participants"].add(joiner_client_id)
        logger.info(f"Client {joiner_client_id} successfully joined session '{code}'. Participants: {len(self._active_session['participants'])}")
        return True

    def get_active_session_code(self) -> Optional[str]:
        return self._active_session["code"] if self._active_session else None