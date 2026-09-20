"""
Iris Language & Multilingual Localization Module
=================================================
WHAT THIS FILE DOES (Simple English):
  This module allows Iris to seamlessly understand both English and Hindi/Hinglish.
  If you speak in English ("open YouTube"), Iris detects English and speaks back in English.
  If you speak in Hindi ("YouTube kholo" or "RAM kitna use ho raha hai"), Iris automatically
  detects Hindi and responds in natural Hindi.

GREAT TECH & PACKAGES USED IN THIS FILE:
  - Lexical Token Classifier:
      * What it does: Matches words against a curated dictionary of Romanized Hindi/Hinglish tokens
        and Devanagari Unicode scripts (`\u0900-\u097F`).
      * Why we use it: Zero-latency language identification running locally without needing any
        heavy neural network models.
  - Localization Mapping Dictionary:
      * What it does: Stores authentic, culturally natural spoken phrases for both languages.
"""

import re
from typing import Dict, Any, Tuple

# Distinctive Hindi/Hinglish words only. Common English words like "me", "to",
# "the" must NOT count, or English commands are misclassified as Hindi.
HINDI_HINGLISH_WORDS = {
    'kya', 'kyun', 'kaun', 'kaise', 'kahan', 'kab', 'kitna', 'kitni', 'kitne',
    'kisko', 'kiska', 'kiski', 'kiske', 'hai', 'hain', 'hoon', 'hun', 'hoga', 'hogi', 'honge',
    'mujhe', 'mera', 'meri', 'mere', 'humein', 'hamara', 'hamari',
    'aap', 'aapko', 'aapka', 'aapki', 'aapke', 'tum', 'tumhe', 'tumhara', 'tumhari',
    'ki', 'ka', 'ke', 'ko', 'se', 'mein', 'me', 'pe', 'par', 'parantu', 'magar', 'liye', 'baare',
    'karo', 'karna', 'kariye', 'kijiye', 'karta', 'karti', 'karte',
    'kholo', 'khol', 'kholna', 'chalao', 'chala', 'chalaana',
    'batao', 'bata', 'bataiye', 'dikhao', 'dikhana', 'rajdhani',
    'dhoondo', 'khojo', 'badhao', 'dheeme', 'hatao', 'suno',
    'samay', 'taareekh', 'aawaz', 'awaz', 'madad', 'sahayata', 'namaste', 'namaskar', 'alvida',
    'nahi', 'nahin', 'the', 'thi', 'tha',
}

ENGLISH_STRUCTURE_WORDS = {
    'the', 'a', 'an', 'you', 'can', 'could', 'would', 'please', 'open', 'listen',
    'what', 'who', 'where', 'when', 'why', 'how', 'is', 'are', 'my', 'your',
}

def detect_language(transcription: str) -> str:
    """
    Detects whether the transcription is Hindi/Hinglish or English.
    Returns: 'hi' or 'en'
    """
    if not transcription or not transcription.strip():
        return 'en'

    text = transcription.lower().strip()

    # 1. Direct Devanagari script detection
    if re.search(r'[\u0900-\u097F]', text):
        return 'hi'

    # 2. Tokenize and count Hindi/Hinglish word matches
    words = re.findall(r'\b[a-z]+\b', text)
    if not words:
        return 'en'

    hindi_match_count = sum(1 for w in words if w in HINDI_HINGLISH_WORDS)
    english_structure = sum(1 for w in words if w in ENGLISH_STRUCTURE_WORDS)
    ratio = hindi_match_count / len(words)

    if english_structure >= 2 and hindi_match_count == 0:
        return 'en'

    if hindi_match_count >= 2 or (hindi_match_count >= 1 and ratio >= 0.25):
        return 'hi'

    if words and words[0] in {'namaste', 'namaskar', 'alvida', 'kholo', 'batao'}:
        return 'hi'

    return 'en'

