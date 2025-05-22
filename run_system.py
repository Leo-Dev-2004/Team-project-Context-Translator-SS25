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
        import platform
        import subprocess
        import psutil
        
        for port in [self.backend_port, self.frontend_port]:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.bind(("localhost", port))
                sock.close()
            except socket.error:
                logger.warning(f"Port {port} is in use, attempting to kill process...")
                try:
                    # Cross-platform way to find and kill process
                    for proc in psutil.process_iter(['pid', 'name']):
                        try:
                            # Get connections if available (may not work on all platforms)
                            conns = proc.connections() if hasattr(proc, 'connections') else []
                            for conn in conns:
                                if hasattr(conn, 'laddr') and conn.laddr and conn.laddr.port == port:
                                    logger.warning(f"Killing process {proc.pid} ({proc.name()}) using port {port}")
                                    proc.kill()
                                    time.sleep(1)  # Wait for port to be released
                                    break
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                    
                    # Verify port is now free
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.bind(("localhost", port))
                    sock.close()
                    logger.info(f"Port {port} is now available")
                except Exception as e:
                    logger.error(f"Failed to free port {port}: {e}")
                    return False
        return True

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
        frontend = subprocess.Popen(
            [
                sys.executable, 
                "-m", "http.server", 
                str(self.frontend_port),
                "--directory", str(FRONTEND_DIR)
            ],
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
