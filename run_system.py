import uvicorn
import logging
import sys
import threading
import subprocess
import webbrowser
import time
import requests
import os
import psutil
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('system.log')
    ]
)
logger = logging.getLogger(__name__)

# Project paths
BACKEND_DIR = Path(__file__).parent / "Backend"
FRONTEND_DIR = Path(__file__).parent / "Frontend"

class SystemRunner:
    def __init__(self):
        self.backend_port = 8000
        self.frontend_port = 9000
        self.processes = []
        self.running = True

    def check_ports_available(self):
        """Check if required ports are available and kill processes using them"""
        import socket
        import psutil
        
        ports_to_check = {
            self.backend_port: "Backend",
            self.frontend_port: "Frontend"
        }
        
        all_ports_available = True
        
        for port, service_name in ports_to_check.items():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.bind(("localhost", port))
                sock.close()
                logger.debug(f"Port {port} ({service_name}) is available")
            except socket.error:
                logger.warning(f"Port {port} ({service_name}) is in use, attempting to kill process...")
                
                try:
                    # Find process using the port (works on Linux/Unix/Windows)
                    for conn in psutil.net_connections():
                        if conn.status == 'LISTEN' and isinstance(conn.laddr, tuple) and len(conn.laddr) >= 2 and conn.laddr[1] == port:
                            try:
                                proc = psutil.Process(conn.pid)
                                logger.warning(f"Killing process {proc.pid} ({proc.name()}) using port {port}")
                                proc.terminate()
                                proc.wait(timeout=3)
                                time.sleep(1)  # Wait for port to be released
                            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired) as e:
                                logger.warning(f"Error terminating process: {e}")
                                continue
                    
                    # Verify port is now free
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
        # Use clean environment without PYTHONPATH override
        env = os.environ.copy()

        # Add debug logs to verify working directory and environment variables
        logger.info(f"Current working directory: {os.getcwd()}")
        env["PYTHONPATH"] = str(BACKEND_DIR.parent)
        logger.info(f"PYTHONPATH set to: {env['PYTHONPATH']}")

        backend = subprocess.Popen(
            [
                sys.executable, 
                "-m", "uvicorn", 
                "Backend.backend:app",
                "--host", "0.0.0.0",
                "--port", str(self.backend_port),
                "--reload"
            ],
            cwd=str(BACKEND_DIR.parent),  # Set to project root directory
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        self.processes.append(backend)
        self._start_logging(backend, "Backend")

    def run_frontend_server(self):
        """Run frontend HTTP server"""
        logger.info("Starting frontend server...")
        
        # Ensure frontend directory exists
        if not FRONTEND_DIR.exists():
            raise FileNotFoundError(f"Frontend directory not found: {FRONTEND_DIR}")

        # Debug log the directory structure
        logger.info(f"Frontend directory contents: {list(FRONTEND_DIR.glob('*'))}")
        if (FRONTEND_DIR / 'src').exists():
            logger.info(f"src directory contents: {list((FRONTEND_DIR / 'src').glob('*'))}")

        frontend = subprocess.Popen(
            [
                sys.executable, 
                "-m", "http.server", 
                str(self.frontend_port),
                "--directory", str(FRONTEND_DIR),
                "--bind", "0.0.0.0"
            ],
            cwd=str(FRONTEND_DIR),  # Wichtig: Arbeitsverzeichnis setzen
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        self.processes.append(frontend)
        self._start_logging(frontend, "Frontend")

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

    def open_browser(self):
        """Open browser to frontend"""
        time.sleep(2)  # Wait for servers to start
        url = f"http://localhost:{self.frontend_port}"
        logger.info(f"Opening browser to {url}")
        try:
            webbrowser.open(url)
        except Exception as e:
            logger.error(f"Failed to open browser: {e}")

    def shutdown(self):
        """Clean shutdown handler"""
        logger.info("Shutting down servers...")
        for p in self.processes:
            try:
                p.terminate()
                p.wait(timeout=3)
            except Exception as e:
                logger.warning(f"Error terminating process: {e}")
        sys.exit(0)

if __name__ == "__main__":
    runner = SystemRunner()
    
    try:
        runner.run_backend_server()
        runner.run_frontend_server()
        runner.open_browser()
        
        # Keep main thread alive
        while runner.running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        runner.shutdown()
