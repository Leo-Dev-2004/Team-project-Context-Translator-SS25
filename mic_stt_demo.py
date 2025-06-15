import speech_recognition as sr

r = sr.Recognizer()
with sr.Microphone() as source:
    print("Start speaking...")
    audio = r.listen(source)

try:
    text = r.recognize_google(audio, language="en-US")
    print("You said: " + text)
except sr.UnknownValueError:
    print("Sorry, could not understand the audio.")
except sr.RequestError as e:
    print(f"Could not request results from Google Speech Recognition service; {e}")