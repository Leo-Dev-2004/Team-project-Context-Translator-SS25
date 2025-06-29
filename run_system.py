# SystemRunner.py

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

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, # Set to INFO for less verbosity in production
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s', # Added %(name)s for better source identification
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('system.log', mode='w', encoding='utf-8') # Added encoding for robustness
    ]
)
logger = logging.getLogger('SystemRunner') # Use a specific logger name

# Project paths
ROOT_DIR = Path(__file__).parent.resolve() # Get absolute path
BACKEND_DIR = ROOT_DIR / "Backend"
FRONTEND_DIR = ROOT_DIR / "Frontend" # This is where your package.json and Electron app lives
STT_SCRIPT_PATH = BACKEND_DIR / "STT" / "transcribe.py" # Path to your STT script

# --- ELECTRON APP CONFIGURATION ---
# Command to run Electron app in development mode
# Ensure these commands are correctly set up in your package.json
# Using shell=True for npm commands on Windows is usually safer.
ELECTRON_DEV_COMMAND = ["npm", "run", "dev:electron"]
ELECTRON_APP_CWD = FRONTEND_DIR # The directory where 'npm run dev:electron' should be executed

class SystemRunner:
    def __init__(self):
        self.backend_port = 8000
        self.processes = [] # List to store Popen objects
        self.running = True # Flag to control the main loop

    def check_ports_available(self):
        """
        Check if required ports are available and attempt to kill processes using them.
        Returns True if all ports are available after checks/kills, False otherwise.
        """
        import socket
        
        ports_to_check = {
            self.backend_port: "Backend"
            # Add other ports if your Electron app or STT module use fixed ports
            # e.g., 3000: "Electron Dev Server" if Vite/Webpack is used for frontend dev
        }
        
        all_ports_free = True
        
        for port, service_name in ports_to_check.items():
            logger.info(f"Checking availability of port {port} ({service_name})...")
            
            # First, try to bind to see if it's free
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Allow address reuse
            try:
                sock.bind(("127.0.0.1", port)) # Bind to localhost explicitly
                sock.close()
                logger.info(f"Port {port} ({service_name}) is currently available.")
            except socket.error as e:
                logger.warning(f"Port {port} ({service_name}) is in use: {e}. Attempting to identify and kill conflicting processes...")
                
                found_and_killed = False
                for conn in psutil.net_connections():
                    if conn.status == 'LISTEN' and conn.laddr and conn.laddr.port == port:
                        try:
                            proc = psutil.Process(conn.pid)
                            logger.warning(f"Found process {proc.pid} ({proc.name()}) using port {port}. Terminating...")
                            proc.terminate() # Send SIGTERM
                            try:
                                proc.wait(timeout=5) # Wait up to 5 seconds for termination
                                logger.info(f"Process {proc.pid} terminated gracefully.")
                            except psutil.TimeoutExpired:
                                logger.warning(f"Process {proc.pid} did not terminate gracefully, killing.")
                                proc.kill() # Send SIGKILL
                                proc.wait(timeout=2)
                            found_and_killed = True
                            time.sleep(0.5) # Give OS a moment to release the port
                        except (psutil.NoSuchProcess, psutil.AccessDenied) as proc_err:
                            logger.error(f"Error accessing or terminating process {conn.pid}: {proc_err}")
                            # Don't mark as killed if we couldn't terminate it
                            found_and_killed = False # Reset if this specific process failed to terminate
                        except Exception as kill_err:
                            logger.error(f"Unexpected error during process kill for PID {conn.pid}: {kill_err}", exc_info=True)
                            found_and_killed = False # Assume failure
                
                if found_and_killed:
                    # After attempting to kill, re-check the port
                    time.sleep(1) # Give the port more time to truly free up
                    try:
                        recheck_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        recheck_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        recheck_sock.bind(("127.0.0.1", port))
                        recheck_sock.close()
                        logger.info(f"Port {port} is now available after cleanup.")
                    except socket.error as recheck_e:
                        logger.critical(f"Port {port} is STILL IN USE after attempting to kill processes: {recheck_e}. Cannot proceed.")
                        all_ports_free = False
                else:
                    logger.critical(f"Port {port} was in use, but no conflicting processes were found or could be killed. Cannot proceed.")
                    all_ports_free = False
            finally:
                sock.close() # Ensure socket is closed
        
        return all_ports_free

    def run_backend_server(self):
        """Run FastAPI backend with Uvicorn"""
        if not self.check_ports_available():
            logger.critical("Required ports are not available. Exiting application.")
            self.shutdown() # Ensure clean shutdown if ports are not free
            sys.exit(1) # Exit if ports are not free

        logger.info("Starting backend server...")
        
        # Configure logging for Uvicorn
        logging.getLogger('uvicorn').setLevel(logging.INFO)
        logging.getLogger('uvicorn.access').setLevel(logging.INFO)
        logging.getLogger('uvicorn.error').setLevel(logging.ERROR) # Only log Uvicorn errors
        logging.getLogger('websockets').setLevel(logging.WARNING) # Reduce websockets noise
        logging.getLogger('asyncio').setLevel(logging.WARNING) # Reduce asyncio noise

        # Set PYTHONPATH to the root directory so Backend modules can be found
        env = os.environ.copy()
        # Ensure ROOT_DIR is the very first entry in PYTHONPATH to prioritize your project's modules
        env["PYTHONPATH"] = str(ROOT_DIR) + os.pathsep + env.get("PYTHONPATH", "")
        logger.info(f"Backend PYTHONPATH set to: {env['PYTHONPATH']}")
        
        # Command to run Uvicorn
        uvicorn_cmd = [
            sys.executable,
            "-m", "uvicorn",
            "Backend.backend:app", # Assuming Backend/backend.py exposes 'app'
            "--host", "0.0.0.0",
            "--port", str(self.backend_port),
            "--log-level", "info", # Control Uvicorn's own logging level
            # "--reload" # --reload can be useful for development but might restart STT/Electron
        ]

        backend = subprocess.Popen(
            uvicorn_cmd,
            cwd=str(ROOT_DIR), # Execute uvicorn from the project root
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1 # Line-buffered output
        )
        self.processes.append(backend)
        logger.info(f"Backend process started with PID: {backend.pid}")
        self._start_logging(backend, "Backend")

    def run_stt_module(self):
        """Run the transcribe.py as a separate process."""
        if not STT_SCRIPT_PATH.exists():
            logger.error(f"STT script not found: {STT_SCRIPT_PATH}. Cannot start STT module.")
            return

        logger.info(f"Starting STT module: {STT_SCRIPT_PATH}...")
        
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT_DIR) + os.pathsep + env.get("PYTHONPATH", "")
        logger.info(f"STT module PYTHONPATH set to: {env['PYTHONPATH']}")

        stt_process = subprocess.Popen(
            [sys.executable, str(STT_SCRIPT_PATH)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(STT_SCRIPT_PATH.parent), # Execute from STT script's directory
            env=env, # Pass environment variables
            bufsize=1 # Line-buffered output
        )
        self.processes.append(stt_process)
        logger.info(f"STT module process started with PID: {stt_process.pid}")
        self._start_logging(stt_process, "STT_Module")

    def run_electron_app(self):
        """Run the Electron desktop application using npm run dev:electron."""
        if not ELECTRON_APP_CWD.exists():
            logger.error(f"Electron app directory not found: {ELECTRON_APP_CWD}. Cannot start Electron app.")
            return

        logger.info(f"Starting Electron app with command: {' '.join(ELECTRON_DEV_COMMAND)} in {ELECTRON_APP_CWD}...")
        try:
            electron_process = subprocess.Popen(
                ELECTRON_DEV_COMMAND,
                cwd=str(ELECTRON_APP_CWD), # Execute npm command from the Frontend directory
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=True if sys.platform == "win32" else False, # Use shell=True on Windows for npm commands
                bufsize=1 # Line-buffered output
            )
            self.processes.append(electron_process)
            logger.info(f"Electron app process started with PID: {electron_process.pid}")
            self._start_logging(electron_process, "Electron")
            logger.info("Electron app launched (check its console/log for further output).")
        except FileNotFoundError:
            logger.error(f"Command '{ELECTRON_DEV_COMMAND[0]}' not found. Make sure Node.js and npm are installed and in your system's PATH. If npm is not in PATH, you might need to provide the full path to npm or ensure your environment is set up for Node.js development.")
        except Exception as e:
            logger.error(f"Failed to start Electron app: {e}", exc_info=True)


    def _start_logging(self, process, prefix):
        """Start logging for a subprocess"""
        # Ensure the process is alive before starting threads
        if process.poll() is not None:
            logger.warning(f"Attempted to start logging for already dead process {prefix} (PID: {process.pid}).")
            return

        def log_output(pipe, prefix):
            try:
                for line in iter(pipe.readline, ''): # Read line by line until EOF
                    logger.info(f"[{prefix}]: {line.strip()}")
            except ValueError: # Pipe might close unexpectedly
                logger.debug(f"[{prefix}]: Pipe closed unexpectedly for {prefix}.")
            except Exception as e:
                logger.error(f"[{prefix}]: Error reading from pipe: {e}", exc_info=True)

        threading.Thread(
            target=log_output,
            args=(process.stdout, f"{prefix} stdout"),
            daemon=True
        ).start()
        threading.Thread(
            target=log_output,
            args=(process.stderr, f"{prefix} stderr"),
            daemon=True
        ).start()

    def check_backend_ready(self, timeout=60): # Increased timeout
        """Poll the backend until it's ready to accept connections."""
        url = f"http://127.0.0.1:{self.backend_port}/" # Use 127.0.0.1 for local checks
        start_time = time.time()
        logger.info(f"Waiting for backend to be ready at {url} (timeout {timeout}s)...")
        while time.time() - start_time < timeout:
            try:
                # Add a specific endpoint check if available, otherwise root
                # e.g., "/health" or "/status"
                response = requests.get(url, timeout=2) # Increased request timeout slightly
                if response.status_code == 200:
                    logger.info("Backend is ready!")
                    return True
                else:
                    logger.debug(f"Backend responded with status {response.status_code}. Retrying...")
            except requests.exceptions.ConnectionError:
                logger.debug(f"Connection to backend at {url} refused. Retrying...")
            except requests.exceptions.Timeout:
                logger.debug(f"Backend request timed out. Retrying...")
            except Exception as e:
                logger.debug(f"An unexpected error occurred while checking backend: {e}")
            time.sleep(1) # Wait longer between checks
        logger.critical("Backend did not become ready within the timeout period. Check backend logs for errors.")
        return False

    def shutdown(self):
        """Clean shutdown handler"""
        logger.info("Initiating shutdown for all managed processes...")
        self.running = False # Signal to main loop to exit

        # Terminate processes in reverse order of starting (optional, but can help dependency chain)
        for p in reversed(self.processes):
            if p.poll() is None: # Only try to terminate if still running
                logger.info(f"Terminating process {p.pid} ({p.args[0] if p.args else 'Unknown'})...")
                try:
                    p.terminate()
                    p.wait(timeout=10) # Give more time for graceful shutdown
                    if p.poll() is None:
                        logger.warning(f"Process {p.pid} did not terminate gracefully, killing it.")
                        p.kill()
                        p.wait(timeout=5) # Wait for kill
                except psutil.NoSuchProcess:
                    logger.debug(f"Process {p.pid} already gone (NoSuchProcess).")
                except Exception as e:
                    logger.error(f"Error during termination of process {p.pid}: {e}", exc_info=True)
            else:
                logger.debug(f"Process {p.pid} was already dead.")
        
        # Verify no ports are left open by our processes
        logger.info("Verifying ports are released...")
        time.sleep(2) # Give system a moment after processes are killed
        # Re-run check_ports_available in a non-killing mode if needed, or simply log if ports are still held
        
        logger.info("All managed processes attempted to be terminated.")
        
        # This sys.exit(0) will exit the SystemRunner script itself
        # If this script is called by another, that caller needs to handle the exit code.
        sys.exit(0)

if __name__ == "__main__":
    runner = SystemRunner()
    
    # Check if this script is being run as a subprocess (e.g., by Uvicorn's --reload)
    # This is a common cause of multiple server starts
    if 'UVICORN_SERVER_RELOAD' in os.environ:
        logger.warning("SystemRunner detected UVICORN_SERVER_RELOAD environment variable. This script might be re-executing due to Uvicorn's --reload. This setup is not recommended for orchestrating multiple processes.")
        logger.warning("If you intend to use --reload, run Uvicorn directly for the backend, and manage other services separately, or remove --reload from the backend command here.")
        # If you truly want to prevent re-execution, you might uncomment sys.exit(0) here,
        # but that would prevent --reload from working at all for the backend.
        # sys.exit(0)

    try:
        # Start services
        runner.run_backend_server()
        
        # Add a check here to ensure the backend process is actually running before polling
        if runner.processes and runner.processes[0].poll() is not None:
             logger.critical(f"Backend process (PID: {runner.processes[0].pid}) exited immediately. Check its error logs.")
             runner.shutdown()
             sys.exit(1)

        if not runner.check_backend_ready():
            logger.critical("Backend did not become ready. Check logs for errors. Shutting down.")
            runner.shutdown()
            sys.exit(1)

        # Give backend a moment to fully spin up before other services try to connect
        time.sleep(2) # Increased pause

        runner.run_stt_module() # Now launch the STT module
        # Add a check for STT process as well
        if runner.processes and runner.processes[1].poll() is not None: # Assuming STT is the second process
             logger.critical(f"STT process (PID: {runner.processes[1].pid}) exited immediately. Check its error logs.")
             runner.shutdown()
             sys.exit(1)
        
        time.sleep(2) # Increased pause
        runner.run_electron_app() # And your Electron app
        # Add a check for Electron process as well
        if runner.processes and len(runner.processes) > 2 and runner.processes[2].poll() is not None: # Assuming Electron is the third process
             logger.critical(f"Electron process (PID: {runner.processes[2].pid}) exited immediately. Check its error logs.")
             runner.shutdown()
             sys.exit(1)

        logger.info("All services launched. Press Ctrl+C to stop.")
        
        # Main loop to keep the orchestrator alive and monitor subprocesses
        while runner.running:
            # Basic health check: check if any managed process has died
            for i, p in enumerate(runner.processes):
                if p.poll() is not None: # Process has terminated
                    logger.critical(f"Managed process {p.args[0] if p.args else 'Unknown'} (PID: {p.pid}) has terminated unexpectedly with exit code {p.returncode}. This indicates a crash or unhandled exit.")
                    # Optionally, you could try to restart it, or shut down everything
                    runner.shutdown()
                    sys.exit(1)
            time.sleep(3) # Check every 3 seconds
            
    except KeyboardInterrupt:
        logger.info("Ctrl+C detected. Initiating graceful shutdown.")
        runner.shutdown()
    except Exception as e:
        logger.critical(f"An unexpected error occurred in SystemRunner's main execution block: {e}", exc_info=True)
        runner.shutdown()
        sys.exit(1)