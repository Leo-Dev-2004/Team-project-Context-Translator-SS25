// frontend/src/modules/MessageQueue.js
class MessageQueue {
    constructor(name = "default") {
        this.name = name;
        this.queue = [];
        this.waitingResolvers = []; // Promises waiting for an item
        this._listeners = new Set(); // For UI updates
        console.log(`MessageQueue '${this.name}' initialized.`);
    }

    enqueue(message) {
        if (!message.timestamp) {
            message.timestamp = Date.now(); // Use milliseconds for JS consistency
        }
        this.queue.push(message);
        console.log(`MessageQueue: Enqueued message to '${this.name}'. Current size: ${this.queue.length}`);
        this.notifyListeners(); // Notify all UI listeners about the change

        // If there are consumers waiting, resolve the *oldest* waiting promise
        // with the *newly available* item.
        if (this.waitingResolvers.length > 0) {
            const resolve = this.waitingResolvers.shift(); // Get the oldest resolver
            resolve(this.queue[this.queue.length - 1]); // Resolve with the *newly added* message
                                                         // The dequeue will then shift it.
        }
    }

    // Dequeue a message (asynchronous, blocking/waiting)
    async dequeue() {
        if (this.queue.length > 0) {
            const item = this.queue.shift(); // Truly remove the item
            console.log(`MessageQueue: Dequeued item from '${this.name}'. Current size: ${this.queue.length}`);
            this.notifyListeners(); // Notify listeners after removal
            return item;
        } else {
            // If the queue is empty, return a Promise that will be resolved
            // when a new item is enqueued.
            return new Promise(resolve => {
                this.waitingResolvers.push(resolve);
            });
        }
    }

    size() {
        return this.queue.length;
    }

    // Used for displaying without removing
    // Returns a shallow copy to prevent external modification of the queue
    getCurrentItemsForDisplay() {
        return [...this.queue];
    }

    // Alias for backward compatibility
    peekAll() {
        return this.getCurrentItemsForDisplay();
    }

    // Alias for backward compatibility
    getAll() {
        return this.getCurrentItemsForDisplay();
    }

    // Method to subscribe UI components to queue changes
    subscribe(callback) {
        this._listeners.add(callback);
        // Optionally, immediately notify the new subscriber with the current state
        callback(this.name, this.queue.length, this.getCurrentItemsForDisplay());
    }

    // Method to unsubscribe UI components
    unsubscribe(callback) {
        this._listeners.delete(callback);
    }

    // Internal method to notify all subscribed listeners
    notifyListeners() {
        // Prepare items for display, ensuring they have necessary properties
        const itemsForDisplay = this.queue.map(msg => ({
            id: msg.id,
            type: msg.type,
            // Assuming 'status' could be part of msg.data, default to 'pending'
            status: msg.data && msg.data.status ? msg.data.status : 'pending',
            timestamp: msg.timestamp
        }));
        this._listeners.forEach(callback => callback(this.name, this.queue.length, itemsForDisplay));
    }


    clear() {
        this.queue = [];
        this.waitingResolvers.forEach(resolve => resolve(null)); // Resolve all pending with null/undefined
        this.waitingResolvers = []; // Clear all waiting resolvers
        this.notifyListeners(); // Notify listeners after clearing
        console.log(`Queue '${this.name}' cleared.`);
    }
}

export default MessageQueue;