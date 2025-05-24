// MessageQueue.js
class MessageQueue {
    constructor() {
        this.queue = [];
        this.pending = [];
        this._listeners = new Set();
    }

    enqueue(message) {
        if (!message.timestamp) {
            message.timestamp = Date.now() / 1000;
        }
        this.queue.push(message);
        this._listeners.forEach(cb => cb(this.queue));
        while (this.pending.length > 0 && this.queue.length > 0) {
            const resolve = this.pending.shift();
            resolve(this.queue.shift());
        }
    }

    async dequeue() {
        if (this.queue.length > 0) {
            return this.queue.shift();
        }
        return new Promise(resolve => this.pending.push(resolve));
    }

    size() {
        return this.queue.length;
    }

    getAll() {
        return [...this.queue]; // Return a copy of the queue
    }

    addListener(callback) {
        this._listeners.add(callback);
    }

    removeListener(callback) {
        this._listeners.delete(callback);
    }

    clear() {
        this.queue = [];
        this._listeners.forEach(cb => cb(this.queue));
    }
}

// Export the queue instances and the class
export const toBackendQueue = new MessageQueue();
export const fromBackendQueue = new MessageQueue();
export const toFrontendQueue = new MessageQueue();
export const fromFrontendQueue = new MessageQueue();
export { MessageQueue }; // Export the class itself if needed elsewhere
