import logging
import sys
import threading
import subprocess
import time
import requests
import os
import psutil
import uuid  # uuid for user session IDs
from pathlib import Path
import json

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s', 
                    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler('system.log', mode='w')])
logger = logging.getLogger('SystemRunner')

# Project paths
ROOT_DIR = Path(__file__).parent.resolve()
FRONTEND_DIR = ROOT_DIR / "Frontend"
STT_SCRIPT_PATH = ROOT_DIR / "Backend" / "STT" / "transcribe.py"

# --- CONFIGURATION ---
ELECTRON_DEV_MODE = True  # Set to False to run in production mode
VITE_DEV_COMMAND = ["npm", "run", "dev:renderer"]
ELECTRON_DEV_COMMAND = ["npm", "run", "dev:main"]
ELECTRON_PROD_COMMAND = ["npm", "run", "start"]
ELECTRON_APP_CWD = FRONTEND_DIR

class SystemRunner:
    def __init__(self):
        logger.debug("SystemRunner: Initializing class instance.")
        self.backend_port = 8000
        self.processes = []
        self.running = True

    def run_ollama_serve(self):
        logger.debug("SystemRunner: Starting Ollama serve process.")
        try:
            use_shell = sys.platform == "win32"
            ollama_process = subprocess.Popen(["ollama", "serve"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=use_shell, bufsize=1)
            self.processes.append(ollama_process)
            logger.info(f"SystemRunner: Ollama serve process started with PID: {ollama_process.pid}")
            self._start_logging(ollama_process, "Ollama")
        except Exception as e:
            logger.critical(f"SystemRunner: Failed to start Ollama serve: {e}", exc_info=True)
            raise

    def run_backend_server(self):
        logger.debug("SystemRunner: Starting backend server process.")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT_DIR) + os.pathsep + env.get("PYTHONPATH", "")
        uvicorn_cmd = [sys.executable, "-m", "uvicorn", "Backend.backend:app", "--host", "0.0.0.0", "--port", str(self.backend_port), "--log-level", "info"]
        try:
            backend = subprocess.Popen(uvicorn_cmd, cwd=str(ROOT_DIR), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
            self.processes.append(backend)
            logger.info(f"SystemRunner: Backend process started with PID: {backend.pid}")
            self._start_logging(backend, "Backend")
        except Exception as e:
            logger.critical(f"SystemRunner: Failed to start backend server: {e}", exc_info=True)
            raise

    # Akzeptiert jetzt die user_session_id
    def run_stt_module(self, user_session_id: str):
        logger.debug("SystemRunner: Starting STT module process.")
        if not STT_SCRIPT_PATH.exists():
            logger.error(f"SystemRunner: STT script not found: {STT_SCRIPT_PATH}.")
            return
        
        # Erstellt den Befehl mit dem Kommandozeilen-Argument
        stt_command = [
            sys.executable,
            str(STT_SCRIPT_PATH),
            f"--user-session-id={user_session_id}"
        ]
        
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT_DIR) + os.pathsep + env.get("PYTHONPATH", "")
            stt_process = subprocess.Popen(stt_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(STT_SCRIPT_PATH.parent), env=env, bufsize=1)
            self.processes.append(stt_process)
            logger.info(f"SystemRunner: STT module process started with PID: {stt_process.pid}")
            self._start_logging(stt_process, "STT_Module")
        except Exception as e:
            logger.critical(f"SystemRunner: Failed to start STT module: {e}", exc_info=True)
            raise

    def run_vite_dev_server(self):
        if not ELECTRON_DEV_MODE:
            logger.info("SystemRunner: Skipping Vite dev server (ELECTRON_DEV_MODE=False)")
            return
            
        logger.debug("SystemRunner: Starting Vite dev server process.")
        try:
            use_shell = sys.platform == "win32"
            vite_process = subprocess.Popen(VITE_DEV_COMMAND, cwd=str(ELECTRON_APP_CWD), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=use_shell, bufsize=1)
            self.processes.append(vite_process)
            logger.info(f"SystemRunner: Vite dev server process started with PID: {vite_process.pid}")
            self._start_logging(vite_process, "Vite")
        except Exception as e:
            logger.critical(f"SystemRunner: Failed to start Vite server: {e}", exc_info=True)
            raise

    def _ensure_frontend_built(self):
        """Ensures frontend is built for production mode."""
        dist_dir = FRONTEND_DIR / "dist"
        preload_file = FRONTEND_DIR / "dist-electron" / "preload.js"
        
        if not dist_dir.exists() or not preload_file.exists():
            logger.warning("SystemRunner: Frontend build files not found. Building now...")
            logger.info("SystemRunner: This may take a minute...")
            
            try:
                use_shell = sys.platform == "win32"
                # Build preload
                build_preload = subprocess.run(
                    ["npm", "run", "build:preload"],
                    cwd=str(FRONTEND_DIR),
                    shell=use_shell,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if build_preload.returncode != 0:
                    logger.error(f"SystemRunner: Preload build failed: {build_preload.stderr}")
                    raise RuntimeError("Failed to build preload script")
                
                # Build renderer
                build_renderer = subprocess.run(
                    ["npm", "run", "build:renderer"],
                    cwd=str(FRONTEND_DIR),
                    shell=use_shell,
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                if build_renderer.returncode != 0:
                    logger.error(f"SystemRunner: Renderer build failed: {build_renderer.stderr}")
                    raise RuntimeError("Failed to build renderer")
                
                logger.info("SystemRunner: Frontend build completed successfully")
            except subprocess.TimeoutExpired:
                logger.error("SystemRunner: Frontend build timed out")
                raise RuntimeError("Frontend build timed out")
            except Exception as e:
                logger.error(f"SystemRunner: Failed to build frontend: {e}")
                raise

    # Akzeptiert jetzt die user_session_id
    def run_electron_app(self, user_session_id: str):
        mode_str = "development" if ELECTRON_DEV_MODE else "production"
        logger.debug(f"SystemRunner: Starting Electron app process in {mode_str} mode.")
        
        # In production mode, ensure frontend is built
        if not ELECTRON_DEV_MODE:
            self._ensure_frontend_built()
        
        # Choose command based on dev mode setting
        if ELECTRON_DEV_MODE:
            # Fügt das Kommandozeilen-Argument an den npm-Befehl an
            electron_command = ELECTRON_DEV_COMMAND + [
                "--",
                f"--user-session-id={user_session_id}"
            ]
        else:
            # Production mode - uses built files
            electron_command = ELECTRON_PROD_COMMAND + [
                "--",
                f"--user-session-id={user_session_id}"
            ]
        
        try:
            use_shell = sys.platform == "win32"
            electron_process = subprocess.Popen(electron_command, cwd=str(ELECTRON_APP_CWD), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=use_shell, bufsize=1)
            self.processes.append(electron_process)
            logger.info(f"SystemRunner: Electron app process started with PID: {electron_process.pid} in {mode_str} mode")
            self._start_logging(electron_process, "Electron")
        except Exception as e:
            logger.critical(f"SystemRunner: Failed to start Electron app: {e}", exc_info=True)
            raise

    def _start_logging(self, process, prefix):
        def log_output(pipe, log_func):
            try:
                for line in iter(pipe.readline, ''):
                    log_func(f"[{prefix}]: {line.strip()}")
            except ValueError: pass
        
        def log_stderr(pipe):
            """Log stderr output, filtering out known informational Electron messages."""
            try:
                for line in iter(pipe.readline, ''):
                    stripped = line.strip()
                    
                    # Filter out known informational Electron messages that appear on stderr
                    if prefix == "Electron":
                        # Common Electron informational messages on stderr
                        if any(pattern in stripped for pattern in [
                            "Debugger listening on",
                            "For help, see: https://nodejs.org/en/docs/inspector",
                            "DevTools listening on",
                            "[SECURITY WARNING]",  # Electron security warnings for dev mode
                            "Autofill.setAddresses",
                        ]):
                            # Log as info instead of warning
                            logger.info(f"[{prefix}]: {stripped}")
                            continue
                    
                    # Log as warning for actual stderr messages
                    logger.warning(f"[{prefix}]: {stripped}")
            except ValueError: pass
        
        threading.Thread(target=log_output, args=(process.stdout, logger.info), daemon=True).start()
        threading.Thread(target=log_stderr, args=(process.stderr,), daemon=True).start()

    def check_ollama_ready(self, timeout=30):
        logger.info(f"SystemRunner: Waiting for Ollama to be ready...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"http://127.0.0.1:11434/api/tags", timeout=1)
                if response.status_code == 200:
                    logger.info("SystemRunner: Ollama is ready!")
                    return True
            except requests.RequestException: pass
            time.sleep(0.5)
        return False

    def check_backend_ready(self, timeout=60):
        logger.info(f"SystemRunner: Waiting for Backend to be ready...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"http://127.0.0.1:{self.backend_port}/", timeout=1)
                if response.status_code == 200:
                    logger.info("SystemRunner: Backend is ready!")
                    return True
            except requests.RequestException: pass
            time.sleep(0.5)
        return False
    
    def shutdown(self):
        logger.info("SystemRunner: Initiating shutdown...")
        self.running = False
        for p in reversed(self.processes):
            if p.poll() is None:
                try:
                    parent = psutil.Process(p.pid)
                    for child in parent.children(recursive=True):
                        child.terminate()
                    parent.terminate()
                    psutil.wait_procs([parent] + parent.children(recursive=True), timeout=5)
                except psutil.NoSuchProcess: pass
        logger.info("SystemRunner: Shutdown complete.")
        sys.exit(0)


    
def flush_json_file(file_path):
        """
        Flushes a JSON file of its content by overwriting it with an empty array.
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump([], f)
            print(f"Successfully flushed {file_path}")
        except IOError as e:
            print(f"Error: Could not access file {file_path}. Reason: {e}")


def main():
    runner = SystemRunner()

    script_dir = Path(__file__).parent
    # Leere die JSON-Dateien zu Beginn
    flush_json_file(script_dir / "Backend/AI/detections_queue.json")    
    flush_json_file(script_dir / "Backend/AI/explanations_queue.json") 

    # Generiere die User Session ID hier
    user_session_id = f"user_{uuid.uuid4()}"
    logger.info(f"Generated User Session ID: {user_session_id}")
    
    try:
        runner.run_ollama_serve()
        if not runner.check_ollama_ready():
            raise RuntimeError("Ollama failed to start.")
        
        runner.run_backend_server()
        if not runner.check_backend_ready():
            raise RuntimeError("Backend failed to start.")

        # Übergebe die ID an die Methoden
        runner.run_stt_module(user_session_id=user_session_id)
        runner.run_vite_dev_server()
        runner.run_electron_app(user_session_id=user_session_id)
        
        logger.info("All services launched. Press Ctrl+C to stop.")
        while runner.running:
            time.sleep(1)

    except (KeyboardInterrupt, RuntimeError) as e:
        logger.info(f"Shutting down due to: {type(e).__name__}")
    finally:
        runner.shutdown()

if __name__ == "__main__":
    main()