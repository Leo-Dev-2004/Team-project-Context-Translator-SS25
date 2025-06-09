// frontend/src/modules/MessageQueue.js
export class MessageQueue {
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
        // FIXED: Now we check if there's a waiting resolver and immediately resolve it
        // with the message that was just enqueued, effectively allowing that dequeue
        // call to proceed. The item will still be dequeued from the front.
        if (this.waitingResolvers.length > 0) {
            const resolve = this.waitingResolvers.shift(); // Get the oldest resolver
            // Resolve the waiting promise without directly passing the item yet.
            // The dequeue method will then properly shift and return the item.
            resolve(); 
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
            // when a new item is enqueued, allowing this dequeue call to retry.
            return new Promise(resolve => {
                this.waitingResolvers.push(resolve);
            })
            // FIXED: Await the resolution of the promise, then recursively call dequeue
            // to ensure we get an actual item from the queue once it's available.
            .then(() => this.dequeue()); 
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
        // FIXED: Reject waiting promises to signal an exceptional clear condition
        this.waitingResolvers.forEach(resolve => {
            // We use setTimeout to ensure the promise is rejected asynchronously,
            // preventing unhandled promise rejections if not caught immediately.
            Promise.resolve().then(() => { // Wrap in Promise.resolve() for async rejection
                // Instead of rejecting, we can simply resolve with null, and rely on the
                // .then(() => this.dequeue()) in dequeue to handle the null.
                // However, a clear should typically interrupt gracefully.
                // For a queue clear, it's often more robust to reject or resolve with a special "cleared" value.
                // Given the dequeue retry logic, resolving with null is a valid approach here.
                resolve(null); // Resolve with null, which will cause dequeue to retry.
            });
        });
        this.waitingResolvers = []; // Clear all waiting resolvers
        this.notifyListeners(); // Notify listeners after clearing
        console.log(`Queue '${this.name}' cleared.`);
    }
}

export default MessageQueue;