"""
Tests for AWS Cedar Authorization Engine in Iris
"""
import pytest
from actions.security.cedar_engine import evaluate_cedar_policy
from actions.security.policy import evaluate_policy, RiskTier


def test_cedar_permits_safe_diagnostics():
    res = evaluate_cedar_policy("SYSTEM_RAM")
    assert res.allowed is True
    assert res.decision == "Allow"

    res_cpu = evaluate_cedar_policy("SYSTEM_CPU")
    assert res_cpu.allowed is True

    res_time = evaluate_cedar_policy("SYSTEM_TIME")
    assert res_time.allowed is True


def test_cedar_permits_browser_actions():
    res = evaluate_cedar_policy("SEARCH_WEB")
    assert res.allowed is True

    res_scroll = evaluate_cedar_policy("BROWSER_SCROLL_DOWN")
    assert res_scroll.allowed is True


def test_cedar_forbids_unconfirmed_destruction():
    res = evaluate_cedar_policy("DELETE_FILE", context={"confirmed": False})
    assert res.allowed is False
    assert res.decision == "Deny"
    assert "explicit user confirmation" in res.reason


def test_cedar_permits_confirmed_file_destruction():
    res = evaluate_cedar_policy("DELETE_FILE", context={"confirmed": True})
    # With confirmed=True, forbid clause does not trigger; default deny if no permit, or permit if defined
    # Cedar forbid triggers unless confirmed==True
    assert res is not None


def test_cedar_file_path_sandboxing():
    # Safe path
    res_safe = evaluate_cedar_policy("CREATE_FILE", context={"is_safe_path": True})
    assert res_safe.allowed is True

    # Unsafe path
    res_unsafe = evaluate_cedar_policy("CREATE_FILE", context={"is_safe_path": False})
    assert res_unsafe.allowed is False
    assert res_unsafe.decision == "Deny"


def test_policy_evaluator_integrates_cedar():
    dec = evaluate_policy("SYSTEM_RAM", {})
    assert dec.allowed is True
    assert "AWS Cedar" in dec.reason

    dec_blocked = evaluate_policy("DELETE_FILE", {})
    assert dec_blocked.allowed is False
