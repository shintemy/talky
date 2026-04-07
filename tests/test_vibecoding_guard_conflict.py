"""First-principles tests: Vibecoding mode vs post-processing guards.

The text guards in text_guard.py are designed for Chinese→Chinese cleaning.
When Vibecoding mode forces English output (Chinese→English), the controller
must SKIP these guards to avoid false reverts.

Guard-level tests below document the inherent incompatibility.
Controller-level bypass is tested separately in test_vibecoding_pipeline.py.
"""

import pytest

from talky.text_guard import (
    collapse_duplicate_output,
    enforce_pronoun_consistency,
    enforce_source_boundaries,
)


# ---------------------------------------------------------------------------
# Guard-level: these document known incompatibilities (not bugs in guard itself)
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason="Guard is Chinese-only; vibecoding English output triggers false revert. "
    "Controller bypasses this guard in vibecoding mode.",
    strict=True,
)
def test_guard_question_type_conflict_with_vibecoding() -> None:
    """enforce_source_boundaries reverts when non-question source → English
    question output.  This is expected behavior for the guard itself;
    the controller must skip it in vibecoding mode."""
    source = "检查一下这个代码有什么问题"
    output = "What issues exist in this code?"

    result = enforce_source_boundaries(source, output)
    assert result == output


@pytest.mark.xfail(
    reason="'consider' advisory marker false positive on English vibecoding output. "
    "Controller bypasses this guard in vibecoding mode.",
    strict=True,
)
def test_guard_consider_advisory_conflict_with_vibecoding() -> None:
    source = "我觉得可以考虑用 Redis 来做缓存"
    output = "Consider using Redis for caching layer."

    result = enforce_source_boundaries(source, output)
    assert result == output


@pytest.mark.xfail(
    reason="'you should' advisory marker false positive on English output. "
    "Controller bypasses this guard in vibecoding mode.",
    strict=True,
)
def test_guard_you_should_conflict_with_vibecoding() -> None:
    source = "你应该先把测试跑一遍"
    output = "You should run the full test suite first."

    result = enforce_source_boundaries(source, output)
    assert result == output


# ---------------------------------------------------------------------------
# Guard-level: behaviors that are correct even for vibecoding
# ---------------------------------------------------------------------------


def test_pronoun_guard_noop_on_english_output() -> None:
    """Pronoun guard uses Chinese chars; English output is unaffected."""
    source = "我需要你帮我检查代码"
    output = "Review the code for me."

    assert enforce_pronoun_consistency(source, output) == output


def test_collapse_works_on_english_vibecoding_output() -> None:
    """Deduplication is language-agnostic."""
    text = "Refactor auth module.\nRefactor auth module.\n"

    assert collapse_duplicate_output(text) == "Refactor auth module."


def test_guard_faithful_statement_passes() -> None:
    """Statement→statement is fine even in cross-language scenario."""
    source = "把这个接口改成异步的"
    output = "Refactor this API to async."

    assert enforce_source_boundaries(source, output) == output
