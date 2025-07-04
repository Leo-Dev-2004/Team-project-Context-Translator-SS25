/**
 * UniversalMessage to ExplanationItem Parser - Optimized Version
 * 
 * Diese Klasse wandelt UniversalMessages von der KI in ExplanationItems um,
 * die dann im Frontend mit ExplanationManager und ExplanationItem-Component angezeigt werden.
 * 
 * Optimiert für:
 * - Verschiedene KI-Antwortformate
 * - Bessere Error-Handling
 * - Integration mit ExplanationManager
 * - Spezifische message types für Erklärungen
 */

/**
 * In WebSocket Handler einfügen:
 * websocket.onmessage = (event) => {
    const universalMessage = JSON.parse(event.data);
    
    // Prüfe, ob es eine Erklärung ist
    if (UniversalMessageParser.isExplanationMessage(universalMessage)) {
        // Parse und füge zur UI hinzu
        UniversalMessageParser.parseAndAddToManager(universalMessage, explanationManager);
    }
};
 */


export class UniversalMessageParser {
    // Bekannte message types für Erklärungen
    static EXPLANATION_TYPES = {
        EXPLANATION_RESPONSE: 'explanation.response',
        EXPLANATION_GENERATED: 'explanation.generated',
        EXPLANATION_TERM: 'explanation.term',
        EXPLANATION_CONCEPT: 'explanation.concept',
        AI_EXPLANATION: 'ai.explanation',
        TRANSCRIPTION_EXPLANATION: 'transcription.explanation'
    };

    /**
     * Parst eine UniversalMessage zu einem ExplanationItem
     * @param {Object} universalMessage - Die UniversalMessage im JSON-Format
     * @returns {Object|null} - Das geparste ExplanationItem oder null bei Fehlern
     */
    static parseToExplanationItem(universalMessage) {
        try {
            // Validierung der UniversalMessage
            if (!this.validateUniversalMessage(universalMessage)) {
                console.error('Invalid UniversalMessage format:', universalMessage);
                return null;
            }

            // Prüfe, ob es sich um eine Erklärung handelt
            if (!this.isExplanationMessage(universalMessage)) {
                console.warn('Message is not an explanation type:', universalMessage.type);
                return null;
            }

            const payload = universalMessage.payload || {};

            // Erstelle ExplanationItem basierend auf der UniversalMessage
            const explanationItem = {
                id: this.generateExplanationId(universalMessage.id),
                title: this.extractTitle(payload, universalMessage.type),
                content: this.extractContent(payload, universalMessage.type),
                timestamp: this.convertTimestamp(universalMessage.timestamp),
                isPinned: false,
                isDeleted: false,
                createdAt: Date.now(),

                // Zusätzliche Metadaten aus der UniversalMessage
                originalMessageId: universalMessage.id,
                origin: universalMessage.origin,
                messageType: universalMessage.type,
                clientId: universalMessage.client_id
            };

            return explanationItem;
        } catch (error) {
            console.error('Error parsing UniversalMessage to ExplanationItem:', error);
            return null;
        }
    }

    /**
     * Prüft, ob eine UniversalMessage eine Erklärung enthält
     * @param {Object} message - Die UniversalMessage
     * @returns {boolean} - True wenn es sich um eine Erklärung handelt
     */
    static isExplanationMessage(message) {
        const type = message.type?.toLowerCase();

        // Prüfe explizite Erklärungstypen
        if (Object.values(this.EXPLANATION_TYPES).includes(message.type)) {
            return true;
        }

        // Prüfe auf explanation-Keywords im type
        if (type?.includes('explanation') || type?.includes('explain')) {
            return true;
        }

        // Prüfe Payload auf Erklärungsinhalte
        const payload = message.payload || {};
        if (payload.explanation || payload.definition || payload.term) {
            return true;
        }

        return false;
    }

    /**
     * Validiert eine UniversalMessage
     * @param {Object} message - Die zu validierende UniversalMessage
     * @returns {boolean} - True wenn gültig, false sonst
     */
    static validateUniversalMessage(message) {
        if (!message || typeof message !== 'object') {
            return false;
        }

        // Überprüfe erforderliche Felder
        const requiredFields = ['id', 'type', 'timestamp'];
        for (const field of requiredFields) {
            if (!message.hasOwnProperty(field)) {
                console.warn(`Missing required field: ${field}`);
                return false;
            }
        }

        // Überprüfe Datentypen
        if (typeof message.id !== 'string' ||
            typeof message.type !== 'string' ||
            typeof message.timestamp !== 'number') {
            return false;
        }

        return true;
    }

