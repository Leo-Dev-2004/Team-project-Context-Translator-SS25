@echo off
setlocal

REM --- KONFIGURATION ---
set "BUILD_TIMEOUT=600"    REM Realistischer Timeout fuer 'npm run build' (Sekunden)
set "OLLAMA_TIMEOUT=60"    REM Timeout fuer kurzes 'ollama run' Warmup (Sekunden)
set "LOG_FILE=frontend_build.log"
REM Speichert den Pfad des aktuellen Skripts, um spaeter zurueckzukehren.
set "SCRIPT_DIR=%~dp0"

REM Ermittele Projekt-Root (eine Ebene ueber dem Skriptverzeichnis) und wechsle dort hin
cd /d "%SCRIPT_DIR%.."
set "ROOT_DIR=%CD%"
set "VENV_DIR=%ROOT_DIR%\.venv"

echo --- 1. Project Setup Started ---

REM 1.1 Python Virtuelle Umgebung im uebergeordneten Ordner erstellen
echo 1.1 Creating Python Virtual Environment (.%\venv)...

REM Finde geeigneten Python Starter (bevorzugt "py -3" auf Windows)
set "PYTHON_CMD="
py -3 -V > nul 2>&1 && set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD (
    python -V > nul 2>&1 && set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
    echo Error: No suitable Python launcher found. Install Python 3.10+ and ensure it is on PATH.
    exit /b 1
)

if exist "%VENV_DIR%\Scripts\activate.bat" (
    echo    -> Virtual environment already exists. Reusing it.
) else (
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        echo Warning: Initial venv creation failed. Retrying after cleanup...
        rmdir /s /q "%VENV_DIR%" > nul 2>&1
        %PYTHON_CMD% -m venv "%VENV_DIR%"
        if %errorlevel% neq 0 (
            echo Error: Failed to create venv. Ensure Python is installed and you have permissions.
            exit /b 1
        )
    )
)

REM 1.2 Virtuelle Umgebung aktivieren
echo 1.2 Activating Virtual Environment...
REM Der Aktivierungspfad nutzt das absolute Verzeichnis.
call "%VENV_DIR%\Scripts\activate.bat"
if %errorlevel% neq 0 (
    echo Error: Failed to activate virtual environment at %VENV_DIR%.
    exit /b 1
)

REM 1.3 Python-Abhaengigkeiten aus dem uebergeordneten Ordner installieren
echo 1.3 Installing Python dependencies from %ROOT_DIR%\requirements.txt...
pip install -r "%ROOT_DIR%\requirements.txt"
if %errorlevel% neq 0 (
    echo Error: Failed to install Python dependencies.
    goto :cleanup
)

echo --- 2. Frontend Setup Started ---

REM Wechsel in das Frontend-Verzeichnis im uebergeordneten Ordner
cd /d "%ROOT_DIR%\Frontend"
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

REM 2.2 Optional: Synchrone Build-Ausfuehrung (Logs werden im Skriptordner gespeichert)
echo 2.2 Running 'npm run build' (this may take a while)...
npm run build > "%SCRIPT_DIR%%LOG_FILE%" 2>&1
if %errorlevel% neq 0 (
    echo FEHLER: 'npm run build' ist fehlgeschlagen. Siehe %SCRIPT_DIR%%LOG_FILE%.
    pause
    goto :cleanup
) else (
    echo Build abgeschlossen. Log: %SCRIPT_DIR%%LOG_FILE%
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
cd /d "%ROOT_DIR%"
python SystemRunner.py


:cleanup
echo --- Automation complete ---
REM Deaktiviert die virtuelle Umgebung, wenn das Skript endet.
if defined VIRTUAL_ENV call deactivate

endlocal
