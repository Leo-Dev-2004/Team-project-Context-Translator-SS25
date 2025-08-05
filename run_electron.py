# run_electron.py (Finale Version mit extra Logging)

import uvicorn
import logging
import sys
import threading
import subprocess
import time
import requests
import os
import psutil
import asyncio
from pathlib import Path
import re
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

# --- ELECTRON APP CONFIGURATION ---
VITE_DEV_COMMAND = ["npm", "run", "dev:renderer"]
ELECTRON_MAIN_COMMAND = ["npm", "run", "dev:main"]
ELECTRON_APP_CWD = FRONTEND_DIR / "packages" / "electron"

class SystemRunner:
    def __init__(self):
        logger.debug("SystemRunner: Initializing class instance.")
        self.backend_port = 8000
        self.frontend_dev_port = 5174
        self.processes = []
        self.running = True
        self.vite_ready_event = threading.Event()
        self.electron_test_results = Queue()
        logger.debug("SystemRunner: Initialization complete.")

    def check_ports_available(self):
        logger.debug("SystemRunner: Starting port availability check.")
        import socket
        ports_to_check = {self.backend_port: "Backend", self.frontend_dev_port: "Frontend Dev Server"}
        all_ports_free = True
        
        for port, service_name in ports_to_check.items():
            logger.info(f"SystemRunner: Checking availability of port {port} ({service_name})...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                sock.close()
                logger.info(f"SystemRunner: Port {port} ({service_name}) is currently available.")
            except socket.error as e:
                logger.warning(f"SystemRunner: Port {port} ({service_name}) is in use: {e}.")
                all_ports_free = False
        logger.debug(f"SystemRunner: Port availability check finished. All ports free: {all_ports_free}")
        return all_ports_free

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
            logger.error(f"SystemRunner: STT script not found: {STT_SCRIPT_PATH}. Cannot start STT module.")
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
            vite_process = subprocess.Popen(VITE_DEV_COMMAND, cwd=str(ELECTRON_APP_CWD), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True if sys.platform == "win32" else False, bufsize=1)
            self.processes.append(vite_process)
            logger.info(f"SystemRunner: Vite dev server process started with PID: {vite_process.pid}")
    
            def log_and_check_output(pipe, prefix):
                try:
                    for line in iter(pipe.readline, ''):
                        logger.info(f"[{prefix}]: {line.strip()}")
                        if "Local:" in line:
                            self.vite_ready_event.set()
                            logger.info("SystemRunner: Vite dev server is ready! (Detected from log output)")
                except ValueError:
                    logger.debug(f"[{prefix}]: Pipe closed unexpectedly.")
                except Exception as e:
                    logger.error(f"[{prefix}]: Error reading from pipe: {e}", exc_info=True)
            
            threading.Thread(target=log_and_check_output, args=(vite_process.stdout, "Vite stdout"), daemon=True).start()
            threading.Thread(target=log_and_check_output, args=(vite_process.stderr, "Vite stderr"), daemon=True).start()
    
            logger.info("SystemRunner: Waiting for Vite dev server readiness...")
            if not self.vite_ready_event.wait(timeout=60):
                logger.critical("SystemRunner: Vite dev server did not become ready within the timeout period.")
                raise RuntimeError("Vite server failed to start.")
        except Exception as e:
            logger.critical(f"SystemRunner: Failed to start Vite server: {e}", exc_info=True)
            raise

    def run_electron_app(self, test_mode=False):
        logger.debug("SystemRunner: Starting Electron app process.")
        try:
            electron_process = subprocess.Popen(ELECTRON_MAIN_COMMAND, cwd=str(ELECTRON_APP_CWD), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=0)
            self.processes.append(electron_process)
            logger.info(f"SystemRunner: Electron app process started with PID: {electron_process.pid}")
    
            if test_mode:
                logger.debug("SystemRunner: Starting test logging for Electron.")
                self._start_test_logging(electron_process)
            else:
                logger.debug("SystemRunner: Starting standard logging for Electron.")
                self._start_logging(electron_process, "Electron")
        except Exception as e:
            logger.critical(f"SystemRunner: Failed to start Electron app: {e}", exc_info=True)
            raise

    def _start_logging(self, process, prefix):
        if process.poll() is not None:
            logger.warning(f"SystemRunner: Attempted to start logging for already dead process {prefix} (PID: {process.pid}).")
            return
        def log_output(pipe, prefix):
            try:
                for line in iter(pipe.readline, ''):
                    logger.info(f"[{prefix}]: {line.strip()}")
            except ValueError:
                logger.debug(f"[{prefix}]: Pipe closed unexpectedly for {prefix}.")
            except Exception as e:
                logger.error(f"[{prefix}]: Error reading from pipe: {e}", exc_info=True)
        threading.Thread(target=log_output, args=(process.stdout, f"{prefix} stdout"), daemon=True).start()
        threading.Thread(target=log_output, args=(process.stderr, f"{prefix} stderr"), daemon=True).start()

    def _start_test_logging(self, process):
        if process.poll() is not None:
            logger.warning(f"SystemRunner: Attempted to start test logging for already dead process (PID: {process.pid}).")
            return

        def log_test_output(pipe, prefix):
            try:
                for line in iter(pipe.readline, ''):
                    line_stripped = line.strip()
                    logger.info(f"[{prefix}]: {line_stripped}")
                    if "Electron IPC Communication Tests Finished" in line_stripped:
                        self.electron_test_results.put("ipc_finished")
                        logger.debug("SystemRunner: Detected IPC tests finished.")
                    if "Backend WebSocket Communication Tests Finished" in line_stripped:
                        self.electron_test_results.put("ws_finished")
                        logger.debug("SystemRunner: Detected WebSocket tests finished.")
                    if "Error" in line_stripped:
                        self.electron_test_results.put("error")
                        logger.debug("SystemRunner: Detected 'Error' keyword in log.")
            except ValueError:
                logger.debug(f"[{prefix}]: Pipe closed unexpectedly.")
            except Exception as e:
                logger.error(f"[{prefix}]: Error reading from pipe: {e}", exc_info=True)
        
        threading.Thread(target=log_test_output, args=(process.stdout, "Electron stdout (Test)"), daemon=True).start()
        threading.Thread(target=log_test_output, args=(process.stderr, "Electron stderr (Test)"), daemon=True).start()

    def check_backend_ready(self, timeout=60):
        logger.debug("SystemRunner: Starting backend readiness check.")
        url = f"http://127.0.0.1:{self.backend_port}/"
        start_time = time.time()
        logger.info(f"SystemRunner: Waiting for backend to be ready at {url} (timeout {timeout}s)...")
        while time.time() - start_time < timeout:
            try:
                response = requests.get(url, timeout=2)
                if response.status_code == 200:
                    logger.info("SystemRunner: Backend is ready!")
                    return True
                else:
                    logger.debug(f"SystemRunner: Backend responded with status {response.status_code}. Retrying...")
            except requests.exceptions.ConnectionError:
                logger.debug(f"SystemRunner: Connection to backend at {url} refused. Retrying...")
            except requests.exceptions.Timeout:
                logger.debug(f"SystemRunner: Backend request timed out. Retrying...")
            except Exception as e:
                logger.debug(f"SystemRunner: An unexpected error occurred while checking backend: {e}")
            time.sleep(1)
        logger.critical("SystemRunner: Backend did not become ready within the timeout period.")
        return False
    
    def shutdown(self):
        logger.info("SystemRunner: Initiating shutdown for all managed processes...")
        self.running = False
        for p in reversed(self.processes):
            if p.poll() is None:
                logger.info(f"SystemRunner: Terminating process {p.pid} ({p.args[0] if p.args else 'Unknown'})...")
                try:
                    p.terminate()
                    p.wait(timeout=10)
                    if p.poll() is None:
                        logger.warning(f"SystemRunner: Process {p.pid} did not terminate gracefully, killing it.")
                        p.kill()
                        p.wait(timeout=5)
                except psutil.NoSuchProcess:
                    logger.debug(f"SystemRunner: Process {p.pid} already gone.")
                except Exception as e:
                    logger.error(f"SystemRunner: Error during termination of process {p.pid}: {e}", exc_info=True)
            else:
                logger.debug(f"SystemRunner: Process {p.pid} was already dead.")
        logger.info("SystemRunner: All managed processes attempted to be terminated.")
        sys.exit(0)

def run_tests(runner):
    logger.info("--- TEST-MODUS AKTIVIERT ---")
    try:
        logger.debug("Test-Workflow: Step 1 - Checking ports.")
        if not runner.check_ports_available():
            raise RuntimeError("Required ports are not available.")

        logger.debug("Test-Workflow: Step 2 - Starting backend server.")
        runner.run_backend_server()
        if not runner.check_backend_ready():
            raise RuntimeError("Backend did not become ready.")
        
        logger.debug("Test-Workflow: Step 3 - Starting STT module.")
        runner.run_stt_module()
        time.sleep(2)
        
        logger.debug("Test-Workflow: Step 4 - Starting Vite dev server.")
        runner.run_vite_dev_server() 
        logger.debug("Test-Workflow: Step 5 - Starting Electron app in test mode.")
        runner.run_electron_app(test_mode=True)
        
        # Warten 5 Sekunden, bevor wir die Logs scannen.
        # Das gibt dem Electron-Renderer genug Zeit, die Tests zu starten.
        logger.info("Test-Workflow: Warte 5 Sekunden, um dem Electron-Renderer Zeit für die Testausführung zu geben.")
        time.sleep(5)
        
        logger.debug("Test-Workflow: Step 6 - Entering loop to check for test results.")
        test_ipc_ok = False
        test_ws_ok = False
        start_time = time.time()
        timeout = 60  # Timeout für alle Tests

        while time.time() - start_time < timeout:
            if not runner.electron_test_results.empty():
                result = runner.electron_test_results.get_nowait()
                if result == "ipc_finished":
                    test_ipc_ok = True
                    logger.info("Test-Workflow: ✅ IPC-Tests im Electron-Renderer erfolgreich.")
                elif result == "ws_finished":
                    test_ws_ok = True
                    logger.info("Test-Workflow: ✅ WebSocket-Tests im Electron-Renderer erfolgreich.")
                elif result == "error":
                    raise RuntimeError("Ein Fehler wurde in den Renderer-Tests festgestellt.")
            
            if test_ipc_ok and test_ws_ok:
                break
            
            time.sleep(0.5)

        logger.debug("Test-Workflow: Loop finished. Checking final results.")
        if not test_ipc_ok or not test_ws_ok:
            raise TimeoutError("Timeout beim Warten auf Testergebnisse der Electron-App.")

        print("✅ Alle System-Tests erfolgreich abgeschlossen!")
    except Exception as e:
        logger.critical(f"❌ System-Tests fehlgeschlagen: {e}", exc_info=True)
        raise
    finally:
        logger.debug("Test-Workflow: Executing final shutdown.")
        runner.shutdown()

if __name__ == "__main__":
    logger.debug("Main: Starting script execution.")
    runner = SystemRunner()
    
    if '--test' in sys.argv:
        logger.debug("Main: '--test' flag detected. Running tests.")
        try:
            run_tests(runner)
        except (KeyboardInterrupt, RuntimeError, TimeoutError) as e:
            logger.critical(f"Main: Abbruch des Testworkflows: {e}")
        except Exception as e:
            logger.critical(f"Main: Ein unerwarteter Fehler im Test-Workflow: {e}", exc_info=True)
        finally:
            logger.debug("Main: Final shutdown from main block.")
            runner.shutdown()
    else:
        logger.debug("Main: No '--test' flag detected. Running in normal mode.")
        try:
            runner.run_backend_server()
            if not runner.check_backend_ready():
                runner.shutdown()
                sys.exit(1)

            time.sleep(2)
            runner.run_stt_module()
            time.sleep(2)
            runner.run_vite_dev_server()
            runner.run_electron_app()
            
            logger.info("All services launched. Press Ctrl+C to stop.")
            while runner.running:
                for p in runner.processes:
                    if p.poll() is not None:
                        logger.critical(f"Managed process {p.args[0] if p.args else 'Unknown'} (PID: {p.pid}) has terminated unexpectedly with exit code {p.returncode}.")
                        runner.shutdown()
                        sys.exit(1)
                time.sleep(3)
        except KeyboardInterrupt:
            logger.info("Ctrl+C detected. Initiating graceful shutdown.")
            runner.shutdown()
        except Exception as e:
            logger.critical(f"An unexpected error occurred in SystemRunner's main execution block: {e}", exc_info=True)
            runner.shutdown()
            sys.exit(1)