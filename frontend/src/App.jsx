import { useEffect, useMemo, useRef, useState } from "react";

const API = "/api";
const BOUNDARY_PAUSE_MS = {
  sentence: 10,
  list_item: 100,
  paragraph: 100,
  page: 200,
  section: 250,
};
const VOICE_SILENCE_MS = 300;
const MAX_VOICE_RECORDING_MS = 6000;

const Icon = ({ name, size = 20 }) => {
  const paths = {
    upload: <><path d="M12 16V4"/><path d="m7 9 5-5 5 5"/><path d="M5 20h14"/></>,
    play: <path d="m8 5 11 7-11 7Z" fill="currentColor" stroke="none" />,
    pause: <><path d="M9 5v14"/><path d="M15 5v14"/></>,
    stop: <rect x="6" y="6" width="12" height="12" rx="1" fill="currentColor" stroke="none" />,
    next: <><path d="m7 5 9 7-9 7Z" fill="currentColor" stroke="none"/><path d="M18 5v14"/></>,
    mic: <><rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0"/><path d="M12 17.5V21"/><path d="M9 21h6"/></>,
    minus: <path d="M5 12h14"/>,
    plus: <><path d="M5 12h14"/><path d="M12 5v14"/></>,
    file: <><path d="M7 3h7l4 4v14H7Z"/><path d="M14 3v5h5"/></>,
    close: <><path d="m6 6 12 12"/><path d="m18 6-12 12"/></>,
  };
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
};

