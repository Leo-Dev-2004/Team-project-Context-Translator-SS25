import subprocess
import threading
import time
import webbrowser
from fastapi import FastAPI
import uvicorn
from Backend.backend import app, start_simulation
import requests

def run_backend():
    """Run the FastAPI backend server"""
    uvicorn.run(app, host="0.0.0.0", port=8000)

def start_simulation_thread():
    """Start the simulation after server is ready"""
    time.sleep(2)  # Wait for server to start
    try:
        response = requests.get("http://localhost:8000/simulation/start")
        print(f"Simulation started: {response.json()}")
    except Exception as e:
        print(f"Failed to start simulation: {e}")

def open_frontend():
    """Open the frontend in browser"""
    time.sleep(3)  # Wait for backend to be ready
    webbrowser.open("http://localhost:9000/Frontend/index.html")

if __name__ == "__main__":
    # Start backend server in a thread
    backend_thread = threading.Thread(target=run_backend, daemon=True)
    backend_thread.start()

    # Start simulation in another thread
    simulation_thread = threading.Thread(target=start_simulation_thread, daemon=True)
    simulation_thread.start()

    # Open frontend
    frontend_thread = threading.Thread(target=open_frontend, daemon=True)
    frontend_thread.start()

    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down system...")
