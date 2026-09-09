# Rime Evidence

## Hard voice claim

Narrative supports application-level **interruption and recovery** while Rime speech is playing. When the browser detects that the user has started speaking, it pauses the current audio locally without waiting for ASR. The recorded command is then transcribed, mapped to a closed intent, and applied to the navigation state. Any obsolete synthesis or completion result is rejected, and the next audible clip reflects the latest accepted command.

## Acceptance test

Use [`demo/acceptance_fixture.md`](demo/acceptance_fixture.md) with the fixed Rime configuration documented in `README.md`.

The test passes when all of the following are true:

The test passes when all of the following are true:

1. Saying "start reading" begins Rime speech without pressing Play.
2. Saying "pause" interrupts current audio and retains a valid reading position.
3. Saying "resume" continues playback from the retained position.
4. Saying "next section" moves playback to the next document section.
5. Saying "read the numbers" reads numeric content without unexpectedly changing sections.
6. Saying "repeat" generates audio again for the current reading position.
7. Saying "stop" ends playback while retaining a valid reading position.
8. An unsupported phrase does not navigate the document.
9. A stale `/playback/complete` request receives HTTP 409 and cannot advance the document.
10. Saying an unsupported phrase such as "summarize the document" does not change the section or sentence and restores the interrupted audio when possible.
11. A stale `/playback/complete` request receives HTTP 409 and cannot advance the document.

## Configuration held constant

| Field | Test value |
| --- | --- |
| Rime endpoint | `https://users.rime.ai/v1/rime-tts` |
| Model ID | `coda` |
| Speaker | `lyra` |
| Language | `en` |
| Audio response | WAV (`Accept: audio/wav`) |
| Transport | HTTPS POST request/response through the FastAPI backend |
| Initial speed | `speedAlpha: 1.0` |
| ASR | Faster Whisper `base.en`, CPU, `int8`, English |
| Browser | Chrome |

## Procedure

1. Start the backend and frontend using the root README.
2. Move any previous `logs/metrics.jsonl` aside so the sample counts only describe this run.
3. Open the app, upload `demo/acceptance_fixture.md`, allow microphone access, and use headphones when practical.
4. Say "start reading" and verify that playback begins without pressing Play. This is an unlabeled setup command and is not included in the six-command accuracy result.
5. Open browser developer tools and load the six-command ground-truth queue shown below:
6. Say these commands in order: pause, resume, next section, read the numbers, repeat, and stop. Wait for a visible response before saying the next command.


```js
window.__RIME_TEST_METRICS__ = {
  groundTruthQueue: [
    {
      command: "PAUSE",
      expectedSectionId: "sec_1",
      expectedSentenceId: "sec_1.sent_1"
    },
    {
      command: "RESUME",
      expectedSectionId: "sec_1",
      expectedSentenceId: "sec_1.sent_1"
    },
    {
      command: "NEXT_SECTION",
      expectedSectionId: "sec_2",
      expectedSentenceId: "sec_2.sent_1"
    },
    {
      command: "READ_NUMBERS",
      expectedSectionId: "sec_2",
      expectedSentenceId: "sec_2.sent_1"
    },
    {
      command: "REPEAT",
      expectedSectionId: "sec_2",
      expectedSentenceId: "sec_2.sent_1"
    },
    {
      command: "STOP",
      expectedSectionId: "sec_2",
      expectedSentenceId: "sec_2.sent_1"
    }
  ]
};
```

7. Confirm that the queue length reaches zero:

```js
window.__RIME_TEST_METRICS__.groundTruthQueue.length
```

8. Run:

```powershell
python analyze_metrics.py logs/metrics.jsonl

```

9. Save the terminal report and the corresponding demo recording. Report sample counts with every percentile or percentage.

## Results

### Automated acceptance result

**PASS.** The repository test suite verifies cancellation of a delayed/stale TTS response, rejection of stale browser completion IDs, voice-command state mutation, start-by-voice behavior, command errors, metric-label propagation, and temporary audio cleanup. At the time this evidence file was prepared, the complete suite reported **36 passed**.

### Final labeled device run

| Measure | Result |
| --- | --- |
| Interrupt-to-silence | `p50: 0.25 ms; p95: 1.15 ms; n=4` |
| Time-to-first-audio, cold | `p50: 6556.21 ms; p95: 6556.21 ms; n=1` |
| Time-to-first-audio, warm | `p50: 6061.17 ms; p95: 27230.73 ms; n=8` |
| Command recognition accuracy | `100.00% (6/6)` |
| State-correctness pass rate | `3/6 passed` |

All six labeled commands - Pause, Resume, Next Section, Read Numbers, Repeat, and Stop were recognized correctly. This is a small exploratory sample and should not be interpreted as general ASR accuracy across all speakers or environments.

The exact-position state check passed 3 of 6 assertions. A state assertion passed only when the section and sentence IDs after a command exactly matched the fixed IDs written before the test. During the failed assertions, playback continued advancing while the tester waited and spoke the next command, so those fixed sentence IDs became outdated. The commands were still recognized correctly and executed at the reader’s current position. Therefore, **the 3/6 result is reported as an exploratory limitation of the test design, not as a 50% command-success rate**.

## Metric definitions

- **Interrupt-to-silence:** how quickly the browser paused the currently played audio after detecting user speech, excluding later ASR and command-processing time.
- **Time-to-first-audio:** measures the application-level delay between handing a request to Rime and starting playback in the browser. It includes Rime generation, network transfer, complete audio download, browser processing, and playback startup; it is not a measurement of raw Rime model latency alone.
- **Command recognition accuracy:** exact accepted intent versus the queued canonical ground truth.
- **State correctness:** resulting section and sentence IDs versus the queued expected IDs.

## Limitations and unsupported input

- This small-sample acceptance run is exploratory and device/network specific, not a general Rime benchmark.
- The browser's energy threshold and echo cancellation depend on microphone, speaker, room noise, and browser implementation.
- Faster Whisper model loading makes the first command slower; warm and cold behavior must not be mixed.
- Recognition is intentionally limited to short English commands. Dictation and open-ended requests are unsupported.
- The implementation requests a complete WAV response before browser playback; it does not measure Rime's first streamed provider byte.
- Scanned PDFs require OCR and complex PDF tables/equations may have imperfect reading order.
- No comparison against alternate TTS providers is claimed. 

## Reproducible code paths

- `frontend/src/App.jsx` - speech detection, immediate local pause, metric timestamps, audio playback, and stale client invalidation.
- `backend/api/command_routes.py` - transcript, accepted intent, ground truth, and expected-state logging.
- `backend/tts/request_manager.py` - Rime handoff, prefetch, generation cancellation, and stale-response rejection.
- `backend/metrics.py` - append-only JSONL metric writer.
- `analyze_metrics.py` - p50/p95, recognition accuracy, and state-correctness report.
- `backend/tests/test_interruption.py` - deterministic delayed-response cancellation test.
