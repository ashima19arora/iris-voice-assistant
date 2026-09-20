"""
Iris Desktop Orb Python Bridge Process
=======================================
Communicates with Electron Orb over stdio JSON lines.
Handles natural language commands, microphone transcription, and live status.
"""

import sys
import os
import io
import json
import time
import threading
import logging

# Ensure robust UTF-8 stdio on Windows across Python 3.10+
try:
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

# Configure logging to stderr so stdout is purely for JSON-RPC
logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("orb_bridge")

import re
import actions

# Wake words: "hey iris", "hi iris", "hello iris", "wake up", "iris", or Hindi "नमस्ते आईरिस" / "आईरिस"
WAKE_WORDS_PATTERN = r'\b(?:(?:hi|hey|hello)(?:\s+\w+)?[,]?\s*iris|wake\s*up|iris|नमस्ते\s*आईरिस|आईरिस|जागो\s*आईरिस)\b'
WAKE_PREFIX_STRIP = r'^(?:(?:hi|hey|hello)(?:\s+\w+)?[,]?\s*iris|wake\s*up|iris|नमस्ते\s*आईरिस|आईरिस|जागो\s*आईरिस)\b[,\s]*'
INACTIVITY_SLEEP_TIMEOUT = 45.0

# State tracking
_is_sleeping = True
_last_active_time = time.time()
_is_manual_recording = False
_last_manual_recording_time = 0.0
_handsfree_running = True
_command_lock = threading.Lock()
_manual_stop_event = threading.Event()

# Lazy load ASR model only when voice recognition is requested
_asr_model = None
_asr_model_loading = False

def get_asr_model():
    global _asr_model, _asr_model_loading
    if _asr_model is not None:
        return _asr_model
    if _asr_model_loading:
        return None
    _asr_model_loading = True
    try:
        import onnx_asr
        logger.info("Loading Parakeet ASR model in background...")
        _asr_model = onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v2", quantization="int8")
        logger.info("Parakeet ASR loaded successfully.")
    except Exception as e:
        logger.warning(f"Could not load onnx_asr, will use standard speech recognizer: {e}")
        _asr_model = None
    finally:
        _asr_model_loading = False
    return _asr_model

def send_ipc(data: dict):
    """Write single JSON line to stdout for Electron."""
    try:
        line = json.dumps(data, ensure_ascii=False)
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
    except Exception as e:
        logger.error(f"Failed to send IPC data: {e}")

def handle_command(text: str, lang: str = "auto"):
    """Executes natural language command via Iris actions engine."""
    global _is_sleeping, _last_active_time
    if not text or not text.strip():
        return

    _is_sleeping = False
    _last_active_time = time.time()

    text = text.strip()
    logger.info(f"Executing command: '{text}' (lang={lang})")
    send_ipc({"type": "status", "state": "thinking", "text": "PROCESSING"})

    with _command_lock:
        try:
            exec_lang = lang if lang and lang != "auto" else None
            result = actions.execute_command(text, lang=exec_lang)
            
            reply_message = result.message or f"Executed: {text}"
            send_ipc({
                "type": "result",
                "success": bool(result.success),
                "intent": result.intent or "ACTION",
                "message": reply_message,
                "text": reply_message
            })
            # If speech synthesis is playing audio, glow speaking state
            try:
                if actions.is_speaking():
                    send_ipc({"type": "status", "state": "speaking", "text": "SPEAKING"})
                    actions.wait_until_speech_finishes(timeout=8.0)
            except Exception:
                pass
        except Exception as exc:
            logger.error(f"Error in actions.execute_command: {exc}", exc_info=True)
            send_ipc({
                "type": "result",
                "success": False,
                "intent": "ERROR",
                "message": f"Error executing command: {exc}",
                "text": f"Error: {exc}"
            })
        finally:
            send_ipc({"type": "status", "state": "ready", "text": "READY"})

