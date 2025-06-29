# transcriber.py
import speech_recognition as sr
import json
import sys
import time
import asyncio
import websockets
import functools

# Configuration for WebSocket
WEBSOCKET_URI = "ws://localhost:8000/ws" # Assuming your WebSocket server runs here

# Global WebSocket connection object
websocket_connection = None
reconnect_attempts = 0
MAX_RECONNECT_ATTEMPTS = 10
RECONNECT_DELAY_SEC = 2

async def connect_to_websocket():
    """Connects to the WebSocket server with retry logic."""
    global websocket_connection, reconnect_attempts
    while reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
        try:
            sys.stderr.write(f"Python Transcriber: Attempting to connect to WebSocket: {WEBSOCKET_URI} (Attempt {reconnect_attempts + 1}/{MAX_RECONNECT_ATTEMPTS})\n")
            websocket_connection = await websockets.connect(WEBSOCKET_URI)
            sys.stderr.write("Python Transcriber: WebSocket connected.\n")
            reconnect_attempts = 0 # Reset on successful connection
            return True
        except Exception as e:
            sys.stderr.write(f"Python Transcriber: WebSocket connection failed: {e}. Retrying in {RECONNECT_DELAY_SEC} seconds...\n")
            reconnect_attempts += 1
            await asyncio.sleep(RECONNECT_DELAY_SEC)
    sys.stderr.write("Python Transcriber: Max reconnect attempts reached. Exiting.\n")
    return False

async def send_transcription_over_websocket(data):
    """Sends transcription data over the WebSocket connection."""
    global websocket_connection
    if websocket_connection and websocket_connection.open:
        try:
            await websocket_connection.send(json.dumps(data))
            sys.stderr.write(f"Python Transcriber: Sent transcription via WS: {data['text']}\n")
        except websockets.exceptions.ConnectionClosedOK:
            sys.stderr.write("Python Transcriber: WebSocket closed gracefully during send.\n")
            websocket_connection = None # Mark as closed
        except websockets.exceptions.ConnectionClosedError as e:
            sys.stderr.write(f"Python Transcriber: WebSocket connection error during send: {e}\n")
            websocket_connection = None # Mark as closed
        except Exception as e:
            sys.stderr.write(f"Python Transcriber: Error sending via WebSocket: {e}\n")
            websocket_connection = None # Mark as closed
    else:
        sys.stderr.write("Python Transcriber: WebSocket not connected. Attempting reconnection...\n")
        asyncio.create_task(connect_to_websocket()) # Try to reconnect in the background

def transcribe_audio_sync(websocket_send_func):
    """Synchronous function to handle audio transcription and call async send."""
    r = sr.Recognizer()
    mic = sr.Microphone()

    try:
        with mic as source:
            r.adjust_for_ambient_noise(source)
            sys.stderr.write("Python Transcriber: Listening...\n")

            while True:
                try:
                    audio = r.listen(source, phrase_time_limit=5)
                    sys.stderr.write("Python Transcriber: Transcribing...\n")

                    text = r.recognize_google(audio, language="en-US")
                    
                    clean_text = text.strip()
                    if clean_text:
                        output_data = {
                            "timestamp": time.time(),
                            "text": clean_text
                        }
                        # Call the async WebSocket send function from sync context
                        asyncio.run_coroutine_threadsafe(websocket_send_func(output_data), asyncio.get_event_loop())
                    
                except sr.UnknownValueError:
                    sys.stderr.write("Python Transcriber: Could not understand audio.\n")
                except sr.RequestError as e:
                    sys.stderr.write(f"Python Transcriber: Could not request results from Google Speech Recognition service; {e}\n")
                except Exception as e:
                    sys.stderr.write(f"Python Transcriber: An unexpected error occurred during listening or recognition: {e}\n")
                    time.sleep(1)

    except Exception as e:
        sys.stderr.write(f"Python Transcriber: Failed to open microphone or an initial error occurred: {e}\n")
        sys.exit(1)

async def main():
    """Main async entry point for the transcriber."""
    sys.stderr.write("Python Transcriber: Starting up...\n")
    
    # Establish initial WebSocket connection
    await connect_to_websocket()

    # Use functools.partial to pass the async send function to the sync audio transcriber
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, functools.partial(transcribe_audio_sync, send_transcription_over_websocket))

    # Keep the main loop running to maintain WebSocket connection and handle reconnections
    while True:
        if websocket_connection is None or not websocket_connection.open:
            await connect_to_websocket()
        await asyncio.sleep(1) # Keep event loop active


if __name__ == "__main__":
    asyncio.run(main())
