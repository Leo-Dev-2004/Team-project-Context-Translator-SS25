import sys
import os
from pathlib import Path

# Get absolute path to project root (Documents/Coding/Teamprojekt Context Translator)
project_root = Path(__file__).parent.parent
project_path = str(project_root)
print(f"Project path: {project_path}")  # Verify correct path

# Add project root to Python path if not already there
if project_path not in sys.path:
    sys.path.insert(0, project_path)

print(f"Project root: {project_path}")
print("Python path:")
for p in sys.path:
    print(f"- {p}")

try:
    from Backend.backend import app
    print("\n✅ Successfully imported Backend.backend")
    print(f"App instance: {app}")
except ImportError as e:
    print(f"\n❌ Failed to import Backend.backend: {e}")
    print("\nChecking Backend directory contents:")
    backend_dir = os.path.join(project_path, "Backend")
    if os.path.exists(backend_dir):
        print(f"Contents of {backend_dir}:")
        for f in os.listdir(backend_dir):
            print(f"- {f}")
    else:
        print(f"Directory not found: {backend_dir}")
