"""
Iris Multi-Turn Conversation Context Manager
=============================================
Thread-safe conversation session history that maintains context across turns
(voice wake word, right-click push-to-talk, or text chat) with automatic
inactivity expiration and context resolution support for LLM reasoning.
"""

import time
import threading
from typing import List, Dict, Optional, Any
from collections import deque

# Default contextual freshness window in seconds (2 minutes)
DEFAULT_CONTEXT_TTL_SECONDS = 120.0
MAX_HISTORY_TURNS = 12


class ConversationTurn:
    """Represents a single conversational turn."""
    __slots__ = ("role", "content", "timestamp", "intent", "lang")

    def __init__(
        self,
        role: str,
        content: str,
        timestamp: Optional[float] = None,
        intent: Optional[str] = None,
        lang: str = "en",
    ):
        self.role = role  # 'user' or 'assistant'
        self.content = content
        self.timestamp = timestamp or time.time()
        self.intent = intent
        self.lang = lang

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "intent": self.intent,
            "lang": self.lang,
            "timestamp": self.timestamp,
        }


class ConversationManager:
    """Thread-safe conversation history storage."""

    def __init__(self, max_turns: int = MAX_HISTORY_TURNS, ttl_seconds: float = DEFAULT_CONTEXT_TTL_SECONDS):
        self._turns: deque = deque(maxlen=max_turns)
        self._lock = threading.Lock()
        self._ttl_seconds = ttl_seconds

    def record_user_turn(self, content: str, lang: str = "en") -> None:
        """Record user speech or typed command."""
        if not content or not content.strip():
            return
        with self._lock:
            self._prune_expired()
            self._turns.append(ConversationTurn(role="user", content=content.strip(), lang=lang))

    def record_assistant_turn(self, content: str, intent: Optional[str] = None, lang: str = "en") -> None:
        """Record Iris's spoken or textual response."""
        if not content or not content.strip():
            return
        with self._lock:
            self._prune_expired()
            self._turns.append(ConversationTurn(role="assistant", content=content.strip(), intent=intent, lang=lang))

    def get_history(self, max_turns: int = 6, max_age_seconds: Optional[float] = None) -> List[Dict[str, str]]:
        """
        Returns recent conversational history formatted for LLM messages:
        [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        """
        ttl = max_age_seconds if max_age_seconds is not None else self._ttl_seconds
        now = time.time()
        with self._lock:
            valid_turns = [
                {"role": t.role, "content": t.content}
                for t in self._turns
                if (now - t.timestamp) <= ttl
            ]
            return valid_turns[-max_turns:]

    def clear(self) -> None:
        """Explicitly reset the conversation history."""
        with self._lock:
            self._turns.clear()

    def get_turn_count(self) -> int:
        with self._lock:
            self._prune_expired()
            return len(self._turns)

    def _prune_expired(self) -> None:
        """Remove turns that exceeded the inactivity TTL."""
        if not self._turns:
            return
        now = time.time()
        # If the most recent turn is older than TTL, clear everything
        if now - self._turns[-1].timestamp > self._ttl_seconds:
            self._turns.clear()
            return
        while self._turns and (now - self._turns[0].timestamp > self._ttl_seconds):
            self._turns.popleft()


# Global singleton instance for use across executor, planner, and bridge
_conversation_manager = ConversationManager()


def get_conversation_manager() -> ConversationManager:
    return _conversation_manager


def record_user_turn(content: str, lang: str = "en") -> None:
    _conversation_manager.record_user_turn(content, lang=lang)


def record_assistant_turn(content: str, intent: Optional[str] = None, lang: str = "en") -> None:
    _conversation_manager.record_assistant_turn(content, intent=intent, lang=lang)


def get_history(max_turns: int = 6, max_age_seconds: Optional[float] = None) -> List[Dict[str, str]]:
    return _conversation_manager.get_history(max_turns=max_turns, max_age_seconds=max_age_seconds)


def clear_history() -> None:
    _conversation_manager.clear()