async function api(path, options) {
  const response = await fetch(`${API}${path}`, options);
  if (!response.ok) {
    let message = "Something went wrong.";
    try {
      const payload = await response.json();
      message = payload.detail || message;
    } catch { /* Use the readable fallback. */ }
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return response;
}

export default function App() {
  const [document, setDocument] = useState(null);
  const [navigation, setNavigation] = useState(null);
  const [activeSentenceId, setActiveSentenceId] = useState(null);
  const [source, setSource] = useState(null);
  const [phase, setPhase] = useState("empty");
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [voiceFeedback, setVoiceFeedback] = useState("");
  const [microphoneEnabled, setMicrophoneEnabled] = useState(false);
  const [microphoneStarting, setMicrophoneStarting] = useState(false);
  const [voiceProcessing, setVoiceProcessing] = useState(false);
  const phaseRef = useRef(phase);
  phaseRef.current = phase;
  const fileInput = useRef(null);
  const audio = useRef(new Audio());
  const audioUrl = useRef(null);
  const sourceUrl = useRef(null);
  const currentAudio = useRef(null);
  const playbackVersion = useRef(0);
  const completionInFlight = useRef(false);
  const transcript = useRef(null);
  const sentenceElements = useRef(new Map());
  const mediaRecorder = useRef(null);
  const microphoneStream = useRef(null);
  const recordedChunks = useRef([]);
  const recordingTimer = useRef(null);
  const microphoneEnabledRef = useRef(false);
  const microphonePreference = useRef(null);
  const voiceQueue = useRef([]);
  const voiceRequestInFlight = useRef(false);
  const voiceAbortController = useRef(null);
  const inputAnalyser = useRef(null);
  const inputAudioContext = useRef(null);
  const inputMonitorFrame = useRef(null);
  const recordingHadSpeech = useRef(false);
  const recordingStartedAt = useRef(0);
  const lastVoiceAt = useRef(0);
  const fallbackRecording = useRef(false);
  const voiceInterruption = useRef(null);
  const voicePauseRequest = useRef(null);

  const sentences = useMemo(() => document?.sections.flatMap((section) => section.sentences) ?? [], [document]);
  const sentenceById = useMemo(
    () => new Map(sentences.map((sentence) => [sentence.id, sentence])),
    [sentences],
  );
  const sentenceByIdRef = useRef(sentenceById);
  sentenceByIdRef.current = sentenceById;
  const foundIndex = sentences.findIndex((sentence) => sentence.id === activeSentenceId);
  const activeSentence = foundIndex >= 0 ? sentences[foundIndex] : null;
  const progress = navigation?.document_completed
    ? 100
    : sentences.length && foundIndex >= 0
      ? Math.round(((foundIndex + 1) / sentences.length) * 100)
      : 0;

  useEffect(() => {
    const container = transcript.current;
    const sentence = sentenceElements.current.get(activeSentenceId);
    if (!container || !sentence) return;

    const containerBox = container.getBoundingClientRect();
    const sentenceBox = sentence.getBoundingClientRect();
    const top = container.scrollTop + sentenceBox.top - containerBox.top
      - (container.clientHeight - sentenceBox.height) / 2;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    container.scrollTo({ top: Math.max(0, top), behavior: reducedMotion ? "auto" : "smooth" });
  }, [activeSentenceId]);

  useEffect(() => {
    const player = audio.current;
    const finish = () => { void completeNaturalPlayback(); };
    const fail = () => { setPhase("ready"); setError("The generated audio could not be played."); };
    player.addEventListener("ended", finish);
    player.addEventListener("error", fail);
    return () => {
      player.removeEventListener("ended", finish);
      player.removeEventListener("error", fail);
      playbackVersion.current += 1;
      player.pause();
      stopContinuousListening(false);
      if (audioUrl.current) URL.revokeObjectURL(audioUrl.current);
      if (sourceUrl.current) URL.revokeObjectURL(sourceUrl.current);
    };
  }, []);

  function clearLocalAudio() {
    const player = audio.current;
    player.pause();
    player.currentTime = 0;
    player.removeAttribute("src");
    if (audioUrl.current) {
      URL.revokeObjectURL(audioUrl.current);
      audioUrl.current = null;
    }
  }

  function interruptLocalAudio() {
    playbackVersion.current += 1;
    currentAudio.current = null;
    clearLocalAudio();
    return playbackVersion.current;
  }

  function releaseMicrophone() {
    if (recordingTimer.current) {
      window.clearTimeout(recordingTimer.current);
      recordingTimer.current = null;
    }
    microphoneStream.current?.getTracks().forEach((track) => track.stop());
    microphoneStream.current = null;
    if (inputMonitorFrame.current) {
      window.cancelAnimationFrame(inputMonitorFrame.current);
      inputMonitorFrame.current = null;
    }
    inputAnalyser.current = null;
    if (inputAudioContext.current) {
      void inputAudioContext.current.close();
      inputAudioContext.current = null;
    }
  }

  function stopContinuousListening(rememberPreference = true) {
    const shouldRestorePlayback = rememberPreference && Boolean(voiceInterruption.current);
    microphoneEnabledRef.current = false;
    if (rememberPreference) microphonePreference.current = false;
    setMicrophoneEnabled(false);
    setMicrophoneStarting(false);
    setVoiceProcessing(false);
    voiceQueue.current = [];
    voiceAbortController.current?.abort();
    voiceAbortController.current = null;
    if (!rememberPreference) {
      voiceInterruption.current = null;
      voicePauseRequest.current = null;
    }
    const recorder = mediaRecorder.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.onstop = null;
      recorder.stop();
    }
    mediaRecorder.current = null;
    recordedChunks.current = [];
    releaseMicrophone();
    if (shouldRestorePlayback) void restoreAfterIgnoredSpeech();
  }

  function pauseForDetectedSpeech() {
    if (voiceInterruption.current) return;
    const previousPhase = phaseRef.current;
    const wasPlaying = previousPhase === "playing";
    voiceInterruption.current = { previousPhase, wasPlaying };
    if (!wasPlaying) {
      voicePauseRequest.current = Promise.resolve();
      return;
    }

    // Stop audible output immediately; the API call synchronizes backend state
    // while the current recording finishes and Whisper transcribes it.
    playbackVersion.current += 1;
    audio.current.pause();
    phaseRef.current = "voice-interrupted";
    setPhase("voice-interrupted");
    voicePauseRequest.current = api("/playback/pause", { method: "POST" })
      .then((response) => response.json())
      .then((nextState) => setNavigation(nextState));
  }

  async function restoreAfterIgnoredSpeech() {
    const interruption = voiceInterruption.current;
    voiceInterruption.current = null;
    const pauseRequest = voicePauseRequest.current;
    voicePauseRequest.current = null;
    try { await pauseRequest; } catch { /* A resume request below re-synchronizes state. */ }

    if (!interruption?.wasPlaying) {
      const restoredPhase = interruption?.previousPhase ?? (document ? "ready" : "empty");
      phaseRef.current = restoredPhase;
      setPhase(restoredPhase);
      return;
    }

    try {
      const response = await api("/playback/resume", { method: "POST" });
      const nextState = await response.json();
      setNavigation(nextState);
      setActiveSentenceId(nextState.current_sentence_id);
      if (audio.current.src && currentAudio.current?.sentenceId === nextState.current_sentence_id) {
        await audio.current.play();
        phaseRef.current = "playing";
        setPhase("playing");
      } else if (nextState.request_id != null) {
        await fetchAndPlayAudio(nextState, playbackVersion.current);
      } else {
        phaseRef.current = "ready";
        setPhase("ready");
      }
    } catch (recoveryError) {
      phaseRef.current = "ready";
      setPhase("ready");
      setError(`Playback could not resume after listening: ${recoveryError.message}`);
    }
  }

  function finishRecordingWindow() {
    const recorder = mediaRecorder.current;
    if (!recorder || recorder.state === "inactive") return;
    if (recordingTimer.current) {
      window.clearTimeout(recordingTimer.current);
      recordingTimer.current = null;
    }
    recorder.stop();
  }

  async function applyVoiceCommand(payload) {
    voiceInterruption.current = null;
    voicePauseRequest.current = null;
    setVoiceFeedback(`Heard “${payload.transcript}”`);
    setNavigation(payload.state);
    setActiveSentenceId(payload.state.current_sentence_id);

    if (payload.intent === "PAUSE") {
      playbackVersion.current += 1;
      audio.current.pause();
      setPhase("paused");
      return;
    }
    if (payload.intent === "STOP") {
      interruptLocalAudio();
      setPhase("ready");
      return;
    }
    if (
      payload.intent === "RESUME"
      && audio.current.src
      && currentAudio.current?.sentenceId === payload.state.current_sentence_id
    ) {
      await audio.current.play();
      setPhase("playing");
      return;
    }

    const expectedVersion = interruptLocalAudio();
    if (payload.request_id == null) {
      setPhase("ready");
      return;
    }
    setPhase("loading-audio");
    await fetchAndPlayAudio({ ...payload.state, request_id: payload.request_id }, expectedVersion);
  }

  async function processVoiceQueue() {
    if (voiceRequestInFlight.current || !microphoneEnabledRef.current || !voiceQueue.current.length) return;
    const blob = voiceQueue.current.shift();
    voiceRequestInFlight.current = true;
    setVoiceProcessing(true);
    const requestController = new AbortController();
    voiceAbortController.current = requestController;
    const extension = blob.type.includes("mp4") ? "m4a" : blob.type.includes("ogg") ? "ogg" : "webm";
    const form = new FormData();
    form.append("audio", blob, `command.${extension}`);
    try {
      await voicePauseRequest.current;
      const response = await api("/command/voice", { method: "POST", body: form, signal: requestController.signal });
      const payload = await response.json();
      if (!microphoneEnabledRef.current || requestController.signal.aborted) return;
      voiceQueue.current = [];
      await applyVoiceCommand(payload);
    } catch (voiceError) {
      if (voiceError.name === "AbortError") return;
      // Silence and ordinary speech are expected while continuously listening.
      await restoreAfterIgnoredSpeech();
      if (voiceError.status !== 422) {
        setError(voiceError.message);
        if (voiceError.status === 503) stopContinuousListening(false);
      }
    } finally {
      if (voiceAbortController.current === requestController) voiceAbortController.current = null;
      voiceRequestInFlight.current = false;
      setVoiceProcessing(false);
      if (microphoneEnabledRef.current && voiceQueue.current.length) void processVoiceQueue();
    }
  }

  function monitorMicrophoneInput() {
    if (!microphoneEnabledRef.current || !inputAnalyser.current) return;
    const samples = new Uint8Array(inputAnalyser.current.fftSize);
    inputAnalyser.current.getByteTimeDomainData(samples);
    let energy = 0;
    for (const sample of samples) {
      const amplitude = (sample - 128) / 128;
      energy += amplitude * amplitude;
    }
    const now = performance.now();
    if (Math.sqrt(energy / samples.length) > 0.018) {
      recordingHadSpeech.current = true;
      lastVoiceAt.current = now;
      if (!mediaRecorder.current) {
        pauseForDetectedSpeech();
        startRecordingWindow(false);
      }
    } else if (
      mediaRecorder.current
      && recordingHadSpeech.current
      && now - lastVoiceAt.current >= VOICE_SILENCE_MS
    ) {
      finishRecordingWindow();
    }
    inputMonitorFrame.current = window.requestAnimationFrame(monitorMicrophoneInput);
  }

  function startRecordingWindow(useFallback = false) {
    const stream = microphoneStream.current;
    if (!microphoneEnabledRef.current || !stream?.active || mediaRecorder.current) return;
    const preferredType = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"]
      .find((type) => MediaRecorder.isTypeSupported(type));
    const recorder = preferredType ? new MediaRecorder(stream, { mimeType: preferredType }) : new MediaRecorder(stream);
    mediaRecorder.current = recorder;
    recordedChunks.current = [];
    fallbackRecording.current = useFallback;
    recordingHadSpeech.current = true;
    recordingStartedAt.current = performance.now();
    lastVoiceAt.current = recordingStartedAt.current;
    recorder.ondataavailable = (event) => {
      if (event.data.size) recordedChunks.current.push(event.data);
    };
    recorder.onstop = () => {
      const hadSpeech = recordingHadSpeech.current;
      const recording = new Blob(recordedChunks.current, { type: recorder.mimeType || "audio/webm" });
      recordedChunks.current = [];
      mediaRecorder.current = null;
      if (!microphoneEnabledRef.current) return;
      if (fallbackRecording.current) startRecordingWindow(true);
      if (hadSpeech && recording.size) {
        voiceQueue.current.push(recording);
        if (voiceQueue.current.length > 3) voiceQueue.current.shift();
        void processVoiceQueue();
      }
    };
    recorder.start();
    recordingTimer.current = window.setTimeout(
      finishRecordingWindow,
      useFallback ? 2400 : MAX_VOICE_RECORDING_MS,
    );
  }

  async function startContinuousListening() {
    if (microphoneEnabledRef.current || microphoneStarting) return;
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setError("Microphone recording is not supported in this browser.");
      return;
    }

    microphonePreference.current = true;
    setMicrophoneStarting(true);
    setError("");
    setVoiceFeedback("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      microphoneStream.current = stream;
      microphoneEnabledRef.current = true;
      setMicrophoneEnabled(true);
      setMicrophoneStarting(false);
      try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (AudioContext) {
          inputAudioContext.current = new AudioContext();
          const sourceNode = inputAudioContext.current.createMediaStreamSource(stream);
          inputAnalyser.current = inputAudioContext.current.createAnalyser();
          inputAnalyser.current.fftSize = 512;
          sourceNode.connect(inputAnalyser.current);
          monitorMicrophoneInput();
        }
      } catch { /* Recording still works if input-level detection is unavailable. */ }
      if (!inputAnalyser.current) startRecordingWindow(true);
    } catch (microphoneError) {
      stopContinuousListening(false);
      microphonePreference.current = false;
      const message = microphoneError?.name === "NotAllowedError"
        ? "Microphone permission was denied. Allow microphone access and try again."
        : `The microphone could not start: ${microphoneError.message}`;
      setError(message);
    }
  }

  async function uploadFile(file) {
    if (!file) return;
    const extension = file.name.split(".").pop()?.toLowerCase();
    if (!extension || !["pdf", "txt", "md"].includes(extension)) {
      setError("Choose a PDF, TXT, or Markdown file.");
      return;
    }
    setError("");
    setVoiceFeedback("");
    setPhase("uploading");
    const restartVoiceControl = microphonePreference.current !== false;
    stopContinuousListening(false);
    interruptLocalAudio();
    const form = new FormData();
    form.append("file", file);
    try {
      const response = await api("/documents/upload", { method: "POST", body: form });
      const nextDocument = await response.json();
      if (sourceUrl.current) {
        URL.revokeObjectURL(sourceUrl.current);
        sourceUrl.current = null;
      }
      if (extension === "pdf") {
        sourceUrl.current = URL.createObjectURL(file);
        setSource({ type: "pdf", url: sourceUrl.current });
      } else {
        setSource({ type: "text", text: await file.text() });
      }
      setDocument(nextDocument);
      const firstSentence = nextDocument.sections.flatMap((section) => section.sentences)[0];
      setActiveSentenceId(firstSentence?.id ?? null);
      const stateResponse = await api("/playback/state");
      setNavigation(await stateResponse.json());
      setPhase("ready");
      if (restartVoiceControl) void startContinuousListening();
    } catch (uploadError) {
      setPhase("empty");
      setError(uploadError.message);
    }
  }

  async function fetchAndPlayAudio(playbackState, expectedVersion = playbackVersion.current) {
    const sentenceId = playbackState?.current_sentence_id;
    const requestId = playbackState?.request_id;
    if (!sentenceId || requestId == null) throw new Error("The server did not identify the generated audio.");
    const response = await api(`/playback/audio?t=${Date.now()}`);
    const blob = await response.blob();
    if (!blob.size) throw new Error("Rime returned an empty audio file.");
    if (expectedVersion !== playbackVersion.current) return false;
    clearLocalAudio();
    audioUrl.current = URL.createObjectURL(blob);
    currentAudio.current = { sentenceId, requestId };
    audio.current.src = audioUrl.current;
    await audio.current.play();
    if (expectedVersion !== playbackVersion.current) return false;
    setPhase("playing");
    return true;
  }

  async function completeNaturalPlayback() {
    const completed = currentAudio.current;
    if (!completed || completionInFlight.current) return;

    const expectedVersion = playbackVersion.current;
    currentAudio.current = null;
    completionInFlight.current = true;
    setPhase("loading-audio");
    try {
      const response = await api("/playback/complete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sentence_id: completed.sentenceId,
          request_id: completed.requestId,
        }),
      });
      const nextState = await response.json();
      if (expectedVersion !== playbackVersion.current) return;

      setNavigation(nextState);
      setActiveSentenceId(nextState.current_sentence_id);
      if (nextState.document_completed || nextState.current_sentence_id === completed.sentenceId || nextState.request_id == null) {
        clearLocalAudio();
        setPhase("ready");
        return;
      }
      const nextSentence = sentenceByIdRef.current.get(nextState.current_sentence_id);
      const transitionPause = BOUNDARY_PAUSE_MS[nextSentence?.boundary_before] ?? 0;
      if (transitionPause) {
        await new Promise((resolve) => window.setTimeout(resolve, transitionPause));
        if (expectedVersion !== playbackVersion.current) return;
      }
      await fetchAndPlayAudio(nextState, expectedVersion);
    } catch (completionError) {
      if (expectedVersion === playbackVersion.current) {
        setPhase("ready");
        setError(completionError.message);
      }
    } finally {
      completionInFlight.current = false;
    }
  }

  async function startPlayback() {
    if (!document || phase === "loading-audio") return;
    setError("");
    if (phase === "paused" && audio.current.src) {
      await audio.current.play();
      await api("/playback/resume", { method: "POST" });
      setPhase("playing");
      return;
    }
    setPhase("loading-audio");
    const expectedVersion = interruptLocalAudio();
    try {
      const response = await api("/playback/start", { method: "POST" });
      const nextState = await response.json();
      if (expectedVersion !== playbackVersion.current) return;
      setNavigation(nextState);
      setActiveSentenceId(nextState.current_sentence_id);
      await fetchAndPlayAudio(nextState, expectedVersion);
    } catch (playError) {
      setPhase("ready");
      setError(playError.message);
    }
  }

  async function pausePlayback() {
    audio.current.pause();
    setPhase("paused");
    try {
      const response = await api("/playback/pause", { method: "POST" });
      setNavigation(await response.json());
    } catch (pauseError) { setError(pauseError.message); }
  }

  async function stopPlayback() {
    interruptLocalAudio();
    setPhase(document ? "ready" : "empty");
    try {
      const response = await api("/playback/stop", { method: "POST" });
      setNavigation(await response.json());
    } catch (stopError) { setError(stopError.message); }
  }

  async function command(text) {
    if (!document) return;
    setError("");
    const expectedVersion = interruptLocalAudio();
    setPhase("loading-audio");
    try {
      const response = await api("/command", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const payload = await response.json();
      if (expectedVersion !== playbackVersion.current) return;
      setNavigation(payload.state);
      setActiveSentenceId(payload.state.current_sentence_id);
      if (payload.request_id == null) {
        setPhase("ready");
        return;
      }
      await fetchAndPlayAudio({ ...payload.state, request_id: payload.request_id }, expectedVersion);
    } catch (commandError) {
      setPhase("ready");
      setError(commandError.message);
    }
  }

  const controlsBusy = ["loading-audio", "uploading"].includes(phase);
  const statusLabel = voiceProcessing ? "Understanding voice…" : phase === "voice-interrupted" ? "Listening…" : phase === "loading-audio" ? "Preparing voice" : phase === "playing" ? "Reading aloud" : phase === "paused" ? "Paused" : phase === "uploading" ? "Reading document" : navigation?.document_completed ? "Completed" : document ? "Ready" : "No document";

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-mark" aria-hidden="true"><span /><span /><span /></div>
        <div><p className="eyebrow">Read beyond the screen</p><h1>Narrative.</h1></div>
        <div className={`connection ${document ? "active" : ""}`}><span />{document ? "Document loaded" : "Waiting for a file"}</div>
      </header>

      <div className="reader-unit">
      <section className={`workspace ${document ? "has-document" : ""}`}>
        {document && (
          <aside className="section-rail" aria-label="Document reading map">
            <div className="rail-heading">
              <p className="rail-label">Reading map</p>
              <span>{document.sections.length} {document.sections.length === 1 ? "section" : "sections"}</span>
            </div>
            <div className="section-list" ref={transcript}>
              {document.sections.map((section, sectionIndex) => {
                const isCurrentSection = section.sentences.some((sentence) => sentence.id === activeSentenceId);
                return (
                  <section className={`section-summary ${isCurrentSection ? "current" : ""}`} key={section.id}>
                    <div className="section-heading">
                      <span>{String(sectionIndex + 1).padStart(2, "0")}</span>
                      <h2>{section.title || `Section ${sectionIndex + 1}`}</h2>
                    </div>
                    <ol className="sentence-list">
                      {section.sentences.map((sentence) => {
                        const isActive = sentence.id === activeSentenceId;
                        return (
                          <li
                            className={`${sentence.block_type === "list_item" ? "list-item" : ""} ${isActive ? "active" : ""}`}
                            key={sentence.id}
                            ref={(node) => {
                              if (node) sentenceElements.current.set(sentence.id, node);
                              else sentenceElements.current.delete(sentence.id);
                            }}
                            aria-current={isActive ? "true" : undefined}
                          >
                            {sentence.block_type === "list_item" && (
                              <span className="list-marker" aria-hidden="true">{sentence.list_marker || "•"}</span>
                            )}
                            <span>{sentence.raw_text}</span>
                          </li>
                        );
                      })}
                    </ol>
                  </section>
                );
              })}
            </div>
          </aside>
        )}
        <article className={`reader ${document ? "has-document" : ""}`}>
          {!document ? (
            <div className={`drop-zone ${dragging ? "dragging" : ""}`}
              onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
              onDragOver={(event) => event.preventDefault()}
              onDragLeave={() => setDragging(false)}
              onDrop={(event) => { event.preventDefault(); setDragging(false); uploadFile(event.dataTransfer.files[0]); }}>
              <div className="file-illustration"><Icon name="file" size={34} /></div>
              <p className="eyebrow">Hello there!</p>
              <h2>What can I read for you? :))</h2>
              <p>Drop a PDF, .txt, or Markdown file here, or select one from your computer.</p>
              <button className="primary-button" type="button" onClick={() => fileInput.current?.click()} disabled={phase === "uploading"}>
                <Icon name="upload" />{phase === "uploading" ? "Opening document…" : "Choose a document"}
              </button>
            </div>
          ) : (
            <div className={`source-shell ${source?.type === "pdf" ? "pdf-source" : "text-source"}`}>
              <div className="source-bar">
                <div><Icon name="file" size={18}/><span>{document.name}</span></div>
                <button className="text-button" onClick={() => fileInput.current?.click()} type="button">Replace file</button>
              </div>
              {source?.type === "pdf" ? (
                <iframe className="pdf-viewer" src={source.url} title={`${document.name} document preview`} />
              ) : (
                <pre className="text-viewer">{source?.text}</pre>
              )}
            </div>
          )}
        </article>
      </section>

      {error && <div className="error-toast" role="alert"><span>{error}</span><button onClick={() => setError("")} aria-label="Dismiss error"><Icon name="close" size={17}/></button></div>}

      <footer className="control-dock" aria-label="Reader controls">
        <button className="upload-control" type="button" onClick={() => fileInput.current?.click()}><Icon name="upload" /><span><small>Document</small>{document ? "Replace file" : "Upload file"}</span></button>
        <div className="transport">
          <button className="icon-button" onClick={stopPlayback} disabled={!document || phase === "ready" || phase === "uploading"} aria-label="Stop"><Icon name="stop" size={17}/></button>
          <button className="play-button" onClick={phase === "playing" ? pausePlayback : startPlayback} disabled={!document || controlsBusy} aria-label={phase === "playing" ? "Pause" : "Play"}><Icon name={phase === "playing" ? "pause" : "play"} size={24}/></button>
          <button className="icon-button" onClick={() => command("next section")} disabled={!document || controlsBusy} aria-label="Next section"><Icon name="next" size={19}/></button>
        </div>
        <div className="voice-control">
          <button className={`voice-button ${microphoneEnabled ? "listening" : ""} ${voiceProcessing ? "processing" : ""}`} onClick={microphoneEnabled ? () => stopContinuousListening(true) : startContinuousListening} disabled={!document || microphoneStarting} aria-label={microphoneEnabled ? "Turn continuous voice control off" : "Turn continuous voice control on"} aria-pressed={microphoneEnabled}><Icon name={microphoneEnabled ? "stop" : "mic"} size={18}/></button>
          <span><small>Voice control</small>{microphoneStarting ? "Starting…" : microphoneEnabled ? "Listening" : "Off"}</span>
        </div>
        <div className="speed-control" aria-label="Reading speed">
          <button onClick={() => command("slow down")} disabled={!document || controlsBusy || (navigation?.playback_speed ?? 1) <= 0.5} aria-label="Slow down"><Icon name="minus" size={16}/></button>
          <span><small>Speed</small>{(navigation?.playback_speed ?? 1).toFixed(1)}×</span>
          <button onClick={() => command("speed up")} disabled={!document || controlsBusy || (navigation?.playback_speed ?? 1) >= 2} aria-label="Speed up"><Icon name="plus" size={16}/></button>
        </div>
        <div className="status-control" title={voiceFeedback}><span className={`status-dot ${phase}`} /><span className="status-copy"><small>Status</small>{statusLabel}{voiceFeedback && <em>{voiceFeedback}</em>}</span></div>
        <div className="progress-control"><div><small>Document completed</small><strong>{progress}%</strong></div><div className="progress-track" aria-label={`${progress}% complete`}><span style={{ width: `${progress}%` }} /></div></div>
      </footer>
      </div>

      <p className="visually-hidden" aria-live="polite" aria-atomic="true">
        {voiceFeedback || (activeSentence ? `Current sentence: ${activeSentence.raw_text}` : "")}
      </p>

      <input ref={fileInput} className="visually-hidden" type="file" accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown" onChange={(event) => uploadFile(event.target.files?.[0])} />
    </main>
  );
}
