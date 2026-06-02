from __future__ import annotations

from talky.hotkey import SECONDARY_CHORD, evaluate


def test_secondary_chord_is_ctrl_shift_alt() -> None:
    assert SECONDARY_CHORD == frozenset({"ctrl", "shift", "alt"})


def test_rising_edge_fires_press_once() -> None:
    conditions = [{"fn"}, set(SECONDARY_CHORD)]
    pressed, fire_press, fire_release = evaluate(conditions, {"fn"}, False)
    assert (pressed, fire_press, fire_release) == (True, True, False)


def test_held_state_does_not_refire() -> None:
    conditions = [{"fn"}, set(SECONDARY_CHORD)]
    pressed, fire_press, fire_release = evaluate(conditions, {"fn"}, True)
    assert (pressed, fire_press, fire_release) == (True, False, False)


def test_falling_edge_fires_release_once() -> None:
    conditions = [{"fn"}, set(SECONDARY_CHORD)]
    pressed, fire_press, fire_release = evaluate(conditions, set(), True)
    assert (pressed, fire_press, fire_release) == (False, False, True)


def test_or_semantics_secondary_condition_matches() -> None:
    conditions = [{"fn"}, set(SECONDARY_CHORD)]
    # Fn not held, but the full chord is -> pressed via the secondary condition.
    pressed, fire_press, _ = evaluate(conditions, {"ctrl", "shift", "alt"}, False)
    assert pressed is True
    assert fire_press is True


def test_partial_chord_does_not_match() -> None:
    conditions = [{"fn"}, set(SECONDARY_CHORD)]
    # Only ctrl+shift (missing alt) -> no condition satisfied.
    pressed, _, _ = evaluate(conditions, {"ctrl", "shift"}, False)
    assert pressed is False


def test_overlap_stays_pressed_when_one_of_two_releases() -> None:
    conditions = [{"fn"}, set(SECONDARY_CHORD)]
    # Holding Fn AND chord, then Fn releases but chord remains -> still pressed.
    pressed, fire_press, fire_release = evaluate(
        conditions, {"ctrl", "shift", "alt"}, True
    )
    assert (pressed, fire_press, fire_release) == (True, False, False)


def test_empty_conditions_never_fires() -> None:
    pressed, fire_press, fire_release = evaluate([], {"ctrl", "shift", "alt"}, False)
    assert (pressed, fire_press, fire_release) == (False, False, False)