def handle_listen(lang: str = "auto"):
    """Manual voice command trigger (Mic button or right-click push-to-talk)."""
    global _is_manual_recording, _is_sleeping, _last_active_time, _last_manual_recording_time, _manual_stop_event
    _manual_stop_event.clear()
    _is_manual_recording = True
    _is_sleeping = False
    _last_active_time = time.time()

    import speech_recognition as sr
    recognizer = sr.Recognizer()
    recognizer.pause_threshold = 0.85
    recognizer.non_speaking_duration = 0.35
    recognizer.phrase_threshold = 0.25

    send_ipc({"type": "status", "state": "listening", "text": "LISTENING..."})

    try:
        with sr.Microphone(sample_rate=16000) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.2)
            recognizer.dynamic_energy_threshold = True
            recognizer.dynamic_energy_ratio = 1.5
            recognizer.energy_threshold = max(recognizer.energy_threshold, 350)

            logger.info(f"Listening for speech (lang mode: {lang})...")
            audio_chunks = []
            try:
                for chunk in recognizer._listen(source, timeout=6.5, phrase_time_limit=14.0, stream=True):
                    audio_chunks.append(chunk)
                    if _manual_stop_event.is_set():
                        logger.info("Manual stop requested (push-to-talk released or toggled).")
                        break
            except sr.WaitTimeoutError:
                if not audio_chunks:
                    raise

            if not audio_chunks:
                send_ipc({"type": "status", "state": "ready", "text": "READY"})
                return

            raw_data = b"".join(c.get_raw_data() for c in audio_chunks)
            audio = sr.AudioData(raw_data, source.SAMPLE_RATE, source.SAMPLE_WIDTH)

        send_ipc({"type": "status", "state": "thinking", "text": "TRANSCRIBING..."})

        text = ""

        # 1. Dedicated Hindi mode: Direct hi-IN recognition for authentic Devanagari
        if lang in ("hi", "hi-IN"):
            try:
                text = recognizer.recognize_google(audio, language="hi-IN").strip()
                logger.info(f"Google Hindi ASR transcribed: '{text}'")
            except Exception as e:
                logger.debug(f"Google Hindi ASR fallback: {e}")
                try:
                    text = recognizer.recognize_google(audio, language="en-IN").strip()
                except Exception:
                    pass

        # 2. Dedicated English mode
        elif lang in ("en", "en-US"):
            model = get_asr_model()
            if model is not None:
                try:
                    import soundfile as sf
                    import numpy as np
                    audio_data = audio.get_wav_data()
                    audio_np, sample_rate = sf.read(io.BytesIO(audio_data))
                    audio_np = audio_np.astype(np.float32)
                    text = model.recognize(audio_np, sample_rate=sample_rate).strip()
                except Exception:
                    pass
            if not text:
                try:
                    text = recognizer.recognize_google(audio, language="en-US").strip()
                except Exception:
                    pass

        # 3. Auto mode: Bilingual detection (try hi-IN or en-IN)
        else:
            try:
                text = recognizer.recognize_google(audio, language="hi-IN").strip()
            except Exception:
                try:
                    text = recognizer.recognize_google(audio, language="en-IN").strip()
                except Exception:
                    pass

            if not text:
                model = get_asr_model()
                if model is not None:
                    try:
                        import soundfile as sf
                        import numpy as np
                        audio_data = audio.get_wav_data()
                        audio_np, sample_rate = sf.read(io.BytesIO(audio_data))
                        audio_np = audio_np.astype(np.float32)
                        text = model.recognize(audio_np, sample_rate=sample_rate).strip()
                    except Exception:
                        pass

        if text:
            # Reject noise artifacts
            clean_t = text.strip()
            if len(clean_t) < 2 or clean_t.lower() in ("uh", "um", "ah", "eh", "huh"):
                logger.info(f"Ignoring voice noise artifact: '{text}'")
                send_ipc({"type": "status", "state": "ready", "text": "READY"})
                return

            logger.info(f"Transcribed voice: '{text}'")
            send_ipc({"type": "transcribed", "text": text})
            handle_command(text, lang=lang)
        else:
            send_ipc({
                "type": "result",
                "success": False,
                "intent": "VOICE_UNRECOGNIZED",
                "message": "Could not recognize any speech. Please try speaking again.",
                "text": "I didn't catch that. Please try again."
            })
            send_ipc({"type": "status", "state": "ready", "text": "READY"})

    except sr.WaitTimeoutError:
        logger.info("Microphone timed out waiting for speech.")
        send_ipc({
            "type": "result",
            "success": False,
            "intent": "TIMEOUT",
            "message": "Microphone timed out (no speech detected).",
            "text": "Listening timed out. Click the mic again to speak."
        })
        send_ipc({"type": "status", "state": "ready", "text": "READY"})
    except Exception as exc:
        logger.error(f"Microphone error: {exc}", exc_info=True)
        send_ipc({
            "type": "result",
            "success": False,
            "intent": "MIC_ERROR",
            "message": f"Microphone error: {exc}",
            "text": f"Microphone unavailable: {exc}"
        })
        send_ipc({"type": "status", "state": "ready", "text": "READY"})
    finally:
        _is_manual_recording = False
        _last_manual_recording_time = time.time()

