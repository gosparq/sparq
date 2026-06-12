function audioRecorder(fieldKey, csrfToken, i18n, transcribeUrl, useServerTranscription) {
    i18n = i18n || {};

    // Closure variables — kept outside Alpine's reactive proxy
    var player = null;
    var recorder = null;
    var stream = null;
    var chunks = [];
    var timer = null;
    var recognition = null;

    return {
        state: 'idle',
        duration: 0,
        audioBlob: null,
        audioUrl: null,
        transcript: '',
        textLocked: false,
        errorMsg: '',
        errorHint: '',
        playbackPct: 0,
        _playbackSec: 0,
        _browserTranscript: '',

        MIN_DURATION: 30,
        MAX_DURATION: 60,

        init() {
            var textarea = document.getElementById(fieldKey);
            if (textarea && textarea.value) {
                this.transcript = textarea.value;
            }
        },

        get durationDisplay() {
            var m = Math.floor(this.duration / 60);
            var s = this.duration % 60;
            return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
        },

        get playbackTime() {
            if (this.state === 'playing') {
                var m = Math.floor(this._playbackSec / 60);
                var s = Math.floor(this._playbackSec % 60);
                return m + ':' + String(s).padStart(2, '0');
            }
            var m = Math.floor(this.duration / 60);
            var s = this.duration % 60;
            return m + ':' + String(s).padStart(2, '0');
        },

        get canStop() {
            return this.duration >= this.MIN_DURATION;
        },

        async startRecording() {
            this.errorMsg = '';
            this.errorHint = '';

            var textarea = document.getElementById(fieldKey);
            if (textarea && textarea.value.trim() && !this.textLocked) {
                if (!confirm(i18n.confirmReplace || 'Recording will replace your text. Continue?')) {
                    return;
                }
            }

            try {
                stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            } catch (e) {
                if (e.name === 'NotFoundError' || e.name === 'DevicesNotFoundError') {
                    this.errorMsg = i18n.micNotFound || 'No microphone found.';
                    this.errorHint = '';
                } else {
                    this.errorMsg = i18n.micDenied || 'Microphone access denied.';
                    this.errorHint = i18n.micDeniedHint || 'Allow microphone access in your browser settings, then try again.';
                }
                return;
            }

            chunks = [];
            var mimeType = this._getMimeType();
            recorder = new MediaRecorder(stream, { mimeType: mimeType });

            recorder.ondataavailable = function(e) {
                if (e.data.size > 0) chunks.push(e.data);
            };

            var self = this;
            recorder.onstop = function() {
                self._onRecordingDone();
            };

            recorder.start(250);
            this.state = 'recording';
            this.duration = 0;
            this.transcript = '';
            this.textLocked = false;
            this._browserTranscript = '';
            this.playbackPct = 0;
            this._playbackSec = 0;

            if (textarea) {
                textarea.readOnly = true;
            }

            if (!useServerTranscription) {
                this._startBrowserTranscription();
            }

            timer = setInterval(function() {
                self.duration++;
                if (self.duration >= self.MAX_DURATION) {
                    self.stopRecording();
                }
            }, 1000);
        },

        stopRecording() {
            this._stopBrowserTranscription();
            if (recorder && recorder.state === 'recording') {
                recorder.stop();
            }
            if (timer) {
                clearInterval(timer);
                timer = null;
            }
            if (stream) {
                stream.getTracks().forEach(function(t) { t.stop(); });
                stream = null;
            }
        },

        rerecord() {
            if (player) {
                player.pause();
                player = null;
            }
            if (this.audioUrl) {
                URL.revokeObjectURL(this.audioUrl);
            }
            this.audioBlob = null;
            this.audioUrl = null;
            this.transcript = '';
            this.textLocked = false;
            this.duration = 0;
            this.state = 'idle';
            this.errorMsg = '';
            this.playbackPct = 0;
            this._playbackSec = 0;

            var textarea = document.getElementById(fieldKey);
            if (textarea) {
                textarea.value = '';
                textarea.readOnly = false;
                textarea.classList.remove('textarea-locked');
            }

            var fileInput = document.getElementById(fieldKey + '_audio');
            if (fileInput) {
                fileInput.value = '';
            }
        },

        togglePlayback() {
            if (!this.audioUrl) return;
            var self = this;

            if (this.state === 'playing') {
                if (player) player.pause();
                this.state = 'recorded';
                return;
            }

            if (!player) {
                player = new Audio(this.audioUrl);
            } else if (player.src !== this.audioUrl) {
                player.src = this.audioUrl;
            }

            player.ontimeupdate = function() {
                self._playbackSec = player.currentTime;
                var dur = self.duration || 1;
                self.playbackPct = Math.min(100, (player.currentTime / dur) * 100);
            };
            player.onended = function() {
                self.state = 'recorded';
                self.playbackPct = 0;
                self._playbackSec = 0;
            };

            player.play().then(function() {
                self.state = 'playing';
            }).catch(function() {
                self.state = 'recorded';
            });
        },

        seekPlayback(event) {
            if (!player || !this.duration) return;
            var wrap = event.currentTarget;
            var rect = wrap.getBoundingClientRect();
            var pct = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
            player.currentTime = pct * this.duration;
        },

        _getMimeType() {
            if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
                return 'audio/webm;codecs=opus';
            }
            if (MediaRecorder.isTypeSupported('audio/webm')) {
                return 'audio/webm';
            }
            if (MediaRecorder.isTypeSupported('audio/mp4')) {
                return 'audio/mp4';
            }
            return '';
        },

        _onRecordingDone() {
            var mimeType = this._getMimeType() || 'audio/webm';
            this.audioBlob = new Blob(chunks, { type: mimeType });
            this.audioUrl = URL.createObjectURL(this.audioBlob);

            player = new Audio(this.audioUrl);

            this._setFileInput();

            if (useServerTranscription) {
                this.state = 'transcribing';
                this._transcribeOnServer();
            } else {
                this._finishBrowserTranscription(this._browserTranscript || '');
            }
        },

        _transcribeOnServer() {
            if (!transcribeUrl || !this.audioBlob) {
                this._finishTranscription('');
                return;
            }

            var ext = this.audioBlob.type.includes('mp4') ? '.mp4' : '.webm';
            var formData = new FormData();
            formData.append('audio', this.audioBlob, 'recording' + ext);

            var self = this;
            fetch(transcribeUrl, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken },
                body: formData,
            })
            .then(function(resp) {
                if (!resp.ok) throw new Error('Transcription request failed');
                return resp.json();
            })
            .then(function(data) {
                self._finishTranscription(data.transcript || '');
            })
            .catch(function() {
                self._finishTranscription('');
            });
        },

        _finishTranscription(text) {
            this.transcript = text;
            this.state = 'recorded';

            var textarea = document.getElementById(fieldKey);
            if (textarea) {
                if (this.transcript.trim()) {
                    textarea.value = this.transcript;
                }
                textarea.readOnly = true;
                textarea.classList.add('textarea-locked');
                this.textLocked = true;
            }
        },

        _startBrowserTranscription() {
            var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) return;

            try {
                recognition = new SpeechRecognition();
                recognition.continuous = true;
                recognition.interimResults = true;
                recognition.lang = document.documentElement.lang || 'en';

                var finalParts = [];
                var self = this;
                recognition.onresult = function(event) {
                    var interim = '';
                    finalParts = [];
                    for (var i = 0; i < event.results.length; i++) {
                        if (event.results[i].isFinal) {
                            finalParts.push(event.results[i][0].transcript);
                        } else {
                            interim += event.results[i][0].transcript;
                        }
                    }
                    self._browserTranscript = finalParts.join(' ') + (interim ? ' ' + interim : '');

                    var textarea = document.getElementById(fieldKey);
                    if (textarea) {
                        textarea.value = self._browserTranscript;
                    }
                };

                recognition.onerror = function() {
                    recognition = null;
                };

                recognition.start();
            } catch (e) {
                recognition = null;
            }
        },

        _stopBrowserTranscription() {
            if (recognition) {
                try { recognition.stop(); } catch (e) {}
                recognition = null;
            }
        },

        _finishBrowserTranscription(text) {
            this.transcript = text;
            this.state = 'recorded';

            var textarea = document.getElementById(fieldKey);
            if (textarea) {
                if (text.trim()) {
                    textarea.value = text;
                }
                textarea.readOnly = false;
                textarea.classList.remove('textarea-locked');
                this.textLocked = false;
            }
        },

        _setFileInput() {
            var fileInput = document.getElementById(fieldKey + '_audio');
            if (!fileInput || !this.audioBlob) return;

            var ext = this.audioBlob.type.includes('mp4') ? '.mp4' : '.webm';
            var file = new File([this.audioBlob], 'standup-audio' + ext, { type: this.audioBlob.type });
            var dt = new DataTransfer();
            dt.items.add(file);
            fileInput.files = dt.files;
        },
    };
}
