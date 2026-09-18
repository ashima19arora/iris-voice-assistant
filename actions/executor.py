"""Two-tier command executor: regex fast path, then planner."""
from __future__ import annotations

import logging
from typing import Callable, Optional

from .config import FAST_PATH_MIN_CONFIDENCE, TIER2_ALWAYS_INTENTS
from .context_provider import gather_context
from .feedback import speak, notify
from .intent_parser import parse_intent, Intent
from .planner import PlannerFailure, run_planner
from .registry import ActionResult, INTENT_HANDLERS

logger = logging.getLogger("iris")

TIER2_CUE = "Let me check that."


def should_use_reasoning_path(intent: Intent) -> bool:
    if intent.name in TIER2_ALWAYS_INTENTS:
        return True
    if intent.name == "UNKNOWN":
        return True
    if intent.confidence < FAST_PATH_MIN_CONFIDENCE:
        return True
    return False


def route_utterance(transcription: str) -> dict:
    intent = parse_intent(transcription)
    tier = 2 if should_use_reasoning_path(intent) else 1
    return {
        "utterance": transcription,
        "intent": intent.name,
        "confidence": intent.confidence,
        "tier": tier,
    }


def _fast_path(transcription: str, intent: Intent, lang: str) -> ActionResult:
    logger.info("fast-path hit intent=%s confidence=%.3f", intent.name, intent.confidence)
    from .security import verify_action_security
    from .languages import get_localized_message

    is_allowed, risk_tier, sanitized_params, reason = verify_action_security(transcription, intent)
    sanitized_params["_lang"] = lang
    if not is_allowed:
        if risk_tier == "FORBIDDEN":
            notify(f"Security Alert: {reason}", success=False)
            speak(get_localized_message("SECURITY_BLOCKED", lang), lang=lang)
            return ActionResult(False, "SECURITY_BLOCKED", reason)
        notify(f"No matching action found for: '{transcription}'", success=False)
        speak(get_localized_message("UNKNOWN", lang), lang=lang)
        return ActionResult(False, "UNKNOWN", f"Unrecognized command: {transcription}")

    handler = INTENT_HANDLERS.get(intent.name)
    if not handler:
        return ActionResult(False, intent.name, f"Handler missing for {intent.name}")
    try:
        return handler(sanitized_params)
    except Exception as exc:
        logger.error("fast-path execution failed: %s", exc)
        notify(f"Error executing {intent.name}: {exc}", success=False)
        return ActionResult(False, intent.name, f"Execution error: {exc}")


def _reasoning_path(
    transcription: str,
    intent: Intent,
    lang: str,
    *,
    confirm_fn: Optional[Callable] = None,
    complete_fn: Optional[Callable] = None,
    gather_fn: Optional[Callable] = None,
) -> ActionResult:
    logger.info("reasoning-path hit intent=%s confidence=%.3f", intent.name, intent.confidence)
    # Cue MUST fire before the blocking LLM call.
    speak(TIER2_CUE, lang=lang)
    gather = gather_fn or (lambda **k: gather_context(lang=lang, utterance=transcription, speak_errors=False))
    context = gather(lang=lang) if gather_fn else gather_context(lang=lang, utterance=transcription, speak_errors=False)
    try:
        kwargs = {"confirm_fn": confirm_fn or (lambda *a, **k: True), "lang": lang}
        if complete_fn is not None:
            kwargs["complete_fn"] = complete_fn
        plan = run_planner(transcription, context, **kwargs)
    except PlannerFailure as exc:
        logger.error("planner failure %s: %s", exc.kind, exc.spoken)
        speak(exc.spoken, lang=lang)
        return ActionResult(False, "PLANNER_" + exc.kind.upper(), exc.spoken)

    lines = []
    for step in plan.get("steps") or []:
        status = "succeeded" if step.get("ok") else "failed"
        err = step.get("error") or ""
        lines.append(f"step {step.get('index')} {step.get('tool')} {status}{(': ' + err) if err else ''}")
        if step.get("ok"):
            logger.info("tool step ok: %s", step)
        else:
            logger.error("tool step failed: %s", step)
    summary = plan.get("spoken") or "Done."
    if lines:
        summary = summary + " " + "; ".join(lines)
        notify("; ".join(lines), success=plan.get("ok", True))
    already_spoke = any(
        step.get("tool") == "knowledge_answer" and step.get("ok")
        for step in (plan.get("steps") or [])
    )
    if not already_spoke:
        speak(plan.get("spoken") or "Done.", lang=lang)
    return ActionResult(bool(plan.get("ok")), intent.name, summary)


def execute_command(
    transcription: str,
    *,
    confirm_fn: Optional[Callable] = None,
    complete_fn: Optional[Callable] = None,
    gather_fn: Optional[Callable] = None,
) -> ActionResult:
    from .languages import detect_language

    user_lang = detect_language(transcription)
    intent = parse_intent(transcription)
    if should_use_reasoning_path(intent):
        return _reasoning_path(
            transcription,
            intent,
            user_lang,
            confirm_fn=confirm_fn,
            complete_fn=complete_fn,
            gather_fn=gather_fn,
        )
    return _fast_path(transcription, intent, user_lang)
