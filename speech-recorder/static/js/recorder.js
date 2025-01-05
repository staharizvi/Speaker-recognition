let audioContext;
let recorder;
let audioStream;
let isRecording = false;

const startButton = document.getElementById('startRecord');
const stopButton = document.getElementById('stopRecord');
const recordingStatus = document.getElementById('recordingStatus');
const transcript = document.getElementById('transcriptionResults');

startButton.addEventListener('click', startRecording);
stopButton.addEventListener('click', stopRecording);

async function initAudioContext() {
    try {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                channelCount: 1,
                sampleRate: 16000
            }
        });
        audioStream = stream;
        console.log('Audio Stream initialized:', audioStream); // Log to verify the stream
        return true;
    } catch (error) {
        console.error('Error initializing audio context:', error);
        alert('Could not access microphone. Please ensure you have granted permission.');
        return false;
    }
}


async function startRecording() {
    try {
        // Ensure audioContext and stream are initialized
        if (!audioContext) {
            const initialized = await initAudioContext();
            if (!initialized) {
                throw new Error('Could not initialize audio context');
            }
        }

        // Ensure audioStream is available
        console.log('Audio Stream:', audioStream);
        if (!audioStream) {
            throw new Error('Audio stream is not available');
        }

        // Check if MediaRecorder is supported
        if (!window.MediaRecorder) {
            throw new Error('MediaRecorder is not supported by this browser');
        }

        // Initialize MediaRecorder
        mediaRecorder = new MediaRecorder(audioStream, {
            mimeType: 'audio/webm;codecs=opus',
            audioBitsPerSecond: 16000
        });

        // Check if mediaRecorder is initialized
        if (!mediaRecorder) {
            throw new Error('Failed to initialize MediaRecorder');
        }

        console.log('MediaRecorder initialized:', mediaRecorder);

        mediaRecorder.ondataavailable = async (event) => {
            if (event.data.size > 0) {
                // Log the size of the audio data
                console.log('Captured audio data size:', event.data.size);
        
                const arrayBuffer = await event.data.arrayBuffer();
                console.log('Sending audio data with size:', arrayBuffer.byteLength);  // Log the size
        
                const formData = new FormData();
                formData.append('audio', new Blob([arrayBuffer], { type: 'audio/wav' }));
        
                // Call the function to send the data
                await processAudioChunk(formData);
            }
        };
        

        // Start the recording process
        mediaRecorder.start(1000); // Capture in 1-second intervals
        isRecording = true;
        updateUIRecordingStarted();
    } catch (error) {
        console.error('Error starting recording:', error);
        alert('Could not access microphone. Please ensure you have granted permission.');
    }
}


function stopRecording() {
    try {
        // Check if mediaRecorder is initialized and recording
        if (mediaRecorder && isRecording) {
            // Stop the recording
            mediaRecorder.stop();
            console.log('Recording stopped.');
            isRecording = false;

            // Update UI state
            updateUIRecordingStopped();
        } else {
            console.log('MediaRecorder not initialized or already stopped.');
        }
    } catch (error) {
        console.error('Error stopping recording:', error);
        alert('An error occurred while stopping the recording.');
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
