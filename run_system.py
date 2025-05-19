import subprocess
import threading
import time
import webbrowser
import signal
import sys
from fastapi import FastAPI
import uvicorn
from Backend.backend import app
import requests
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class SystemRunner:
    def __init__(self):
        self.processes = []
        self.running = True
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

    def run_backend(self):
        """Run the FastAPI backend server"""
        logger.info("Starting backend server...")
        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="debug",
            access_log=True
        )
        server = uvicorn.Server(config)
        logger.info("Backend server configured, starting...")
        server.run()

    def start_simulation(self):
        """Start the simulation after server is ready"""
        max_retries = 10
        retry_count = 0
        
        while self.running and retry_count < max_retries:
            try:
                # First check if backend is responsive
                health = requests.get("http://localhost:8000/health")
                if health.status_code == 200:
                    print("Backend is ready, starting simulation...")
                    # Start simulation
                    response = requests.get("http://localhost:8000/simulation/start")
                    if response.status_code == 200:
                        print(f"Simulation started successfully: {response.json()}")
                        # Monitor simulation status
                        while self.running:
                            status = requests.get("http://localhost:8000/simulation/status").json()
                            print(f"Simulation status: {status}")
                            time.sleep(2)
                        break
                    else:
                        print(f"Failed to start simulation: {response.json()}")
                else:
                    print(f"Backend not ready yet (HTTP {health.status_code})")
            except Exception as e:
                print(f"Error connecting to backend: {str(e)}")
            
            retry_count += 1
            time.sleep(1)
        
        if retry_count >= max_retries:
            print("Failed to start simulation after maximum retries")

    def run_frontend_server(self):
        """Run the frontend HTTP server"""
        logger.info("Starting frontend HTTP server...")
        frontend = subprocess.Popen(
            ["python", "-m", "http.server", "9000", "--directory", "Frontend"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        self.processes.append(frontend)
        
        # Log frontend server output in real-time
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

    def open_browser(self):
        """Open the frontend in browser"""
        logger.info("Waiting 3 seconds before opening browser...")
        time.sleep(3)
        url = "http://localhost:9000/index.html"
        logger.info(f"Opening browser to {url}")
        webbrowser.open(url)

    def shutdown(self, signum, frame):
        """Clean shutdown handler"""
        print("\nShutting down system...")
        self.running = False
        for p in self.processes:
            p.terminate()
        sys.exit(0)

    def run(self):
        """Run all system components"""
        logger.info("Starting system components...")
        
        # Start frontend HTTP server
        self.run_frontend_server()

        # Start backend in thread
        backend_thread = threading.Thread(
            target=self.run_backend,
            daemon=True,
            name="BackendThread"
        )
        backend_thread.start()
        logger.info("Backend thread started")

        # Open browser
        browser_thread = threading.Thread(
            target=self.open_browser,
            daemon=True,
            name="BrowserThread"
        )
        browser_thread.start()
        logger.info("Browser thread started")

        # Monitor system status
        logger.info("Entering main loop...")
        while self.running:
            try:
                # Check backend health
                health = requests.get("http://localhost:8000/health", timeout=1)
                logger.debug(f"Backend health: {health.status_code}")
                
                # Check frontend health
                frontend = requests.get("http://localhost:9000", timeout=1)
                logger.debug(f"Frontend health: {frontend.status_code}")
                
                time.sleep(5)
            except requests.exceptions.RequestException as e:
                logger.warning(f"Health check failed: {str(e)}")
                time.sleep(1)
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {str(e)}")
                self.shutdown(None, None)

if __name__ == "__main__":
    runner = SystemRunner()
    runner.run()
