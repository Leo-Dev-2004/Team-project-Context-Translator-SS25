/**
 * Test-File für UniversalMessage Parser
 * 
 * Dieses File testet verschiedene Szenarien des UniversalMessage Parsers
 * und zeigt, wie er mit verschiedenen KI-Antwortformaten umgeht.
 */

import { UniversalMessageParser } from './universal-message-parser.js';
import { explanationManager } from './explanation-manager.js';

// Test-Daten: Verschiedene UniversalMessage-Formate
const testMessages = [
    // 1. Vollständige KI-Erklärung mit strukturierten Daten
    {
        id: "msg_12345_abc",
        type: "explanation.response",
        payload: {
            term: "Mikroservice",
            definition: "Ein Mikroservice ist ein kleiner, unabhängiger Service, der Teil einer größeren Anwendung ist.",
            explanation: {
                title: "Was ist ein Mikroservice?",
                content: "**Mikroservices** sind ein Architekturmuster, bei dem eine Anwendung als Suite kleiner Services entwickelt wird, die jeweils in ihrem eigenen Prozess laufen und über gut definierte APIs kommunizieren.\n\n**Vorteile:**\n- Skalierbarkeit\n- Technologie-Diversität\n- Fehlertoleranz\n\n**Nachteile:**\n- Komplexität\n- Netzwerk-Latenz"
            }
        },
        timestamp: 1640995200.0,
        origin: "ai_service",
        destination: "frontend",
        client_id: "client_123"
    },

    // 2. Einfache KI-Antwort mit Markdown
    {
        id: "msg_67890_def",
        type: "ai.explanation",
        payload: {
            content: "# OAuth 2.0\n\nOAuth 2.0 ist ein Autorisierungsprotokoll, das es Anwendungen ermöglicht, begrenzten Zugang zu Benutzerkonten zu erhalten.\n\n## Wie es funktioniert:\n1. **Authorization Request** - Die Anwendung leitet den Benutzer zur Autorisierung weiter\n2. **Authorization Grant** - Der Benutzer autorisiert die Anwendung\n3. **Access Token** - Die Anwendung erhält ein Access Token\n4. **Protected Resource** - Die Anwendung greift auf geschützte Ressourcen zu"
        },
        timestamp: 1640995300.0,
        origin: "ai_service",
        client_id: "client_123"
    },

    // 3. Transkript-Erklärung (von eurem Meeting-System)
    {
        id: "msg_abc123_ghi",
        type: "transcription.explanation",
        payload: {
            term: "Docker Container",
            definition: "Ein Docker Container ist eine leichtgewichtige, eigenständige, ausführbare Paketierung einer Anwendung.",
            context: "Erwähnt in Meeting um 14:23 - 'Wir sollten unsere Anwendung in Docker Containern deployen'",
            explanation: {
                content: "**Docker Container** sind wie virtuelle Maschinen, aber viel effizienter:\n\n- **Isolierung:** Jeder Container läuft isoliert\n- **Portabilität:** Läuft überall gleich\n- **Effizienz:** Teilt sich den OS-Kernel\n\n```bash\n# Beispiel Docker-Befehl\ndocker run -d -p 8080:80 nginx\n```"
            }
        },
        timestamp: 1640995400.0,
        origin: "transcription_service",
        destination: "frontend",
        client_id: "client_123"
    },

    // 4. Minimale KI-Antwort
    {
        id: "msg_minimal_test",
        type: "explanation.generated",
        payload: {
            response: "**API** steht für Application Programming Interface. Es ist eine Schnittstelle, die es verschiedenen Softwareanwendungen ermöglicht, miteinander zu kommunizieren."
        },
        timestamp: 1640995500.0,
        origin: "ai_service"
    },

    // 5. Fehlerhafte/unvollständige Nachricht (sollte fehlschlagen)
    {
        id: "msg_invalid",
        // type fehlt!
        payload: {
            some_data: "test"
        },
        timestamp: 1640995600.0
    },

    // 6. Keine Erklärung (sollte ignoriert werden)
    {
        id: "msg_no_explanation",
        type: "system.status",
        payload: {
            status: "running",
            cpu_usage: 45.2
        },
        timestamp: 1640995700.0,
        origin: "system_monitor"
    }
];

/**
 * Führt alle Tests aus
 */