    /**
     * Extrahiert den Titel aus dem Payload
     * @param {Object} payload - Das Payload der UniversalMessage
     * @param {string} messageType - Der Type der Message für kontextbasierte Extraktion
     * @returns {string} - Der extrahierte Titel
     */
    static extractTitle(payload, messageType) {
        // 1. Explizite Titel-Felder prüfen
        if (payload.explanation?.title) {
            return payload.explanation.title;
        }

        if (payload.title) {
            return payload.title;
        }

        // 2. Fachbegriff-basierte Titel
        if (payload.term) {
            return payload.term;
        }

        if (payload.concept) {
            return payload.concept;
        }

        if (payload.word) {
            return payload.word;
        }

        // 3. Aus dem Content ableiten
        if (payload.explanation?.content || payload.content) {
            const content = payload.explanation?.content || payload.content;
            return this.extractTitleFromContent(content);
        }

        // 4. Aus Definition ableiten
        if (payload.definition) {
            const firstWords = payload.definition.split(' ').slice(0, 4).join(' ');
            return firstWords.length > 30 ? firstWords.substring(0, 30) + '...' : firstWords;
        }

        // 5. Fallback basierend auf messageType
        const fallbackTitles = {
            'explanation.response': 'KI-Erklärung',
            'explanation.generated': 'Generierte Erklärung',
            'explanation.term': 'Fachbegriff',
            'explanation.concept': 'Konzept',
            'ai.explanation': 'KI-Antwort',
            'transcription.explanation': 'Transkript-Erklärung'
        };

        return fallbackTitles[messageType] || 'Neue Erklärung';
    }

