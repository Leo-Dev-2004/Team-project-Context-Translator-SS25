import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from Backend.backend import app
    print("✅ Successfully imported Backend.backend")
    print(f"App instance: {app}")
except ImportError as e:
    print("❌ Failed to import Backend.backend")
    print(f"Error: {e}")
    print("\nCurrent Python path:")
    for p in sys.path:
        print(f"- {p}")
