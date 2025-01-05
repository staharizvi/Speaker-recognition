from flask import Flask, render_template, request, jsonify
from pydub import AudioSegment
import io
import subprocess
from datetime import datetime
import azure.cognitiveservices.speech as speechsdk
import json
import os
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
import logging
from threading import Lock
from functools import wraps
from time import time
from collections import deque


# Add rate limiting to work within free tier limits
def rate_limit(max_requests: int, time_window: float):
    requests = deque()
    lock = Lock()

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            with lock:
                now = time()
                while requests and requests[0] < now - time_window:
                    requests.popleft()

                if len(requests) >= max_requests:
                    return jsonify({
                        'error': 'Rate limit exceeded. Please wait before sending more audio.'
                    }), 429

                requests.append(now)
            return f(*args, **kwargs)
        return wrapped
    return decorator


@dataclass
class Speaker:
    name: str
    voice_profile_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None


@dataclass
class TranscriptEntry:
    timestamp: float
    text: str
    speaker: Optional[str]


class SpeakerRecognitionSystem:
    def __init__(self, speech_key: str, service_region: str):
        self.speech_key = speech_key
        self.service_region = service_region
        self.audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
        self.speakers: Dict[str, Speaker] = {}
        self.transcript: List[TranscriptEntry] = []
        self.speech_config = speechsdk.SpeechConfig(
            subscription=speech_key,
            region=service_region
        )
        self.speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm
        )

    def create_speaker_profile(self):
        try:
            client = speechsdk.VoiceProfileClient(self.speech_config)
            result = client.create_profile(speechsdk.VoiceProfileType.TextIndependentIdentification, locale="en-us")
            if result.reason == speechsdk.ResultReason.CreatedVoiceProfile:
                return result.voice_profile_id
            else:
                logging.error("Failed to create voice profile: %s", result)
                return None
        except Exception as e:
            logging.error(f"Error creating speaker profile: {str(e)}")
            raise

    def enroll_speaker(self, audio_stream: bytes, name: str) -> bool:
        try:
            if len(self.speakers) >= 50:
                logging.warning("Maximum speaker limit reached for free tier")
                return False

            profile_id = self.create_speaker_profile()
            if not profile_id:
                return False

            client = speechsdk.VoiceProfileClient(self.speech_config)
            stream = speechsdk.audio.PushAudioInputStream()
            stream.write(audio_stream)
            audio_config = speechsdk.audio.AudioConfig(stream=stream)

            enrollment_result = client.enroll_profile(speechsdk.EnrollmentConfig(profile_id, audio_config))

            if enrollment_result.reason == speechsdk.ResultReason.EnrolledVoiceProfile:
                first_name, last_name = name.split(' ', 1)
                speaker = Speaker(
                    name=name,
                    voice_profile_id=profile_id,
                    first_name=first_name,
                    last_name=last_name
                )
                self.speakers[profile_id] = speaker
                return True
            return False
        except Exception as e:
            logging.error(f"Error enrolling speaker: {str(e)}")
            return False

    def identify_speaker(self, audio_stream: bytes) -> Optional[Speaker]:
        try:
            stream = speechsdk.audio.PushAudioInputStream()
            stream.write(audio_stream)
            audio_config = speechsdk.audio.AudioConfig(stream=stream)

            recognizer = speechsdk.SpeakerRecognizer(self.speech_config, audio_config)

            profile_ids = [speaker.voice_profile_id for speaker in self.speakers.values()]
            model = speechsdk.SpeakerIdentificationModel(profile_ids)

            result = recognizer.recognize_speaker_async(model).get()

            if result.reason == speechsdk.ResultReason.RecognizedSpeaker:
                return self.speakers.get(result.profile_id)
            return None
        except Exception as e:
            logging.error(f"Error identifying speaker: {str(e)}")
            return None

    def transcribe_audio(self, audio_stream: bytes) -> Optional[str]:
        try:
            stream = speechsdk.audio.PushAudioInputStream()
            stream.write(audio_stream)
            audio_config = speechsdk.audio.AudioConfig(stream=stream)
            speech_recognizer = speechsdk.SpeechRecognizer(self.speech_config, audio_config)

            result = speech_recognizer.recognize_once_async().get()

            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                return result.text
            return None
        except Exception as e:
            logging.error(f"Error transcribing audio: {str(e)}")
            return None

    def add_transcript_entry(self, text: str, speaker_name: Optional[str] = None):
        entry = TranscriptEntry(
            timestamp=datetime.now().timestamp(),
            text=text,
            speaker=speaker_name
        )
        self.transcript.append(entry)

    def get_formatted_transcript(self) -> List[Dict]:
        formatted_entries = []
        for entry in self.transcript:
            formatted_entry = {
                'timestamp': datetime.fromtimestamp(entry.timestamp).strftime('%H:%M:%S'),
                'text': entry.text,
                'speaker': entry.speaker if entry.speaker else 'Not recognized'
            }
            formatted_entries.append(formatted_entry)
        return formatted_entries


# Flask application setup
app = Flask(__name__)

# Initialize logging
logging.basicConfig(level=logging.INFO)

# Initialize the speaker recognition system
AZURE_SPEECH_KEY = '1AuqtBBihDvY4gARgN3Uv8VBxjX7PcwOGVXElhjrSQ5BPG1TEDWKJQQJ99ALACYeBjFXJ3w3AAAAACOGRdLo'
AZURE_SPEECH_REGION = 'eastus'
speaker_system = SpeakerRecognitionSystem(AZURE_SPEECH_KEY, AZURE_SPEECH_REGION)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'wav'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/start-recording', methods=['POST'])
def start_recording():
    return jsonify({'status': 'success', 'message': 'Recording started'})


@app.route('/api/stop-recording', methods=['POST'])
def stop_recording():
    return jsonify({'status': 'success', 'message': 'Recording stopped'})


@app.route('/api/process-audio', methods=['POST'])
def process_audio():
    try:
        # Check if the audio is in the form data
        if 'audio' not in request.files:
            logging.error("No audio file found in request.")
            return jsonify({'error': 'No audio file found'}), 400

        audio_file = request.files['audio']
        
        # Log the size of the received file
        logging.info(f"Received audio file: {audio_file.filename} of size {len(audio_file.read())} bytes")
        
        # Rewind to the start after reading file size
        audio_file.seek(0)

        # Check if the file is a WAV file
        if not audio_file.filename.lower().endswith('.wav'):
            logging.error("Invalid file format. Only WAV files are accepted.")
            return jsonify({'error': 'Invalid file format. Only WAV files are accepted.'}), 400
        
        # Process the audio file (no need for conversion)
        audio_data = audio_file.read()  # Read the audio data

        # Log the size of the received data
        logging.info(f"Received audio data of size: {len(audio_data)} bytes")

        if not audio_data:
            logging.error("No audio data received.")
            return jsonify({'error': 'No audio data received'}), 400

        # Process the audio data (example of handling the raw bytes)
        text = speaker_system.transcribe_audio(audio_data)
        if not text:
            logging.error("Failed to transcribe audio.")
            return jsonify({'error': 'Failed to transcribe audio'}), 400

        speaker = speaker_system.identify_speaker(audio_data)
        speaker_name = speaker.name if speaker else "Unknown"

        # Update the transcript
        speaker_system.add_transcript_entry(text, speaker_name)

        # Return the formatted transcript
        return jsonify({
            'status': 'success',
            'transcript': speaker_system.get_formatted_transcript()
        })

    except Exception as e:
        logging.error(f"Error processing audio: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    app.run(debug=True)
