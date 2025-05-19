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

class SystemRunner:
    def __init__(self):
        self.processes = []
        self.running = True
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

    def run_backend(self):
        """Run the FastAPI backend server"""
        uvicorn.run(app, host="0.0.0.0", port=8000)

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
        frontend = subprocess.Popen(
            ["python", "-m", "http.server", "9000", "--directory", "Frontend"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        self.processes.append(frontend)

    def open_browser(self):
        """Open the frontend in browser"""
        time.sleep(3)
        webbrowser.open("http://localhost:9000/index.html")

    def shutdown(self, signum, frame):
        """Clean shutdown handler"""
        print("\nShutting down system...")
        self.running = False
        for p in self.processes:
            p.terminate()
        sys.exit(0)

    def run(self):
        """Run all system components"""
        # Start frontend HTTP server
        self.run_frontend_server()

        # Start backend in thread
        backend_thread = threading.Thread(target=self.run_backend, daemon=True)
        backend_thread.start()

        # Open browser
        browser_thread = threading.Thread(target=self.open_browser, daemon=True)
        browser_thread.start()

        # Keep main thread alive
        while self.running:
            time.sleep(1)

if __name__ == "__main__":
    runner = SystemRunner()
    runner.run()