def handsfree_worker():
    """Continuous hands-free wake word and active listening daemon."""
    global _is_sleeping, _last_active_time, _is_manual_recording, _handsfree_running, _last_manual_recording_time
    logger.info("Hands-free voice daemon starting. Listening for 'Hey Iris' / 'Wake up'...")

    import speech_recognition as sr
    recognizer = sr.Recognizer()
    recognizer.pause_threshold = 0.9
    recognizer.non_speaking_duration = 0.4
    recognizer.phrase_threshold = 0.3
    recognizer.dynamic_energy_threshold = True
    recognizer.dynamic_energy_adjustment_damping = 0.15
    recognizer.dynamic_energy_ratio = 1.6
    recognizer.energy_threshold = 360

    time.sleep(2.0)  # Wait for initial engine load

    try:
        with sr.Microphone(sample_rate=16000) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            recognizer.energy_threshold = max(recognizer.energy_threshold, 350)

            # Signal standby state initially
            send_ipc({"type": "status", "state": "sleeping", "text": "STANDBY"})

            while _handsfree_running:
                cycle_start = time.time()

                # Acoustic feedback loopback prevention: do not listen while Iris speaks
                try:
                    if actions.is_speaking():
                        actions.wait_until_speech_finishes(timeout=8.0)
                        time.sleep(0.3)
                except Exception:
                    pass

                # If manual recording (mic button or right-click push-to-talk) is active, yield
                if _is_manual_recording:
                    time.sleep(0.3)
                    continue

                # Inactivity sleep check (45s)
                now = time.time()
                if not _is_sleeping and (now - _last_active_time > INACTIVITY_SLEEP_TIMEOUT):
                    _is_sleeping = True
                    logger.info("45s inactivity reached. Entering Standby mode...")
                    send_ipc({"type": "collapse"})
                    send_ipc({"type": "status", "state": "sleeping", "text": "STANDBY"})

                try:
                    # Listen with 3.0s timeout so the loop can periodically check state
                    audio = recognizer.listen(source, timeout=3.0, phrase_time_limit=12.0)
                except sr.WaitTimeoutError:
                    continue
                except Exception as e:
                    logger.debug(f"Handsfree listen cycle error: {e}")
                    time.sleep(0.2)
                    continue

                # Mutual exclusion: discard if manual recording occurred during or right after this cycle
                if _is_manual_recording or (cycle_start < _last_manual_recording_time + 1.2):
                    logger.debug("Discarding handsfree audio cycle due to manual recording.")
                    continue

                try:
                    if actions.is_speaking():
                        continue
                except Exception:
                    pass

                # Transcribe
                text = ""
                model = get_asr_model()
                if model is not None:
                    try:
                        import soundfile as sf
                        import numpy as np
                        audio_data = audio.get_wav_data()
                        audio_np, sample_rate = sf.read(io.BytesIO(audio_data))
                        audio_np = audio_np.astype(np.float32)
                        text = model.recognize(audio_np, sample_rate=sample_rate).strip()
                    except Exception as e:
                        logger.debug(f"Handsfree ASR error: {e}")

                if not text:
                    try:
                        text = recognizer.recognize_google(audio).strip()
                    except Exception:
                        pass

                if not text:
                    continue

                clean_text = text.strip()
                # Ignore short background noise artifacts
                if len(clean_text) < 3 or clean_text.lower() in ("uh", "um", "ah", "eh", "huh", "you", "the"):
                    continue

                logger.info(f"[Handsfree Heard] '{text}' (sleeping={_is_sleeping})")

                if _is_sleeping:
                    wake_match = re.search(WAKE_WORDS_PATTERN, text, re.IGNORECASE)
                    if not wake_match:
                        # Strictly ignore ambient noise and non-wake speech in standby
                        continue

                    _is_sleeping = False
                    _last_active_time = time.time()
                    logger.info(f"[Iris Woke Up!] Triggered by '{text}'")
                    send_ipc({"type": "wake", "text": text})

                    # Check for compound command (e.g. "Hey Iris, open WhatsApp Web")
                    command_after = text.strip()
                    while True:
                        prev_cmd = command_after
                        command_after = re.sub(WAKE_PREFIX_STRIP, '', command_after, flags=re.IGNORECASE).strip()
                        if command_after == prev_cmd:
                            break

                    has_real_content = bool(re.search(r'[a-zA-Z0-9]', command_after))
                    if command_after and has_real_content:
                        send_ipc({"type": "transcribed", "text": command_after})
                        handle_command(command_after)
                    else:
                        wake_resp = "Hey, I am awake and ready for your commands!"
                        send_ipc({
                            "type": "result",
                            "success": True,
                            "intent": "WAKE",
                            "message": wake_resp,
                            "text": wake_resp
                        })
                        send_ipc({"type": "status", "state": "speaking", "text": "SPEAKING"})
                        try:
                            actions.speak(wake_resp, lang="en", asynchronous=False)
                            actions.wait_until_speech_finishes(timeout=4.0)
                        except Exception:
                            pass
                        send_ipc({"type": "status", "state": "ready", "text": "READY"})
                else:
                    # Active Mode: reset inactivity timer
                    _last_active_time = time.time()

                    # Check for sleep or minimize commands
                    t_lower = text.lower().strip()
                    if re.search(r"\b(?:go\s+to\s+sleep|sleep|minimize|collapse)\b", t_lower):
                        _is_sleeping = True
                        logger.info("User requested sleep/minimize.")
                        sleep_reply = "Going to standby mode. Say 'Hey Iris' to wake me up."
                        send_ipc({
                            "type": "result",
                            "success": True,
                            "intent": "SLEEP",
                            "message": sleep_reply,
                            "text": sleep_reply
                        })
                        send_ipc({"type": "status", "state": "speaking", "text": "SPEAKING"})
                        try:
                            actions.speak(sleep_reply, lang="en", asynchronous=False)
                            actions.wait_until_speech_finishes(timeout=4.0)
                        except Exception:
                            pass
                        send_ipc({"type": "collapse"})
                        send_ipc({"type": "status", "state": "sleeping", "text": "STANDBY"})
                        continue

                    # Strip any repeated wake prefix if user spoke it again
                    clean_cmd = re.sub(WAKE_PREFIX_STRIP, '', text, flags=re.IGNORECASE).strip()
                    cmd_to_run = clean_cmd if bool(re.search(r'[a-zA-Z0-9]', clean_cmd)) else text

                    send_ipc({"type": "transcribed", "text": cmd_to_run})
                    handle_command(cmd_to_run)

    except Exception as exc:
        logger.error(f"Handsfree worker fatal exception: {exc}", exc_info=True)

