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
        
        # Run server in a thread so we can check when it's ready
        def run_server():
            logger.info("Backend server starting...")
            server.run()
            
        backend_thread = threading.Thread(
            target=run_server,
            daemon=True
        )
        backend_thread.start()
        
        # Wait for server to be ready
        max_retries = 20
        retry_count = 0
        while retry_count < max_retries:
            try:
                health = requests.get("http://localhost:8000/health", timeout=0.5)
                if health.status_code == 200:
                    logger.info("Backend server is ready")
                    return
            except Exception:
                logger.debug(f"Waiting for backend to start... ({retry_count+1}/{max_retries})")
                retry_count += 1
                time.sleep(0.5)
                
        logger.error("Backend server failed to start")

    def start_simulation(self):
        """Start the simulation after server is ready"""
        max_retries = 10
        retry_count = 0
        
        while self.running and retry_count < max_retries:
            try:
                # First check if backend is responsive
                print("\nChecking backend health...")
                health = requests.get("http://localhost:8000/health")
                if health.status_code == 200:
                    print("\n=== BACKEND READY ===")
                    print("Starting simulation...")
                    # Start simulation
                    print("Making request to /simulation/start...")
                    response = requests.get("http://localhost:8000/simulation/start")
                    if response.status_code == 200:
                        print("\n=== SIMULATION STARTED ===")
                        print(f"Response: {response.json()}")
                        print("Starting queue monitoring...")
                        # Monitor simulation status
                        while self.running:
                            print("\n=== QUEUE STATUS ===")
                            status = requests.get("http://localhost:8000/simulation/status").json()
                            print(f"to_frontend_queue: {status['to_frontend_queue_size']}")
                            print(f"from_frontend_queue: {status['from_frontend_queue_size']}")
                            print(f"to_backend_queue: {status['to_backend_queue_size']}")
                            print(f"from_backend_queue: {status['from_backend_queue_size']}")
                            
                            # Get detailed queue contents
                            print("\nQueue Contents:")
                            queues = requests.get("http://localhost:8000/queues/debug").json()
                            for qname, items in queues.items():
                                print(f"{qname}: {len(items)} items")
                                for i, item in enumerate(items[:3]):  # Show first 3 items
                                    print(f"  {i+1}. {item.get('type', '?')} - {item.get('status', '?')}")
                            
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
                # Only check backend health if no active WebSockets
                if not hasattr(app.state, 'websockets') or len(app.state.websockets) == 0:
                    try:
                        health = requests.get("http://localhost:8000/health", timeout=0.5)
                        if health.status_code != 200:
                            logger.warning(f"Backend health check failed: {health.status_code}")
                    except requests.exceptions.RequestException as e:
                        logger.debug(f"Backend health check: {str(e)}")
                
                # Check frontend less frequently
                if time.time() % 10 < 0.5:  # ~every 10 seconds
                    try:
                        frontend = requests.get("http://localhost:9000", timeout=0.5)
                        if frontend.status_code != 200:
                            logger.warning(f"Frontend health check failed: {frontend.status_code}")
                    except requests.exceptions.RequestException as e:
                        logger.debug(f"Frontend health check: {str(e)}")
                
                # Periodic status report
                if time.time() % 5 < 0.1:  # Every ~5 seconds
                    try:
                        status = requests.get("http://localhost:8000/simulation/status").json()
                        logger.info(f"System status: {status}")
                    except Exception as e:
                        logger.debug(f"Could not get status: {str(e)}")
                
                time.sleep(1)
            except requests.exceptions.RequestException as e:
                logger.warning(f"Health check failed: {str(e)}")
                time.sleep(1)
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {str(e)}")
                self.shutdown(None, None)

if __name__ == "__main__":
    runner = SystemRunner()
    runner.run()