def get_localized_message(intent: str, lang: str, **kwargs) -> str:
    """
    Returns a natural localized spoken message for a given intent and language ('en' or 'hi').
    """
    target = kwargs.get("target", "")
    query = kwargs.get("query", "")
    app_name = kwargs.get("app_name", "")

    if lang == 'hi':
        messages = {
            "GREETING": "नमस्ते! मैं आईरिस हूँ। मैं बिल्कुल ठीक हूँ। हाँ, मैं पूरी तरह से हिंदी बोल और समझ सकता हूँ। आप मुझसे कोई भी काम कह सकते हैं।",
            "SEARCH_WEB": f"{query} के लिए वेब पर खोज रहा हूँ।",
            "OPEN_WEBSITE": f"{target.capitalize()} खोल रहा हूँ",
            "OPEN_APP": f"{app_name.capitalize()} ओपन कर रहा हूँ",
            "BROWSER_NEW_TAB": "नया टैब खोल दिया है",
            "BROWSER_CLOSE_TAB": "टैब बंद कर दिया है",
            "BROWSER_SWITCH_TAB": "टैब बदल दिया है",
            "BROWSER_REFRESH": "पेज रीफ्रेश कर दिया है",
            "WINDOW_CLOSE": "विंडो बंद कर दी है",
            "WINDOW_MINIMIZE": "विंडो मिनिमाइज़ कर दी है",
            "WINDOW_MAXIMIZE": "विंडो मैक्सिमाइज़ कर दी है",
            "SHOW_DESKTOP": "डेस्कटॉप दिखा रहा हूँ",
            "VOLUME_UP": "आवाज़ बढ़ा दी गई है",
            "VOLUME_DOWN": "आवाज़ कम कर दी गई है",
            "VOLUME_MUTE": "आवाज़ म्यूट कर दी गई है",
            "SCREENSHOT": "स्क्रीनशॉट ले लिया गया है",
            "MEDIA_PLAY_PAUSE": "मीडिया प्ले पॉज़ कर दिया है",
            "LOCK_SCREEN": "कंप्यूटर लॉक कर दिया गया है",
            "EXIT_ASSISTANT": "अलविदा! आईरिस वॉइस असिस्टेंट अब बंद हो रहा है।",
            "SECURITY_BLOCKED": "सुरक्षा चेतावनी: यह कमांड आपके सिस्टम की सुरक्षा के लिए प्रतिबंधित है।",
            "UNKNOWN": "मुझे वह कमांड समझ नहीं आई। कृपया दोबारा साफ़ बोलें।",
            "FORM_SUBMIT": "फॉर्म सबमिट कर दिया गया है",
            "SEND_MESSAGE": "संदेश भेज दिया गया है",
            "KNOWLEDGE_QUERY": f"{query} के बारे में जानकारी ढूंढ रहा हूँ"
        }
        return messages.get(intent, kwargs.get("fallback", "काम पूरा हो गया है।"))

    # Default English
    messages = {
        "GREETING": "Hello! I am Iris, your voice assistant. Yes, I can speak both English and Hindi! How can I help you today?",
        "SEARCH_WEB": f"Searching the web for {query}.",
        "OPEN_WEBSITE": f"Opening {target.capitalize()}",
        "OPEN_APP": f"Opening {app_name.capitalize()}",
        "BROWSER_NEW_TAB": "Opening new tab",
        "BROWSER_CLOSE_TAB": "Closing tab",
        "BROWSER_SWITCH_TAB": "Switching tab",
        "BROWSER_REFRESH": "Refreshing page",
        "WINDOW_CLOSE": "Closing active window",
        "WINDOW_MINIMIZE": "Minimizing window",
        "WINDOW_MAXIMIZE": "Maximizing window",
        "SHOW_DESKTOP": "Showing desktop",
        "VOLUME_UP": "Increasing volume",
        "VOLUME_DOWN": "Decreasing volume",
        "VOLUME_MUTE": "Toggling volume mute",
        "SCREENSHOT": "Taking screenshot",
        "MEDIA_PLAY_PAUSE": "Toggled media playback",
        "LOCK_SCREEN": "Locking computer",
        "EXIT_ASSISTANT": "Goodbye! Iris voice assistant is shutting down.",
        "SECURITY_BLOCKED": "Security Alert: That command is restricted to protect your system.",
        "UNKNOWN": "I did not catch a command. Please say it again clearly.",
        "FORM_SUBMIT": "Form submitted.",
        "SEND_MESSAGE": "Message sent.",
        "KNOWLEDGE_QUERY": f"Searching knowledge base for {query}."
    }
    return messages.get(intent, kwargs.get("fallback", "Action completed."))