def main():
    logger.info("Iris Orb Python Bridge starting up...")
    send_ipc({"type": "ready", "status": "Iris Engine Loaded"})

    # Pre-warm ASR in background thread
    threading.Thread(target=get_asr_model, daemon=True).start()

    # Launch hands-free continuous voice daemon
    threading.Thread(target=handsfree_worker, daemon=True).start()

    global _is_sleeping, _last_active_time

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except Exception:
                logger.warning(f"Invalid JSON received: {line}")
                continue

            msg_type = data.get("type")
            if msg_type == "command":
                text = data.get("text", "")
                lang = data.get("lang", "auto")
                threading.Thread(target=handle_command, args=(text, lang), daemon=True).start()
            elif msg_type == "listen":
                lang = data.get("lang", "auto")
                threading.Thread(target=handle_listen, args=(lang,), daemon=True).start()
            elif msg_type == "sleep":
                _is_sleeping = True
                send_ipc({"type": "status", "state": "sleeping", "text": "STANDBY"})
            elif msg_type == "user_active":
                _is_sleeping = False
                _last_active_time = time.time()
                send_ipc({"type": "status", "state": "ready", "text": "READY"})
            elif msg_type == "stop":
                _manual_stop_event.set()
            elif msg_type == "ping":
                send_ipc({"type": "pong"})
            else:
                logger.info(f"Unknown message type: {msg_type}")

        except (KeyboardInterrupt, SystemExit):
            break
        except Exception as e:
            logger.error(f"Loop error: {e}", exc_info=True)

    logger.info("Iris Orb Python Bridge exited.")

if __name__ == "__main__":
    main()
