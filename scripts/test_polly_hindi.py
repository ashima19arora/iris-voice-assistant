import os
import sys
import boto3
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()
region = os.getenv("AWS_DEFAULT_REGION", "eu-north-1")
polly = boto3.client("polly", region_name=region)

print(f"Checking Amazon Polly voices in {region}...")
res = polly.describe_voices()
voices = res.get("Voices", [])

print("\n--- Hindi / Indian Voices Found ---")
found = 0
for v in voices:
    lang_code = v.get("LanguageCode", "")
    additional = v.get("AdditionalLanguageCodes", [])
    if "hi-IN" in lang_code or "hi-IN" in additional or "en-IN" in lang_code:
        found += 1
        print(f"ID: {v['Id']:<10} | Name: {v.get('Name', v['Id']):<10} | Primary: {lang_code:<8} | Engines: {v.get('SupportedEngines')} | Extra: {additional}")

print(f"Total Indian/Hindi voices: {found}")

# Test synthesis in Hindi using Aditi / Kajal
test_text_hindi = "नमस्ते, मैं आईरिस हूँ। आपकी सहायता के लिए तैयार हूँ।"
print(f"\nSynthesizing test Hindi speech: '{test_text_hindi}'...")

for voice_id in ["Aditi", "Kajal"]:
    try:
        synth = polly.synthesize_speech(
            Text=test_text_hindi,
            OutputFormat="mp3",
            VoiceId=voice_id,
            Engine="neural" if "neural" in [e for v in voices if v["Id"] == voice_id for e in v.get("SupportedEngines", [])] else "standard"
        )
        audio = synth["AudioStream"].read()
        print(f"✓ [{voice_id}] Successfully synthesized Hindi audio ({len(audio)} bytes)!")
    except Exception as e:
        print(f"✗ [{voice_id}] Synthesis error: {e}")