function runAllTests() {
    console.log('🧪 Starte UniversalMessage Parser Tests...\n');

    // Test 1: Einzelne Messages parsen
    console.log('📝 Test 1: Einzelne Messages parsen');
    testMessages.forEach((message, index) => {
        console.log(`\n--- Test Message ${index + 1} ---`);
        console.log('Input:', JSON.stringify(message, null, 2));

        const result = UniversalMessageParser.parseToExplanationItem(message);

        if (result) {
            console.log('✅ Erfolgreich geparst:');
            console.log('- ID:', result.id);
            console.log('- Title:', result.title);
            console.log('- Content Preview:', result.content.substring(0, 100) + '...');
            console.log('- Timestamp:', new Date(result.timestamp).toLocaleString('de-DE'));
            console.log('- Original Message ID:', result.originalMessageId);
            console.log('- Message Type:', result.messageType);
        } else {
            console.log('❌ Parsing fehlgeschlagen (erwartet bei invaliden Messages)');
        }
    });

    // Test 2: Mehrere Messages gleichzeitig parsen
    console.log('\n\n📝 Test 2: Mehrere Messages gleichzeitig parsen');
    const multipleResults = UniversalMessageParser.parseMultipleToExplanationItems(testMessages);
    console.log(`✅ ${multipleResults.length} von ${testMessages.length} Messages erfolgreich geparst`);

    // Test 3: Integration mit ExplanationManager
    console.log('\n\n📝 Test 3: Integration mit ExplanationManager');

    // Zuerst Manager leeren
    explanationManager.clearAll();

    // Teste parseAndAddToManager
    const validMessages = testMessages.filter(msg =>
        UniversalMessageParser.isExplanationMessage(msg) &&
        UniversalMessageParser.validateUniversalMessage(msg)
    );

    validMessages.forEach((message, index) => {
        const addedItem = UniversalMessageParser.parseAndAddToManager(message, explanationManager);
        if (addedItem) {
            console.log(`✅ Item ${index + 1} erfolgreich zum ExplanationManager hinzugefügt:`, addedItem.title);
        }
    });

    console.log(`\n📊 ExplanationManager enthält jetzt ${explanationManager.getVisibleExplanations().length} Erklärungen`);

    // Test 4: Spezifische Validierungen
    console.log('\n\n📝 Test 4: Spezifische Validierungen');

    // Test isExplanationMessage
    testMessages.forEach((message, index) => {
        const isExplanation = UniversalMessageParser.isExplanationMessage(message);
        console.log(`Message ${index + 1}: ${isExplanation ? '✅' : '❌'} ist Erklärung`);
    });

    // Test 5: Reverse Engineering (ExplanationItem -> UniversalMessage)
    console.log('\n\n📝 Test 5: Reverse Engineering');
    const explanations = explanationManager.getVisibleExplanations();
    if (explanations.length > 0) {
        const firstExplanation = explanations[0];
        const reversedMessage = UniversalMessageParser.createUniversalMessageFromExplanationItem(firstExplanation);
        console.log('✅ ExplanationItem zurück zu UniversalMessage konvertiert:');
        console.log('- Original Title:', firstExplanation.title);
        console.log('- Reversed Message Type:', reversedMessage.type);
        console.log('- Reversed Payload:', JSON.stringify(reversedMessage.payload, null, 2));
    }

    console.log('\n🎉 Alle Tests abgeschlossen!\n');
}

/**
 * Interaktiver Test für Live-Entwicklung
 */
function interactiveTest() {
    console.log('🔄 Interaktiver Test-Modus');
    console.log('Du kannst hier eigene UniversalMessages testen...\n');

    // Beispiel für eigene Test-Message
    const customMessage = {
        id: "custom_test_" + Date.now(),
        type: "explanation.custom",
        payload: {
            term: "Dein Fachbegriff",
            content: "Deine Erklärung hier..."
        },
        timestamp: Date.now() / 1000,
        origin: "test_client"
    };

    console.log('Teste custom message:');
    const result = UniversalMessageParser.parseToExplanationItem(customMessage);
    console.log('Result:', result);
}

/**
 * Performance Test
 */
function performanceTest() {
    console.log('⚡ Performance Test');

    const startTime = performance.now();

    // Parse alle Test-Messages 1000 mal
    for (let i = 0; i < 1000; i++) {
        UniversalMessageParser.parseMultipleToExplanationItems(testMessages);
    }

    const endTime = performance.now();
    console.log(`✅ 1000 Durchläufe in ${(endTime - startTime).toFixed(2)}ms`);
    console.log(`📊 Durchschnittlich ${((endTime - startTime) / 1000).toFixed(2)}ms pro Durchlauf`);
}

// Exportiere Test-Funktionen
export {
    runAllTests,
    interactiveTest,
    performanceTest,
    testMessages
};

// Führe Tests automatisch aus, wenn das Modul direkt geladen wird
if (typeof window !== 'undefined') {
    // Im Browser
    window.addEventListener('load', () => {
        console.log('🚀 UniversalMessage Parser Tests starten...');
        runAllTests();
    });
} else {
    // In Node.js
    runAllTests();
}

// Utility: Erstelle Test-Messages für verschiedene Szenarien
export function createTestMessage(type, payload, options = {}) {
    return {
        id: options.id || `test_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
        type,
        payload,
        timestamp: options.timestamp || Date.now() / 1000,
        origin: options.origin || 'test_client',
        destination: options.destination || 'frontend',
        client_id: options.client_id || 'test_client_123'
    };
}

// Beispiel für die Verwendung in der Console:
/*
// In der Browser-Console:
import { runAllTests, createTestMessage } from './parser-tests.js';

// Alle Tests ausführen
runAllTests();

// Eigene Test-Message erstellen
const myTestMessage = createTestMessage('explanation.test', {
    term: 'Test Begriff',
    content: 'Das ist eine Test-Erklärung'
});

// Parsen
const result = UniversalMessageParser.parseToExplanationItem(myTestMessage);
console.log(result);
*/