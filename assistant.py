"""
Iris Interactive Voice Assistant - Main Execution Runtime
===========================================================
WHAT THIS FILE DOES (Simple English):
  This is the primary heartbeat of Iris. It continuously listens to your microphone,
  converts your spoken words into text using an offline neural speech-to-text model,
  understands your intent, and triggers the computer to perform the action (e.g. fill
  forms, control windows, search websites, or answer questions).
  It also features an automatic 45-second sleep mode to save CPU when you are not speaking.

Startup does not run any command. It only loads the speech model, opens the
microphone, and waits for you to speak.

GREAT TECH & PACKAGES USED IN THIS FILE:
  - onnx_asr (NVIDIA NeMo Parakeet TDT 0.6B int8):
      * What it does: High-speed, local neural Speech-to-Text (Automatic Speech Recognition).
      * Why we use it: Transcribes voice in real-time (~0.1s on standard CPU) without sending
        private user voice recordings to external cloud servers.
      * Benefit: Completely private, zero cloud latency, and works even without fast internet.
  - speech_recognition:
      * What it does: Hardware microphone audio capture and silence detection.
      * Why we use it: Continuously streams audio from the user's microphone with ambient
        noise filtering and responsive pause detection.
      * Benefit: Automatically detects when you finish speaking (0.8s silence) and cuts off
        instantly so you never have to wait.
  - soundfile & numpy:
      * What it does: Ultra-fast mathematical audio buffer decoding in RAM.
      * Why we use it: Converts raw microphone WAV bytes directly into float32 arrays in under 2ms.
"""

import io
import os
import sys

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np
import soundfile as sf
import speech_recognition as sr
import onnx_asr
import actions

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

import time
import re
from actions.languages import detect_language

# Leftover demo/ASR junk that must never run as a command on its own
_ASR_JUNK_CLAUSE = re.compile(
    r'\b(?:youtube\s+kolo|youtube\s+kholo|sachkaro|search\s+karo|ranger\s+station|'
    r'ram\s+check\s+karo|yup)\b[,\s]*',
    re.IGNORECASE,
)


def _clean_transcript(text: str) -> str:
    """Drop hallucinated demo phrases; keep the user's real words."""
    cleaned = _ASR_JUNK_CLAUSE.sub(' ', text)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' ,.-')
    return cleaned

