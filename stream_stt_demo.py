import speech_recognition as sr
import time

r = sr.Recognizer()

def callback(recognizer, audio):
    try:
        text = recognizer.recognize_google(audio, language="en-US")
        print("You said:", text)
    except sr.UnknownValueError:
        print("Sorry, could not understand audio.")
    except sr.RequestError as e:
        print(f"Could not request results; {e}")

# Start background listening
print("Starting background listening...")
stop_listening = r.listen_in_background(sr.Microphone(), callback)

# Keep the script running until manually stopped
print("Listening... Press Ctrl+C to stop.")
while True:
    time.sleep(0.1)