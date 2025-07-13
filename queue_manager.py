import time

shared_queue = []
cooldown_map = {}

def add_to_queue(term_obj):
    shared_queue.append(term_obj)
    cooldown_map[term_obj["term"].lower()] = time.time()

def get_queue():
    return shared_queue
