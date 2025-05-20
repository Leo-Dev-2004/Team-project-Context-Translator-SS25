import uvicorn
import logging
import sys
import threading
import subprocess
import webbrowser
import time
import requests

# Configure logging for run_system.py itself
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import the FastAPI app instance from your backend
# Make sure this path is correct for your project structure
# e.g., if 'backend.py' is directly in 'Backend', use 'Backend.backend'
from Backend.backend import app

class SystemRunner:
    def __init__(self):
        self.processes = []
        self.running = True # Flag to control main loop for Uvicorn and other services

    def run_backend_server(self):
        """Run the Uvicorn server for the FastAPI backend."""
        logger.info("Starting backend Uvicorn server...")
        # Uvicorn will handle its own logging and startup/shutdown events
        # We don't need to put it in a subprocess here, as this script is the main entry point
        # and uvicorn.run blocks.
        # This function is designed to be called directly from if __name__ == "__main__"
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info", # Adjust as needed (debug, info, warning, error, critical)
            access_log=True
        )

    def run_frontend_server(self):
        """Run the frontend HTTP server in a separate thread."""
        logger.info("Starting frontend HTTP server...")
        try:
            # Use sys.executable to ensure the correct python interpreter is used
            frontend = subprocess.Popen(
                [sys.executable, "-m", "http.server", "9000", "--directory", "Frontend"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            self.processes.append(frontend)

            def log_output(pipe, prefix):
                for line in pipe:
                    logger.debug(f"{prefix}: {line.strip()}")

            threading.Thread(
                target=log_output,
                args=(frontend.stdout, "Frontend stdout"),
                daemon=True
            ).start()
            threading.Thread(
                target=log_output,
                args=(frontend.stderr, "Frontend stderr"),
                daemon=True
            ).start()

            logger.info("Frontend server started on port 9000")
        except Exception as e:
            logger.error(f"Failed to start frontend server: {e}")

    def open_browser(self):
        """Open the frontend in browser after a short delay."""
        logger.info("Waiting 3 seconds before opening browser...")
        time.sleep(3) # Give servers a moment to start
        url = "http://localhost:9000/index.html"
        logger.info(f"Opening browser to {url}")
        try:
            webbrowser.open(url)
        except Exception as e:
            logger.error(f"Failed to open browser: {e}")

    def trigger_simulation_start(self):
        """Trigger the simulation start via API in a separate thread."""
        def _trigger():
            backend_url = "http://localhost:8000/health"
            simulation_start_url = "http://localhost:8000/simulation/start"
            max_retries = 20
            retry_count = 0

            logger.info("Attempting to connect to backend and start simulation...")
            while retry_count < max_retries and self.running:
                try:
                    health_response = requests.get(backend_url, timeout=1)
                    if health_response.status_code == 200:
                        logger.info("Backend is ready. Attempting to start simulation.")
                        start_response = requests.get(simulation_start_url, timeout=5)
                        if start_response.status_code == 200:
                            logger.info(f"Simulation started successfully: {start_response.json()}")
                            return
                        else:
                            logger.warning(f"Failed to start simulation (HTTP {start_response.status_code}): {start_response.json()}")
                    else:
                        logger.info(f"Backend not ready yet (HTTP {health_response.status_code}). Retrying...")
                except requests.exceptions.ConnectionError:
                    logger.info("Backend not reachable. Retrying...")
                except Exception as e:
                    logger.error(f"Error during simulation start attempt: {e}")

                retry_count += 1
                time.sleep(1)

            if retry_count >= max_retries:
                logger.error("Failed to start simulation after maximum retries. Please check backend logs.")

        # Run in a separate thread to not block the main Uvicorn server start
        threading.Thread(target=_trigger, daemon=True).start()

    def shutdown(self, signum=None, frame=None):
        """Clean shutdown handler."""
        logger.info("Shutting down system...")
        self.running = False # Signal other threads to stop
        for p in self.processes:
            if p.poll() is None: # Only terminate if still running
                logger.info(f"Terminating process {p.pid}...")
                p.terminate()
                p.wait(timeout=5) # Wait for process to terminate
                if p.poll() is None:
                    logger.warning(f"Process {p.pid} did not terminate gracefully, killing...")
                    p.kill()
        sys.exit(0)

if __name__ == "__main__":
    runner = SystemRunner()

    # Register shutdown handler for graceful exit on Ctrl+C
    import signal
    signal.signal(signal.SIGINT, runner.shutdown)
    signal.signal(signal.SIGTERM, runner.shutdown)

    # Start frontend server in a separate thread
    frontend_thread = threading.Thread(target=runner.run_frontend_server, daemon=True)
    frontend_thread.start()

    # Open browser in a separate thread
    browser_thread = threading.Thread(target=runner.open_browser, daemon=True)
    browser_thread.start()
    
    # Trigger simulation start via API in a separate thread
    # This must happen *after* the backend server is expected to be up and running.
    # The _trigger function handles waiting for the backend.
    runner.trigger_simulation_start()

    # Run the backend server (this will block the main thread until it shuts down)
    # All queue initialization and async task management is now handled within app.on_event("startup") in Backend/backend.py
    runner.run_backend_server()