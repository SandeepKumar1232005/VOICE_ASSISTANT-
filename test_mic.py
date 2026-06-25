import speech_recognition as sr
import traceback

r = sr.Recognizer()
try:
    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source, duration=1)
        print("Listening for 5 seconds...")
        audio = r.listen(source, timeout=5, phrase_time_limit=5)
        print("Got audio, recognizing...")
        try:
            text = r.recognize_google(audio)
            print(f"Recognized (Google): {text}")
        except sr.UnknownValueError:
            print("Google could not understand audio")
        except sr.RequestError as e:
            print(f"Google error: {e}")
except Exception as e:
    print("General Exception:")
    traceback.print_exc()