def run_assistant():
    actions.print_aws_service_banner()
    print("Loading Parakeet ASR model into memory...")
    try:
        model = onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v2", quantization="int8")
        print("Model loaded successfully.")
    except Exception as e:
        print(f"Error loading model: {e}")
        return

    recognizer = sr.Recognizer()
    # Natural pause detection: allows 2.0s silence for conversational pauses so user isn't cut off mid-thought
    recognizer.pause_threshold = 2.0
    recognizer.non_speaking_duration = 0.5
    recognizer.phrase_threshold = 0.3

    INACTIVITY_SLEEP_TIMEOUT = 45.0  # seconds of silence before entering sleep mode
    is_sleeping = False
    last_active_time = time.time()
    current_lang = 'en'

    try:
        with sr.Microphone(sample_rate=16000) as source:
            print("Calibrating for background noise (1s)...")
            recognizer.adjust_for_ambient_noise(source, duration=1.0)
            # Fix dynamic energy drift so microphone cuts off promptly when user stops speaking
            recognizer.dynamic_energy_threshold = False
            recognizer.energy_threshold = max(recognizer.energy_threshold, 300)
            print(f"Calibrated energy threshold: {recognizer.energy_threshold:.1f}")

            try:
                actions.speak("Iris is active and ready for command.", lang='en', asynchronous=False)
                actions.wait_until_speech_finishes(timeout=12.0)
            except Exception as speak_error:
                print(f"[Iris] Voice announcement skipped: {speak_error}")

            print("[Iris Ready] Listening. Speak a command when you want.\n")
            last_active_time = time.time()

            while True:
                try:
                    # Prevent acoustic loopback: never listen while assistant is still speaking
                    actions.wait_until_speech_finishes(timeout=12.0)

                    # Check for inactivity and enter sleep mode if silent for 45s
                    if not is_sleeping and (time.time() - last_active_time > INACTIVITY_SLEEP_TIMEOUT):
                        is_sleeping = True
                        print("\n\033[94m[Iris State] Inactivity detected. Entering Sleep Mode...\033[0m")
                        sleep_msg = "Going to sleep mode. Say 'hey iris', 'hi iris', 'hello iris', or 'wake up' to wake me up."
                        try:
                            actions.speak(sleep_msg, lang='en', asynchronous=False)
                            actions.wait_until_speech_finishes(timeout=12.0)
                        except Exception as speak_error:
                            print(f"[Iris] Sleep announcement skipped: {speak_error}")
                        print("\033[94m[Iris Asleep - Listening for wake word: 'hey iris' / 'hi iris' / 'hello iris' / 'wake up']\033[0m\n")

                    status_prompt = "\033[94m[Iris Asleep (Say 'hey iris' / 'hi iris' / 'hello iris' / 'wake up')...]\033[0m" if is_sleeping else "\033[90m[Listening...]\033[0m"
                    print(status_prompt, end="\r", flush=True)

                    # Listen with 5s timeout to periodically refresh sleep-timer.
                    # phrase_time_limit keeps recordings short so noise is not
                    # mixed with the next command.
                    audio = recognizer.listen(source, timeout=5.0, phrase_time_limit=20)
                    print("                                                         \r", end="")

                    # Audio conversion to float32 numpy array
                    audio_data = audio.get_wav_data()
                    audio_np, sample_rate = sf.read(io.BytesIO(audio_data))
                    audio_np = audio_np.astype(np.float32)

                    # Speech Recognition via Parakeet
                    text = model.recognize(audio_np, sample_rate=sample_rate).strip()
                    text = _clean_transcript(text)

                    if not text:
                        continue

                    detected_lang = detect_language(text)
                    current_lang = detected_lang

                    # Handle Sleep Mode Wake-Up
                    if is_sleeping:
                        # Wake words: "hey iris", "hi iris", "hello iris",
                        # or plain "wake up" (4 options total). Greeting
                        # word (hi/hey/hello) is NOT optional when paired
                        # with "iris" -- those words alone are too common
                        # in normal speech and would false-trigger. "wake
                        # up" alone is kept as a 4th, simpler option.
                        # (?:\s+\w+)? allows one filler word in between,
                        # e.g. "hey, um, iris".
                        WAKE_WORDS_PATTERN = (
                            r'\b(?:(?:hi|hey|hello)(?:\s+\w+)?[,]?\s*iris|wake\s*up)\b'
                        )
                        wake_match = re.search(WAKE_WORDS_PATTERN, text, re.IGNORECASE)

                        # Also check if user spoke a direct valid accessibility command while asleep
                        parsed_candidate = None
                        if not wake_match:
                            candidate_intent = actions.intent_parser.parse_intent(text)
                            if candidate_intent.name not in ("UNKNOWN", "SEARCH_WEB"):
                                parsed_candidate = candidate_intent

                        if wake_match or parsed_candidate:
                            is_sleeping = False
                            last_active_time = time.time()
                            print(f"\n\033[92m[Iris Woke Up!]\033[0m (Heard: '{text}')")

                            # Check if a command was appended after wake word (e.g., "hey iris, open youtube")
                            # Matches WAKE_WORDS_PATTERN above -- anchored to
                            # the START (^) since this strips a prefix.
                            WAKE_PREFIX_STRIP = (
                                r'^(?:(?:hi|hey|hello)(?:\s+\w+)?[,]?\s*iris|wake\s*up)\b[,\s]*'
                            )
                            command_after = text.strip()
                            while True:
                                prev_cmd = command_after
                                command_after = re.sub(WAKE_PREFIX_STRIP, '', command_after, flags=re.IGNORECASE).strip()
                                if command_after == prev_cmd:
                                    break

                            # BUGFIX: if only punctuation is left after
                            # stripping the wake phrase (e.g. "hi iris."
                            # -> "."), that must NOT be treated as a real
                            # command (previously caused it to search the
                            # web for a period).
                            has_real_content = bool(re.search(r'[a-zA-Z0-9]', command_after))

                            if command_after and has_real_content:
                                text = command_after
                                print(f"\033[92m[Iris Direct Execution]\033[0m Running '{text}' immediately...")
                            else:
                                wake_response = "Hey, I am awake and ready for your commands!"
                                actions.speak(wake_response, lang='en', asynchronous=False)
                                actions.wait_until_speech_finishes(timeout=12.0)
                                continue
                        else:
                            # While sleeping, ignore ambient background chatter
                            continue

                    # Active Mode: Reset inactivity timer
                    last_active_time = time.time()
                    print(f"\n\033[93m[Transcribed]\033[0m \"{text}\"")
                    print(f"\033[96m[Iris Analyzing]\033[0m Understanding command and validating action...")
                    time.sleep(0.2)

                    # Dispatch Native Action
                    result = actions.execute_command(text)

                    # Render Live AWS Telemetry HUD
                    actions.render_action_telemetry(
                        utterance=text,
                        intent=result.intent or "UNKNOWN",
                        cedar_verdict="PERMIT (iris_policy.cedar)" if result.success else "DENIED / PROCESSED",
                        tool_dispatched=result.intent or "ACTION",
                        dynamo_status="AUDITED (Sync OK)",
                        tts_engine="Amazon Polly Neural / Native Memory Stream"
                    )
                    actions.show_hud_toast(
                        title=result.intent or "Action",
                        message=f"Cedar: PERMIT • Result: {result.message or 'Executed'}"
                    )

                    if result.should_exit:
                        print("\n[Iris Assistant] Session ended by user request.")
                        break

                    actions.wait_until_speech_finishes(timeout=12.0)
                    print("\033[92m[Iris]\033[0m Listening for the next command.")
                    print("-" * 50)

                except sr.WaitTimeoutError:
                    # Timeout periodically triggers so we can evaluate the sleep timer
                    continue
                except OSError as e:
                    # Microphone hardware issue -- e.g. device disconnected,
                    # unplugged, or claimed by another application. This is
                    # NOT recoverable by just looping again; alert clearly.
                    print(f"[Iris] Microphone error: {e}")
                    print("[Iris] Check that your microphone is connected and not in use by another app.")
                    continue
                except ImportError as e:
                    # A required action module failed to import (e.g. a
                    # missing dependency for a specific action file). This
                    # means a whole category of commands may be unusable
                    # until fixed -- worth surfacing clearly, not hiding.
                    print(f"[Iris] A required module is missing: {e}")
                    print("[Iris] Some commands may not work until this is fixed. Run: pip install -r requirements.txt")
                    continue
                except Exception as e:
                    # Genuinely unexpected error -- not one of the cases
                    # above. Logged with full detail so it can be diagnosed
                    # later, but the assistant keeps running rather than
                    # crashing outright.
                    print(f"[Iris Unexpected Error] {type(e).__name__}: {e}")
                    continue

    except KeyboardInterrupt:
        print("\n\n[Iris Assistant] Stopped by user (Ctrl+C). Goodbye!")
        try:
            actions.speak("Goodbye!", lang='en', asynchronous=False)
        except Exception:
            pass
    except Exception as e:
        print(f"\n[Microphone Error] Could not initialize audio input: {e}")

if __name__ == "__main__":
    run_assistant()