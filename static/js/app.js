let mediaRecorder;
let audioContext;
let audioStream;
let isRecording = false;

const startButton = document.getElementById('startButton');
const stopButton = document.getElementById('stopButton');
const recordingStatus = document.getElementById('recordingStatus');
const transcript = document.getElementById('transcript');

startButton.addEventListener('click', startRecording);
stopButton.addEventListener('click', stopRecording);

async function initAudioContext() {
    try {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const stream = await navigator.mediaDevices.getUserMedia({ 
            audio: {
                channelCount: 1,
                sampleRate: 16000,
                sampleSize: 16
            } 
        });
        audioStream = stream;
        return true;
    } catch (error) {
        console.error('Error initializing audio:', error);
        return false;
    }
}

async function startRecording() {
    try {
        if (!audioContext) {
            const initialized = await initAudioContext();
            if (!initialized) {
                throw new Error('Could not initialize audio context');
            }
        }

        mediaRecorder = new MediaRecorder(audioStream, {
            mimeType: 'audio/webm;codecs=opus',
            audioBitsPerSecond: 16000
        });

        mediaRecorder.ondataavailable = async (event) => {
            if (event.data.size > 0) {
                // Log the size of the audio data
                console.log('Captured audio data size:', event.data.size);
                
                const arrayBuffer = await event.data.arrayBuffer();
                console.log('Sending audio data with size:', arrayBuffer.byteLength);  // Log the size
                
                const formData = new FormData();
                formData.append('audio', new Blob([arrayBuffer], { type: 'audio/webm' }));

                await processAudioChunk(formData);
            }
        };

        mediaRecorder.start(1000); // Capture in 1-second intervals
        isRecording = true;
        updateUIRecordingStarted();
    } catch (error) {
        console.error('Error starting recording:', error);
        alert('Could not access microphone. Please ensure you have granted permission.');
    }
}

function stopRecording() {
    if (mediaRecorder && isRecording) {
        mediaRecorder.stop();
        isRecording = false;
        updateUIRecordingStopped();
    }
}

function updateUIRecordingStarted() {
    startButton.disabled = true;
    stopButton.disabled = false;
    recordingStatus.textContent = 'Recording in progress...';
    recordingStatus.classList.add('recording-active');
}

function updateUIRecordingStopped() {
    startButton.disabled = false;
    stopButton.disabled = true;
    recordingStatus.textContent = 'Recording stopped';
    recordingStatus.classList.remove('recording-active');
}

async function processAudioChunk(formData) {
    try {
        const response = await fetch('/api/process-audio', {
            method: 'POST',
            body: formData, // Send audio data as form data
        });

        const data = await response.json();
        if (data.status === 'success') {
            updateTranscript(data.transcript);
        } else {
            console.error('Error:', data.error);
        }
    } catch (error) {
        console.error('Error processing audio:', error);
    }
}

function updateTranscript(newEntries) {
    const fragment = document.createDocumentFragment();

    newEntries.forEach(entry => {
        const div = document.createElement('div');
        div.classList.add('speaker-entry');
        div.innerHTML = `
            <span class="timestamp">${entry.timestamp}</span>
            <span class="speaker-name">${entry.speaker}:</span>
            <span class="speaker-text">${entry.text}</span>
        `;
        fragment.appendChild(div);
    });

    transcript.appendChild(fragment);
    transcript.scrollTop = transcript.scrollHeight; // Auto-scroll to bottom
}
