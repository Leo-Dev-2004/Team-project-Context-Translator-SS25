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
        time.sleep(2)
        while self.running:
            try:
                response = requests.get("http://localhost:8000/simulation/start")
                print(f"Simulation started: {response.json()}")
                break
            except Exception as e:
                print(f"Waiting for backend... ({e})")
                time.sleep(1)

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

        # Start simulation in thread
        simulation_thread = threading.Thread(target=self.start_simulation, daemon=True)
        simulation_thread.start()

        # Open browser
        browser_thread = threading.Thread(target=self.open_browser, daemon=True)
        browser_thread.start()

        # Keep main thread alive
        while self.running:
            time.sleep(1)

if __name__ == "__main__":
    runner = SystemRunner()
    runner.run()
