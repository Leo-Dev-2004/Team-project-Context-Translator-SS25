@echo off
setlocal

REM --- KONFIGURATION ---
set "BUILD_TIMEOUT=10"    REM 10 Sekunden fuer 'npm run build'
set "OLLAMA_TIMEOUT=10"  REM 10 Sek fuer 'ollama run'
set "LOG_FILE=frontend_build.log"
REM Speichert den Pfad des aktuellen Skripts, um spaeter zurueckzukehren.
set "SCRIPT_DIR=%~dp0"

echo --- 1. Project Setup Started ---

REM 1.1 Python Virtuelle Umgebung im uebergeordneten Ordner erstellen
echo 1.1 Creating Python Virtual Environment (..\.venv)...
REM Windows verwendet 'python' anstelle von 'python3' und Backslashes '\'.
python -m venv "%~dp0..\.venv"
if %errorlevel% neq 0 (
    echo Error: Failed to create venv. Ensure Python is installed and in your PATH.
    exit /b 1
)

REM 1.2 Virtuelle Umgebung aktivieren
echo 1.2 Activating Virtual Environment...
REM Der Aktivierungspfad ist unter Windows anders. 'call' stellt sicher, dass das Skript hierher zurueckkehrt.
call ..\.venv\Scripts\activate.bat

REM 1.3 Python-Abhaengigkeiten aus dem uebergeordneten Ordner installieren
echo 1.3 Installing Python dependencies from ..\requirements.txt...
pip install -r ..\requirements.txt
if %errorlevel% neq 0 (
    echo Error: Failed to install Python dependencies.
    goto :cleanup
)

echo --- 2. Frontend Setup Started ---

REM Wechsel in das Frontend-Verzeichnis im uebergeordneten Ordner
cd ..\Frontend
if %errorlevel% neq 0 (
    echo Error: Could not switch to the '..\Frontend' directory.
    goto :cleanup
)

REM 2.1 Pruefen, ob die Abhaengigkeiten bereits installiert sind
echo 2.1 Checking for existing npm dependencies (node_modules)...

IF EXIST "node_modules" (
    echo    -> 'node_modules' directory already exists. Skipping 'npm install'.
) ELSE (
    echo    -> 'node_modules' not found. Installing dependencies...
    npm install
    if %errorlevel% neq 0 (
        echo ####################################################################
        echo ##  FEHLER: 'npm install' ist fehlgeschlagen.
        echo ##  Pruefen Sie die Fehlermeldung oben, um die Ursache zu finden.
        echo ##  Moegliche Ursachen: Netzwerkprobleme, Fehler in package.json.
        echo ####################################################################
        pause
        goto :cleanup
)
)

REM 2.2 'npm run build' mit Zeitlimit ausfuehren
echo 2.2 Starting 'npm run build' (Timeout: %BUILD_TIMEOUT%s)...
REM 'start' startet einen Prozess im Hintergrund. Der Titel "NPM_BUILD_PROCESS" hilft, ihn spaeter zu finden.
start "NPM_BUILD_PROCESS" /b npm run build > "%SCRIPT_DIR%%LOG_FILE%" 2>&1

REM Warten bis zum Timeout. 'timeout' ist das Windows-Aequivalent zu 'sleep'.
timeout /t %BUILD_TIMEOUT% /nobreak > nul

REM Pruefen, ob der Prozess noch laeuft, und ihn beenden.
REM tasklist sucht nach dem Prozess ueber den Fenstertitel, den wir mit 'start' vergeben haben.
tasklist /v /fi "WINDOWTITLE eq NPM_BUILD_PROCESS*" | find "node.exe" > nul
if %errorlevel% equ 0 (
    echo Timeout reached for 'npm run build'. Terminating process.
    REM taskkill beendet den Prozess und alle seine untergeordneten Prozesse (/t).
    taskkill /fi "WINDOWTITLE eq NPM_BUILD_PROCESS*" /t /f > nul
) else (
    echo 'npm run build' finished or was terminated early.
)

REM Zurueck zum Verzeichnis des Skripts wechseln
cd /d "%SCRIPT_DIR%"

echo --- 3. Ollama Model Preparation ---

REM Aufruf der "Funktionen" (Batch-Labels)
call :pull_ollama_model "llama3.2:3B"
call :pull_ollama_model "llama3:8B"

call :run_ollama_with_timeout "llama3.2:3B"
call :run_ollama_with_timeout "llama3:8B"

REM Springt zum Start der Hauptanwendung, ueberspringt die Funktionsdefinitionen
goto :start_system_runner

REM --- Funktionsdefinitionen (Batch-Labels) ---

:pull_ollama_model
set "MODEL_NAME=%~1"
echo 3.1 Pulling Ollama model: %MODEL_NAME%...
ollama pull "%MODEL_NAME%"
if %errorlevel% neq 0 (
    echo Warning: Failed to pull Ollama model %MODEL_NAME%. SystemRunner.py might fail.
)
goto :eof


:run_ollama_with_timeout
set "MODEL_NAME=%~1"
REM Erstellt einen sicheren Dateinamen, indem ':' durch '_' ersetzt wird.
set "MODEL_NAME_SAFE=%MODEL_NAME::=_%"
set "MODEL_LOG=ollama_%MODEL_NAME_SAFE%.log"

echo 3.2 Briefly running Ollama model: %MODEL_NAME% (Timeout: %OLLAMA_TIMEOUT%s)...
start "OLLAMA_RUN_%MODEL_NAME_SAFE%" /b ollama run "%MODEL_NAME%" "brief test query" > "%MODEL_LOG%" 2>&1

REM Warten bis zum Timeout
timeout /t %OLLAMA_TIMEOUT% /nobreak > nul

REM Pruefen, ob der Ollama-Prozess noch laeuft, und ihn beenden
tasklist /v /fi "WINDOWTITLE eq OLLAMA_RUN_%MODEL_NAME_SAFE%*" | find "ollama.exe" > nul
if %errorlevel% equ 0 (
    echo Timeout reached. Terminating Ollama run for %MODEL_NAME%.
    taskkill /fi "WINDOWTITLE eq OLLAMA_RUN_%MODEL_NAME_SAFE%*" /t /f > nul
) else (
    echo Ollama run for %MODEL_NAME% finished or was terminated early.
)

REM Anzeigen der erfassten Ausgabe
echo --- Console Output from %MODEL_NAME% ---
REM 'type' ist das Windows-Aequivalent zu 'cat'.
type "%MODEL_LOG%"
echo -----------------------------------

REM Temporaere Log-Datei loeschen
del "%MODEL_LOG%"
goto :eof


:start_system_runner
echo --- 4. Starting SystemRunner.py (Press CTRL+C to stop all services) ---
python ..\SystemRunner.py


:cleanup
echo --- Automation complete ---
REM Deaktiviert die virtuelle Umgebung, wenn das Skript endet.
call deactivate

endlocal
    
