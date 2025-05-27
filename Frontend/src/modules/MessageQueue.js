// frontend/src/modules/MessageQueue.js
class MessageQueue {
    constructor(name = "default") {
        this.name = name;
        this.queue = [];
        this.waitingResolvers = []; // Renamed from 'pending' for clarity
        this._listeners = new Set();
        console.log(`MessageQueue '${this.name}' initialized.`);
    }

    enqueue(message) {
        if (!message.timestamp) {
            message.timestamp = Date.now() / 1000;
        }
        this.queue.push(message);
        this._listeners.forEach(cb => cb(this.queue));

        // If there are consumers waiting, resolve one immediately with the oldest item
        if (this.waitingResolvers.length > 0 && this.queue.length > 0) {
            const resolve = this.waitingResolvers.shift();
            // We enqueue first, then resolve with the *oldest* item from the queue,
            // effectively allowing the waiting dequeue to take the newly available item.
            // This behavior was somewhat ambiguous in the previous version's enqueue.
            // The dequeue method directly shifts, which is correct.
            // Here, we just need to signal availability to a waiting dequeue.
            // The `dequeue` method itself will shift the item.
            resolve(this.queue[0]); // Indicate availability, dequeue will consume the actual item
        }
    }

    // Dequeue a message (asynchronous, blocking/waiting)
    async dequeue() {
        if (this.queue.length > 0) {
            const item = this.queue.shift(); // Truly remove the item
            console.log(`Dequeued item from '${this.name}':`, item);
            this._listeners.forEach(cb => cb(this.queue)); // Notify listeners
            return item;
        } else {
            return new Promise(resolve => {
                this.waitingResolvers.push(resolve);
            });
        }
    }

    size() {
        return this.queue.length;
    }

    getCurrentItemsForDisplay() { // Used for displaying without removing
        return [...this.queue]; // Return a shallow copy
    }

    // Add peekAll and getAll aliases for backward compatibility if other code uses them
    peekAll() {
        return this.getCurrentItemsForDisplay();
    }

    getAll() {
        return this.getCurrentItemsForDisplay();
    }

    addListener(callback) {
        this._listeners.add(callback);
    }

    removeListener(callback) {
        this._listeners.delete(callback);
    }

    clear() {
        this.queue = [];
        this.waitingResolvers = []; // Also clear waiting resolvers
        this._listeners.forEach(cb => cb(this.queue));
        console.log(`Queue '${this.name}' cleared.`);
    }
}

// Export the class itself as a DEFAULT export, as originally intended in app.js.
// This is critical for `import MessageQueue from './modules/MessageQueue.js';` to work.
export default MessageQueue;