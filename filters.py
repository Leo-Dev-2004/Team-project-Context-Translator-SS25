import time
from queue_manager import cooldown_map

CONFIDENCE_THRESHOLD = 0.9
known_terms = {
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
    "login","system", "module", "process", "service", "function", "model",
    "input", "output","data", "rate", "code", "structure", "operation", "performance",
    "memory", "network", "flow", "solution", "platform", "application", "tool",
    "resource", "logic", "signal", "protocol", "instance", "modular", "login", "password",
    "user", "input", "output", "error", "code", "file", "program", "install", "update", "model",
    "run", "command", "tool", "website", "page", "link", "browser", "button", "web", "user",
    "account", "credentials", "access", "secure", "permission", "number", "chart", "email"
}
cooldown_set = set()
COOLDOWN_SECONDS = 300

def should_pass(confidence, term):
    now = time.time()
    term = term.lower()

    if confidence >= CONFIDENCE_THRESHOLD:
        return False
    if term in known_terms:
        return False
    if term in cooldown_map and now - cooldown_map[term] < COOLDOWN_SECONDS:
        print(f"Skipped: {term} in cooldown ({int(now - cooldown_map[term])}s ago)")
        return False
    return True
