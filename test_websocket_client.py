import asyncio
import sys
from pathlib import Path
from httpx import AsyncClient

# Add project root to Python path (Documents/Coding/Teamprojekt Context Translator)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
print(f"Project path: {sys.path[0]}")  # Verify correct path

try:
    from Backend.backend import app
    print("Successfully imported Backend.backend")
except ImportError as e:
    print(f"Import error: {e}")
    print("Current Python path:")
    print(sys.path)
    raise

async def test_websocket():
    async with AsyncClient(app=app, base_url="http://test") as client:
        async with client.websocket_connect("/ws") as websocket:
            test_msg = {"test": "data"}
            await websocket.send_json(test_msg)
            response = await websocket.receive_json()
            print("Received:", response)

if __name__ == "__main__":
    asyncio.run(test_websocket())
