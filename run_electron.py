# run_electron.py (Finale, vereinfachte Version)

import uvicorn
import logging
import sys
import threading
import subprocess
import time
import requests
import os
import psutil
from pathlib import Path
from queue import Queue

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('system.log', mode='w', encoding='utf-8')
    ]
)
logger = logging.getLogger('SystemRunner')

# Project paths
ROOT_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = ROOT_DIR / "Backend"
FRONTEND_DIR = ROOT_DIR / "Frontend"
STT_SCRIPT_PATH = BACKEND_DIR / "STT" / "transcribe.py"

# --- CONFIGURATION ---
VITE_DEV_COMMAND = ["npm", "run", "dev:renderer"]
ELECTRON_MAIN_COMMAND = ["npm", "run", "dev:main"]
ELECTRON_APP_CWD = FRONTEND_DIR / "packages" / "electron"

class SystemRunner:
    def __init__(self):
        logger.debug("SystemRunner: Initializing class instance.")
        self.backend_port = 8000
        self.processes = []
        self.running = True
        self.electron_test_results = Queue()
        logger.debug("SystemRunner: Initialization complete.")

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

    def run_stt_module(self):
        logger.debug("SystemRunner: Starting STT module process.")
        if not STT_SCRIPT_PATH.exists():
            logger.error(f"SystemRunner: STT script not found: {STT_SCRIPT_PATH}.")
            return
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT_DIR) + os.pathsep + env.get("PYTHONPATH", "")
            stt_process = subprocess.Popen([sys.executable, str(STT_SCRIPT_PATH)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(STT_SCRIPT_PATH.parent), env=env, bufsize=1)
            self.processes.append(stt_process)
            logger.info(f"SystemRunner: STT module process started with PID: {stt_process.pid}")
            self._start_logging(stt_process, "STT_Module")
        except Exception as e:
            logger.critical(f"SystemRunner: Failed to start STT module: {e}", exc_info=True)
            raise

    def run_vite_dev_server(self):
        logger.debug("SystemRunner: Starting Vite dev server process.")
        try:
            use_shell = sys.platform == "win32"
            vite_process = subprocess.Popen(
                VITE_DEV_COMMAND, cwd=str(ELECTRON_APP_CWD), stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, text=True, shell=use_shell, bufsize=1
            )
            self.processes.append(vite_process)
            logger.info(f"SystemRunner: Vite dev server process started with PID: {vite_process.pid}")
            self._start_logging(vite_process, "Vite")
            logger.info("SystemRunner: Vite process launched. Waiting is handled by 'npm run dev:main'.")
        except Exception as e:
            logger.critical(f"SystemRunner: Failed to start Vite server: {e}", exc_info=True)
            raise

    def run_electron_app(self, test_mode=False):
        logger.debug("SystemRunner: Starting Electron app process.")
        try:
            use_shell = sys.platform == "win32"
            electron_process = subprocess.Popen(
                ELECTRON_MAIN_COMMAND, cwd=str(ELECTRON_APP_CWD), stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, text=True, shell=use_shell, bufsize=1
            )
            self.processes.append(electron_process)
            logger.info(f"SystemRunner: Electron app process started with PID: {electron_process.pid}")
    
            if test_mode:
                self._start_test_logging(electron_process)
            else:
                self._start_logging(electron_process, "Electron")
        except Exception as e:
            logger.critical(f"SystemRunner: Failed to start Electron app: {e}", exc_info=True)
            raise

    def _start_logging(self, process, prefix):
        def log_output(pipe, log_func):
            try:
                for line in iter(pipe.readline, ''):
                    log_func(f"[{prefix}]: {line.strip()}")
            except ValueError:
                logger.debug(f"[{prefix}]: Pipe closed.")
            except Exception as e:
                logger.error(f"[{prefix}]: Error reading pipe: {e}", exc_info=True)
        
        threading.Thread(target=log_output, args=(process.stdout, logger.info), daemon=True).start()
        threading.Thread(target=log_output, args=(process.stderr, logger.warning), daemon=True).start()

    def _start_test_logging(self, process):
        # ... Implementierung für Test-Logging, falls benötigt ...
        pass

    def check_backend_ready(self, timeout=60):
        logger.info(f"SystemRunner: Waiting for Backend to be ready at http://127.0.0.1:{self.backend_port}/ (timeout {timeout}s)...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"http://127.0.0.1:{self.backend_port}/", timeout=1)
                if response.status_code == 200:
                    logger.info("SystemRunner: Backend is ready!")
                    return True
            except requests.RequestException:
                pass # Backend is not ready yet
            time.sleep(1)
        logger.critical("SystemRunner: Backend readiness check timed out.")
        return False
    
    def shutdown(self):
        logger.info("SystemRunner: Initiating shutdown for all managed processes...")
        self.running = False
        for p in reversed(self.processes):
            if p.poll() is None:
                try:
                    parent = psutil.Process(p.pid)
                    children = parent.children(recursive=True)
                    logger.info(f"SystemRunner: Terminating process {p.pid} and its {len(children)} children...")
                    for child in children:
                        child.terminate()
                    parent.terminate()
                    gone, still_alive = psutil.wait_procs([parent] + children, timeout=5)
                    for proc in still_alive:
                        logger.warning(f"Process {proc.pid} did not terminate gracefully, killing it.")
                        proc.kill()
                except psutil.NoSuchProcess:
                    logger.warning(f"SystemRunner: Process {p.pid} no longer exists.")
                except Exception as e:
                    logger.error(f"Error during termination of process {p.pid}: {e}", exc_info=True)
        logger.info("SystemRunner: Shutdown complete.")
        sys.exit(0)

def main():
    runner = SystemRunner()
    try:
        runner.run_backend_server()
        if not runner.check_backend_ready():
            raise RuntimeError("Backend failed to start.")

        runner.run_stt_module()
        runner.run_vite_dev_server()
        runner.run_electron_app()
        
        logger.info("All services launched. Press Ctrl+C to stop.")
        while runner.running:
            time.sleep(1)
            for p in runner.processes:
                if p.poll() is not None:
                    raise RuntimeError(f"Process {p.pid} terminated unexpectedly.")

    except (KeyboardInterrupt, RuntimeError) as e:
        if isinstance(e, RuntimeError):
            logger.critical(f"Runtime error: {e}", exc_info=True)
        else:
            logger.info("Ctrl+C detected. Shutting down.")
    finally:
        runner.shutdown()

if __name__ == "__main__":
    main()