import time
from shared_queue import (
    add_entry,
    get_pending_entries,
    update_entry,
    get_entry_history,
    cleanup_queue,
    get_status_summary
)

def test_add_and_get_pending():
    print("Test 1: Add Entry and Get Entry")
    add_entry({
        "term": "STT",
        "confidence": 0.85,
        "context": "Speech to Text"
    })
    add_entry({
        "term": "LLM",
        "confidence": 0.85,
        "context": "Large Language Model"
    })
    pending_entries = get_pending_entries()
    assert len(pending_entries) > 0, "No pending entries"
    print("Pending entries:", pending_entries)

def test_update_entry():
    print("Test 2: Update Entry")
    pending = get_pending_entries()
    if not pending:
        print("No entries to update.")
        return
    entry_id = pending[0]["id"]
    update_entry(entry_id, explanation="A technology that converts spoken language into written text.", status="explained")
    updated = get_entry_history(status_filter=["explained"])
    assert any(e["id"] == entry_id for e in updated), "Entry not updated!"
    print("Updated entry:", updated)

def test_get_entry_history():
    print("Test 3: Get Entry History ")
    history = get_entry_history()
    print("Total entries:", len(history))
    filtered = get_entry_history(status_filter=["explained"], term_filter="STT")
    print("Filtered history:", filtered)

def test_cleanup_queue():
    print("Test 4: Cleanup Queue")
    add_entry({
        "term": "Outdated",
        "confidence": 0.4,
        "context": "Outdated term.",
        "timestamp": time.time() - 10  # make this entry 10s ahead
    })
    before = len(get_entry_history())
    cleanup_queue(limited = 5) # clean up the entry with timestamp before 7s
    after = len(get_entry_history())
    print(f"Entries before cleanup: {before}, after: {after}")


def test_get_status_summary():
    print("Test: Status Summary")
    summary = get_status_summary()
    print("Status counts:", summary)

def run_all_tests():
    test_add_and_get_pending()
    test_update_entry()
    test_get_entry_history()
    test_cleanup_queue()
    test_get_status_summary()

if __name__ == "__main__":
    run_all_tests()
