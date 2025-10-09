#!/bin/bash

# Dieses Skript automatisiert die Installation und das Starten des Projekts auf Linux-Systemen.

# --- KONFIGURATION ---
BUILD_TIMEOUT=60    # 1 Minute für 'npm run build'
OLLAMA_TIMEOUT=120  # 2 Minuten für 'ollama run'

echo "--- 1. Projekt-Setup gestartet ---"

# 1. Python Virtual Environment erstellen
echo "1.1 Erstelle Python Virtual Environment (.venv)..."
python3 -m venv .venv
if [ $? -ne 0 ]; then
    echo "Fehler: Konnte venv nicht erstellen. Stellen Sie sicher, dass python3 und python3-venv installiert sind."
    exit 1
fi

# 2. Virtual Environment aktivieren (Linux/macOS)
echo "1.2 Aktiviere Virtual Environment..."
source .venv/bin/activate

# 3. Python-Abhängigkeiten installieren
echo "1.3 Installiere Python-Abhängigkeiten..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Fehler: Konnte Python-Abhängigkeiten nicht installieren."
    deactivate
    exit 1
fi

# 4. Frontend-Setup und Build
echo "--- 2. Frontend-Setup gestartet ---"
cd Frontend
if [ $? -ne 0 ]; then
    echo "Fehler: Konnte nicht in das Verzeichnis 'Frontend' wechseln."
    deactivate
    exit 1
fi

# 4.1 npm-Abhängigkeiten installieren
echo "2.1 Installiere npm-Abhängigkeiten..."
npm install
if [ $? -ne 0 ]; then
    echo "Warnung: npm install ist fehlgeschlagen. Der Build wird möglicherweise fehlschlagen."
fi

# 4.2 npm run build mit Zeitlimit
echo "2.2 Starte 'npm run build' (Timeout: ${BUILD_TIMEOUT}s)..."
# Startet den Build-Prozess im Hintergrund
npm run build > ../frontend_build.log 2>&1 &
BUILD_PID=$!

# Wartet auf das Timeout
sleep $BUILD_TIMEOUT

# Prüfen, ob der Prozess noch läuft und ihn beenden
if kill -0 $BUILD_PID 2>/dev/null; then
    echo "Zeitlimit für 'npm run build' erreicht. Beende den Prozess (PID: $BUILD_PID)."
    kill $BUILD_PID 2>/dev/null
else
    echo "'npm run build' abgeschlossen oder vorzeitig beendet."
fi

# Gehe zurück zum Wurzelverzeichnis
cd ..

# --- 3. Ollama Modell-Vorbereitung ---

# Funktion, um Ollama-Modelle zu ziehen
pull_ollama_model() {
    MODEL_NAME=$1
    echo "3.1 Ziehe Ollama-Modell: $MODEL_NAME..."
    ollama pull "$MODEL_NAME"
    if [ $? -ne 0 ]; then
        echo "Warnung: Konnte Ollama-Modell $MODEL_NAME nicht ziehen. SystemRunner.py wird möglicherweise fehlschlagen."
    fi
}

# Funktion, um Ollama-Modelle kurz auszuführen (mit Timeout)
run_ollama_with_timeout() {
    MODEL_NAME=$1
    
    echo "3.2 Führe Ollama-Modell: $MODEL_NAME kurz aus (Timeout: ${OLLAMA_TIMEOUT}s)..."

    # Führe Befehl im Hintergrund aus und leite die Ausgabe in eine temporäre Datei um
    ollama run "$MODEL_NAME" "brief test query" > "ollama_${MODEL_NAME//:/_}.log" 2>&1 &
    OLLAMA_PID=$!

    # Warte auf das konfigurierte Timeout
    sleep $OLLAMA_TIMEOUT

    # Prüfe, ob der Prozess noch läuft und beende ihn
    if kill -0 $OLLAMA_PID 2>/dev/null; then
        echo "Zeitlimit erreicht. Beende Ollama-Lauf für $MODEL_NAME (PID: $OLLAMA_PID)."
        kill $OLLAMA_PID 2>/dev/null
    else
        echo "Ollama-Lauf für $MODEL_NAME abgeschlossen oder vorzeitig beendet."
    fi
    
    # Ausgabe anzeigen (Piping der Ausgabe, so dass sie sichtbar ist)
    echo "--- Konsolen-Ausgabe von $MODEL_NAME ---"
    cat "ollama_${MODEL_NAME//:/_}.log"
    echo "-----------------------------------"

    # Temporäre Log-Datei aufräumen
    rm -f "ollama_${MODEL_NAME//:/_}.log"
}

# Ollama-Befehle ausführen
pull_ollama_model "llama3.2:3B"
pull_ollama_model "llama3:8B"

run_ollama_with_timeout "llama3.2:3B"
run_ollama_with_timeout "llama3:8B"

# --- 4. SystemRunner starten ---

echo "--- 4. Starte SystemRunner.py (Drücke STRG+C zum Beenden aller Dienste) ---"

# Starte den SystemRunner in der aktiven Virtual Environment
python3 SystemRunner.py

echo "--- Automatisierung beendet ---"
