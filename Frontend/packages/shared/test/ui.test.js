import { screen, within } from '@testing-library/dom';
import { describe, it, beforeEach, expect } from 'vitest';
import { UI } from '../src/ui.js';

// Hilfsfunktion zum Einfügen des Elements in das DOM
function renderUI() {
  document.body.innerHTML = '<my-element></my-element>';
  return document.querySelector('my-element');
}

describe('UI Component Tests', () => {
  let element;

  beforeEach(() => {
    element = renderUI();
  });

  it('should add explanation on button click', async () => {
    const button = element.shadowRoot.querySelector('md-filled-button');
    button.click();
    await Promise.resolve();

    const items = element.shadowRoot.querySelectorAll('explanation-item');
    expect(items.length).toBeGreaterThan(0);
  });

  it('should remove explanation when delete clicked', async () => {
    element.explanations = [{ id: '1', title: 'Delete me' }];
    await Promise.resolve();

    const card = element.shadowRoot.querySelector('explanation-item');
    card._handleDelete();
    await Promise.resolve();

    const items = element.shadowRoot.querySelectorAll('explanation-item');
    expect(items.length).toBe(0);
  });

  it('should render explanation cards when explanations are added', async () => {
    const testExplanation = {
      id: '1',
      title: 'Test Term',
      content: 'Test Content',
      timestamp: Date.now()
    };
    element.explanations = [testExplanation];
    await Promise.resolve();

    const card = element.shadowRoot.querySelector('explanation-item');
    expect(card).toBeTruthy();
    expect(card.explanation).toEqual(testExplanation);
  });

  it('should not render duplicate explanations', async () => {
    const duplicateExplanation = {
      id: '1',
      title: 'Duplicate',
      content: 'Content'
    };
    element.explanations = [duplicateExplanation, duplicateExplanation];
    await Promise.resolve();

    const cards = element.shadowRoot.querySelectorAll('explanation-item');
    expect(cards.length).toBe(1);
  });

  it('should handle pin action', async () => {
    const testExplanation = {
      id: '1',
      title: 'Test',
      isPinned: false
    };
    element.explanations = [testExplanation];
    await Promise.resolve();

    const card = element.shadowRoot.querySelector('explanation-item');
    card._handlePin();
    expect(element.explanations[0].isPinned).toBe(true);
  });

  it('should toggle expanded state', async () => {
    element.explanations = [{
      id: '1',
      title: 'Test',
      content: 'Content'
    }];
    await Promise.resolve();

    const card = element.shadowRoot.querySelector('explanation-item');
    expect(card.expanded).toBe(false);

    card._toggleExpanded();
    expect(card.expanded).toBe(true);

    card._toggleExpanded();
    expect(card.expanded).toBe(false);
  });

  it('should clear unpinned explanations but keep pinned ones', async () => {
    element.explanations = [
      { id: '1', title: 'Unpinned', isPinned: false },
      { id: '2', title: 'Pinned', isPinned: true }
    ];
    await Promise.resolve();

    const clearButton = element.shadowRoot.querySelector('md-text-button');
    clearButton.click();
    await Promise.resolve();

    expect(element.explanations.length).toBe(1);
    expect(element.explanations[0].isPinned).toBe(true);
  });
});
