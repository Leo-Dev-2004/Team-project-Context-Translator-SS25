import time
from filters import COOLDOWN_SECONDS

explained_terms = {}

def is_explained(term):
    """Return True only if term was explained within cooldown window."""
    now = time.time()
    term = term.lower()
    if term in explained_terms:
        last_time = explained_terms[term]
        if now - last_time < COOLDOWN_SECONDS:
            return True
    return False

def mark_as_explained(term):
    """Mark a term as explained with the current timestamp."""
    explained_terms[term.lower()] = time.time()