    /**
     * Extrahiert einen Titel aus dem Content
     * @param {string} content - Der Content-Text
     * @returns {string} - Der extrahierte Titel
     */
    static extractTitleFromContent(content) {
        if (!content) return 'Neue Erklärung';

        // Suche nach Markdown-Headings
        const headingMatch = content.match(/^#+ (.+)/m);
        if (headingMatch) {
            return headingMatch[1];
        }

        // Suche nach **Bold** am Anfang
        const boldMatch = content.match(/^\*\*(.+?)\*\*/);
        if (boldMatch) {
            return boldMatch[1];
        }

        // Ersten Satz verwenden
        const firstSentence = content.split(/[.!?]/)[0].trim();
        if (firstSentence.length > 5 && firstSentence.length < 80) {
            return firstSentence;
        }

        // Erste Wörter verwenden
        const firstWords = content.split(' ').slice(0, 5).join(' ');
        return firstWords.length > 50 ? firstWords.substring(0, 50) + '...' : firstWords;
    }

    /**
     * Extrahiert den Inhalt aus dem Payload
     * @param {Object} payload - Das Payload der UniversalMessage
     * @param {string} messageType - Der Type der Message
     * @returns {string} - Der extrahierte Inhalt
     */
    static extractContent(payload, messageType) {
        // 1. Explizite Content-Felder prüfen
        if (payload.explanation?.content) {
            return payload.explanation.content;
        }

        if (payload.content) {
            return payload.content;
        }

        // 2. Description verwenden
        if (payload.description) {
            return payload.description;
        }

        // 3. Definition verwenden
        if (payload.definition) {
            return payload.definition;
        }

        // 4. Text-Feld verwenden
        if (payload.text) {
            return payload.text;
        }

        // 5. Strukturierte Daten kombinieren
        if (payload.term && payload.definition) {
            return `**${payload.term}**\n\n${payload.definition}`;
        }

        if (payload.concept && payload.explanation && payload.explanation.content) {
            return `**${payload.concept}**\n\n${payload.explanation.content}`;
        }

        // 6. KI-Response spezifisch
        if (payload.response) {
            return payload.response;
        }

        if (payload.answer) {
            return payload.answer;
        }

        // 7. Fallback: Strukturierte Darstellung des Payloads
        const importantFields = ['term', 'concept', 'definition', 'explanation', 'response', 'answer'];
        const foundFields = importantFields.filter(field => payload[field]);

        if (foundFields.length > 0) {
            return foundFields.map(field => `**${field}:** ${payload[field]}`).join('\n\n');
        }

        // 8. Letzter Fallback: JSON-Darstellung
        return `Rohdaten:\n\`\`\`json\n${JSON.stringify(payload, null, 2)}\n\`\`\``;
    }

    /**
     * Konvertiert Unix-Timestamp zu JavaScript-Timestamp
     * @param {number} unixTimestamp - Unix-Timestamp in Sekunden
     * @returns {number} - JavaScript-Timestamp in Millisekunden
     */
    static convertTimestamp(unixTimestamp) {
        if (!unixTimestamp) return Date.now();

        // Prüfe, ob es bereits in Millisekunden ist
        if (unixTimestamp > 1000000000000) {
            return unixTimestamp;
        }

        // Konvertiere von Sekunden zu Millisekunden
        return Math.floor(unixTimestamp * 1000);
    }

    /**
     * Generiert eine ExplanationItem-ID basierend auf der UniversalMessage-ID
     * @param {string} originalId - Die Original-ID der UniversalMessage
     * @returns {string} - Die generierte ExplanationItem-ID
     */
    static generateExplanationId(originalId) {
        const cleanId = originalId.replace(/[^a-zA-Z0-9]/g, '').substring(0, 8);
        return `exp_${Date.now()}_${cleanId}`;
    }

    /**
     * Parst mehrere UniversalMessages zu ExplanationItems
     * @param {Array} universalMessages - Array von UniversalMessages
     * @returns {Array} - Array von ExplanationItems
     */
    static parseMultipleToExplanationItems(universalMessages) {
        if (!Array.isArray(universalMessages)) {
            console.error('Expected array of UniversalMessages');
            return [];
        }

        return universalMessages
            .map(message => this.parseToExplanationItem(message))
            .filter(item => item !== null);
    }

    /**
     * Integration mit ExplanationManager
     * Parst eine UniversalMessage und fügt sie direkt dem ExplanationManager hinzu
     * @param {Object} universalMessage - Die UniversalMessage
     * @param {Object} explanationManager - Die ExplanationManager-Instanz
     * @returns {Object|null} - Das erstellte ExplanationItem oder null
     */
    static parseAndAddToManager(universalMessage, explanationManager) {
        const explanationItem = this.parseToExplanationItem(universalMessage);

        if (explanationItem && explanationManager) {
            // Verwende die addExplanation-Methode des Managers
            return explanationManager.addExplanation(
                explanationItem.title,
                explanationItem.content,
                explanationItem.timestamp
            );
        }

        return null;
    }

    /**
     * Erstellt eine UniversalMessage aus einem ExplanationItem (umgekehrte Richtung)
     * @param {Object} explanationItem - Das ExplanationItem
     * @returns {Object} - Die erstellte UniversalMessage
     */
    static createUniversalMessageFromExplanationItem(explanationItem) {
        return {
            id: explanationItem.originalMessageId || `um_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`,
            type: explanationItem.messageType || 'explanation.item',
            payload: {
                explanation: {
                    title: explanationItem.title,
                    content: explanationItem.content
                },
                metadata: {
                    isPinned: explanationItem.isPinned,
                    isDeleted: explanationItem.isDeleted,
                    createdAt: explanationItem.createdAt
                }
            },
            timestamp: explanationItem.timestamp / 1000, // Zurück zu Unix-Timestamp
            origin: explanationItem.origin || 'frontend',
            destination: 'backend',
            client_id: explanationItem.clientId
        };
    }
}

// Beispiel-Verwendung mit verschiedenen KI-Antwortformaten:
/*
// Beispiel 1: KI-Erklärung mit strukturierten Daten
const universalMessage1 = {
    id: "msg_12345_abc",
    type: "explanation.response",
    payload: {
        term: "Mikroservice",
        definition: "Ein Mikroservice ist ein kleiner, unabhängiger Service...",
        explanation: {
            title: "Was ist ein Mikroservice?",
            content: "**Mikroservices** sind ein Architekturmuster..."
        }
    },
    timestamp: 1640995200.0,
    origin: "ai_service",
    destination: "frontend",
    client_id: "client_123"
};

// Beispiel 2: Einfache KI-Antwort
const universalMessage2 = {
    id: "msg_67890_def",
    type: "ai.explanation", 
    payload: {
        content: "# OAuth 2.0\n\nOAuth 2.0 ist ein Autorisierungsprotokoll..."
    },
    timestamp: 1640995300.0,
    origin: "ai_service",
    client_id: "client_123"
};

// Parsing
const explanationItem1 = UniversalMessageParser.parseToExplanationItem(universalMessage1);
const explanationItem2 = UniversalMessageParser.parseToExplanationItem(universalMessage2);

// Direkte Integration mit ExplanationManager
import { explanationManager } from './explanation-manager.js';
const addedItem = UniversalMessageParser.parseAndAddToManager(universalMessage1, explanationManager);
*/