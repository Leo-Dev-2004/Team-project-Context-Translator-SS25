# SystemRunner.py (Updated for Electron dev:electron command)

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
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('system.log', mode='w') # mode w überschreibt system.log statt anzuhängen
    ]
)
logger = logging.getLogger(__name__)

# Project paths
ROOT_DIR = Path(__file__).parent # The root of your project
BACKEND_DIR = ROOT_DIR / "Backend"
FRONTEND_DIR = ROOT_DIR / "Frontend" # This is where your package.json and Electron app lives
STT_SCRIPT_PATH = BACKEND_DIR / "STT" / "transcribe.py" # Path to your STT script

# --- ELECTRON APP CONFIGURATION ---
# Command to run Electron app in development mode
ELECTRON_DEV_COMMAND = ["npm", "run", "dev:electron"]
ELECTRON_APP_CWD = FRONTEND_DIR # The directory where 'npm run dev:electron' should be executed

class SystemRunner:
    def __init__(self):
        self.backend_port = 8000
        self.processes = []
        self.running = True

    def check_ports_available(self):
        """Check if required ports are available and kill processes using them"""
        import socket
        
        ports_to_check = {
            self.backend_port: "Backend"
        }
        
        all_ports_available = True
        
        for port, service_name in ports_to_check.items():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                # Use SO_REUSEADDR for more robust port binding on restart
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
                sock.bind(("localhost", port))
                sock.close()
                logger.debug(f"Port {port} ({service_name}) is available")
            except socket.error:
                logger.warning(f"Port {port} ({service_name}) is in use, attempting to kill process...")
                
                try:
                    for conn in psutil.net_connections():
                        if conn.status == 'LISTEN' and isinstance(conn.laddr, tuple) and len(conn.laddr) >= 2 and conn.laddr[1] == port:
                            try:
                                proc = psutil.Process(conn.pid)
                                logger.warning(f"Killing process {proc.pid} ({proc.name()}) using port {port}")
                                proc.terminate()
                                proc.wait(timeout=3)
                                time.sleep(1) # Give OS time to release port
                            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired) as e:
                                logger.warning(f"Error terminating process {conn.pid}: {e}")
                                continue
                    
                    # Verify port is now free after attempted kill
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind(("localhost", port))
                    sock.close()
                    logger.info(f"Port {port} is now available")
                except Exception as e:
                    logger.error(f"Failed to free port {port}: {e}")
                    all_ports_available = False
                    continue
        
        return all_ports_available

    def run_backend_server(self):
        """Run FastAPI backend with Uvicorn"""
        if not self.check_ports_available():
            sys.exit(1)

        logger.info("Starting backend server...")
        # Reduce verbosity of third-party libraries
        logging.getLogger('uvicorn.access').setLevel(logging.INFO)
        logging.getLogger('uvicorn.error').setLevel(logging.INFO)
        logging.getLogger('websockets').setLevel(logging.INFO)
        logging.getLogger('asyncio').setLevel(logging.INFO)

        # Set PYTHONPATH to the root directory so Backend modules can be found
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT_DIR) # Set to project root directory
        logger.info(f"Backend PYTHONPATH set to: {env['PYTHONPATH']}")

        backend = subprocess.Popen(
            [
                sys.executable, 
                "-m", "uvicorn", 
                "Backend.backend:app", # Assuming Backend/backend.py exposes 'app'
                "--host", "0.0.0.0",
                "--port", str(self.backend_port),
               # "--reload" # --reload can be useful for development but might restart STT/Electron
            ],
            cwd=str(ROOT_DIR), # Execute uvicorn from the project root
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        self.processes.append(backend)
        self._start_logging(backend, "Backend")

    def run_stt_module(self):
        """Run the transcribe.py as a separate process."""
        if not STT_SCRIPT_PATH.exists():
            logger.error(f"STT script not found: {STT_SCRIPT_PATH}. Cannot start STT module.")
            return

        logger.info(f"Starting STT module: {STT_SCRIPT_PATH}...")
        
        # Ensure STT script can find its dependencies (e.g., faster-whisper)
        # by setting PYTHONPATH to the project root for the STT subprocess
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT_DIR)
        logger.info(f"STT module PYTHONPATH set to: {env['PYTHONPATH']}")

        stt_process = subprocess.Popen(
            [sys.executable, str(STT_SCRIPT_PATH)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(STT_SCRIPT_PATH.parent), # Execute from STT script's directory (or ROOT_DIR)
            env=env # Pass environment variables
        )
        self.processes.append(stt_process)
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
                shell=True if sys.platform == "win32" else False # Use shell=True on Windows for npm commands
            )
            self.processes.append(electron_process)
            self._start_logging(electron_process, "Electron")
            logger.info("Electron app started successfully.")
        except FileNotFoundError:
            logger.error(f"Command '{ELECTRON_DEV_COMMAND[0]}' not found. Make sure Node.js and npm are installed and in your system's PATH. If npm is not in PATH, you might need to provide the full path to npm or ensure your environment is set up for Node.js development.")
        except Exception as e:
            logger.error(f"Failed to start Electron app: {e}", exc_info=True)


    def _start_logging(self, process, prefix):
        """Start logging for a subprocess"""
        def log_output(pipe, prefix):
            for line in pipe:
                logger.info(f"{prefix}: {line.strip()}")

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

    def check_backend_ready(self, timeout=30):
        """Poll the backend until it's ready to accept connections."""
        url = f"http://localhost:{self.backend_port}/"
        start_time = time.time()
        logger.info(f"Waiting for backend to be ready at {url}...")
        while time.time() - start_time < timeout:
            try:
                response = requests.get(url, timeout=1)
                if response.status_code == 200:
                    logger.info("Backend is ready!")
                    return True
            except requests.exceptions.ConnectionError:
                pass
            time.sleep(0.5)
        logger.error("Backend did not become ready within the timeout period.")
        return False

    def shutdown(self):
        """Clean shutdown handler"""
        logger.info("Shutting down all processes...")
        self.running = False # Signal to main loop to exit
        for p in self.processes:
            try:
                p.terminate() 
                p.wait(timeout=5)
                if p.poll() is None:
                    logger.warning(f"Process {p.pid} did not terminate, killing it.")
                    p.kill()
                    p.wait(timeout=2)
            except psutil.NoSuchProcess:
                logger.debug(f"Process {p.pid} already gone.")
            except Exception as e:
                logger.warning(f"Error terminating process {p.pid}: {e}")
        logger.info("All processes terminated.")
        sys.exit(0)

if __name__ == "__main__":
    runner = SystemRunner()
    
    try:
        runner.run_backend_server()
        if not runner.check_backend_ready():
            logger.critical("Backend did not start correctly. Exiting.")
            runner.shutdown()
            sys.exit(1)

        # Give backend a moment to fully spin up before STT connects
        time.sleep(1) 
        runner.run_stt_module() # Now launch the STT module
        
        # Give STT a moment to start before Electron potentially connects/depends on it
        time.sleep(1) 
        runner.run_electron_app() # And your Electron app

        logger.info("All services launched. Press Ctrl+C to stop.")
        
        # Keep main thread alive
        while runner.running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Ctrl+C detected.")
        runner.shutdown()
    except Exception as e:
        logger.critical(f"An unexpected error occurred in SystemRunner: {e}", exc_info=True)
        runner.shutdown()
        sys.exit(1)