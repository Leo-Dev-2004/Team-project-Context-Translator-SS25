#!/bin/bash

# This script automates the installation and launch process for the project on Linux systems.
# It assumes this script is located inside a subdirectory (e.g., 'initial_install') 
# and the main project files are in the parent directory (../).

# --- CONFIGURATION ---
BUILD_TIMEOUT=60    # 1 minute for 'npm run build'
OLLAMA_TIMEOUT=120  # 2 minutes for 'ollama run'
LOG_FILE="frontend_build.log"

echo "--- 1. Project Setup Started ---"

# 1. Create Python Virtual Environment in the parent folder
echo "1.1 Creating Python Virtual Environment (../.venv)..."
python3 -m venv ../.venv
if [ $? -ne 0 ]; then
    echo "Error: Failed to create venv. Ensure python3 and python3-venv are installed."
    exit 1
fi

# 2. Activate Virtual Environment (Linux/macOS)
echo "1.2 Activating Virtual Environment..."
source ../.venv/bin/activate

# 3. Install Python Dependencies from the parent folder
echo "1.3 Installing Python dependencies from ../requirements.txt..."
pip install -r ../requirements.txt
if [ $? -ne 0 ]; then
    echo "Error: Failed to install Python dependencies."
    deactivate
    exit 1
fi

# 4. Frontend Setup and Build
echo "--- 2. Frontend Setup Started ---"

# Change to the Frontend directory in the parent folder
cd ../Frontend
if [ $? -ne 0 ]; then
    echo "Error: Could not switch to the '../Frontend' directory."
    deactivate
    exit 1
fi

# 4.1 Install npm Dependencies
echo "2.1 Installing npm dependencies..."
npm install
if [ $? -ne 0 ]; then
    echo "Warning: npm install failed. The build might fail."
fi

# 4.2 Run 'npm run build' with a time limit
echo "2.2 Starting 'npm run build' (Timeout: ${BUILD_TIMEOUT}s)..."
# Start the build process in the background, logging output to the current script's directory
npm run build > ../initial_install/"$LOG_FILE" 2>&1 &
BUILD_PID=$!

# Wait for the timeout
sleep $BUILD_TIMEOUT

# Check if the process is still running and terminate it
if kill -0 $BUILD_PID 2>/dev/null; then
    echo "Timeout reached for 'npm run build'. Terminating process (PID: $BUILD_PID)."
    kill $BUILD_PID 2>/dev/null
else
    echo "'npm run build' finished or was terminated early."
fi

# Go back to the script's directory (initial_install)
cd - > /dev/null

# --- 3. Ollama Model Preparation ---

# Function to pull Ollama models
pull_ollama_model() {
    MODEL_NAME=$1
    echo "3.1 Pulling Ollama model: $MODEL_NAME..."
    # Note: Ollama output is usually verbose, piping its output to /dev/null
    # unless an error occurs, in which case it prints to stderr.
    ollama pull "$MODEL_NAME"
    if [ $? -ne 0 ]; then
        echo "Warning: Failed to pull Ollama model $MODEL_NAME. SystemRunner.py might fail."
    fi
}

# Function to run Ollama models briefly (with timeout)
run_ollama_with_timeout() {
    MODEL_NAME=$1
    
    echo "3.2 Briefly running Ollama model: $MODEL_NAME (Timeout: ${OLLAMA_TIMEOUT}s)..."
    MODEL_LOG="ollama_${MODEL_NAME//:/_}.log"

    # Execute command in background and redirect output to a temporary file
    ollama run "$MODEL_NAME" "brief test query" > "$MODEL_LOG" 2>&1 &
    OLLAMA_PID=$!

    # Wait for the configured timeout
    sleep $OLLAMA_TIMEOUT

    # Check if the process is still running and terminate it
    if kill -0 $OLLAMA_PID 2>/dev/null; then
        echo "Timeout reached. Terminating Ollama run for $MODEL_NAME (PID: $OLLAMA_PID)."
        kill $OLLAMA_PID 2>/dev/null
    else
        echo "Ollama run for $MODEL_NAME finished or was terminated early."
    fi
    
    # Display the captured output (as requested)
    echo "--- Console Output from $MODEL_NAME ---"
    cat "$MODEL_LOG"
    echo "-----------------------------------"

    # Clean up the temporary log file
    rm -f "$MODEL_LOG"
}

# Execute Ollama commands
pull_ollama_model "llama3.2"

run_ollama_with_timeout "llama3.2"

# --- 4. Start SystemRunner ---

echo "--- 4. Starting SystemRunner.py (Press CTRL+C to stop all services) ---"

# Start the SystemRunner from the parent folder using the active Virtual Environment
python3 ../SystemRunner.py

# Deactivate the Virtual Environment after shutdown
deactivate

echo "--- Automation complete ---"
