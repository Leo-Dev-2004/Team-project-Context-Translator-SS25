import { MessageQueue } from './frontend.js';

describe('MessageQueue', () => {
  let queue;

  beforeEach(() => {
    queue = new MessageQueue();
  });

  test('enqueue/dequeue', async () => {
    const testMsg = {test: "data"};
    queue.enqueue(testMsg);
    expect(await queue.dequeue()).toEqual(testMsg);
  });

  test('async dequeue', async () => {
    const testMsg = {test: "data"};
    setTimeout(() => queue.enqueue(testMsg), 10);
    expect(await queue.dequeue()).toEqual(testMsg);
  });
});
