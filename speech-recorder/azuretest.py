import azure.cognitiveservices.speech as speechsdk

speech_config = speechsdk.SpeechConfig(subscription="1AuqtBBihDvY4gARgN3Uv8VBxjX7PcwOGVXElhjrSQ5BPG1TEDWKJQQJ99ALACYeBjFXJ3w3AAAAACOGRdLo", region="eastus")
audio_input = speechsdk.audio.AudioConfig(filename=r"C:\Users\staha\Desktop\Fiverr\Abdul K\output.wav")
speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_input)

result = speech_recognizer.recognize_once()
print(result.text if result.reason == speechsdk.ResultReason.RecognizedSpeech else "Failed")


