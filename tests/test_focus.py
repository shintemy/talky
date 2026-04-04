from talky.focus import FrontAppInfo, _ax_get_attr, has_focus_target


def test_has_focus_target_false_for_desktop_apps() -> None:
    assert not has_focus_target(FrontAppInfo(name="Finder", pid=100))
    assert not has_focus_target(FrontAppInfo(name="Dock", pid=101))
    assert not has_focus_target(FrontAppInfo(name="loginwindow", pid=102))


def test_has_focus_target_false_for_invalid_pid() -> None:
    assert not has_focus_target(FrontAppInfo(name="Safari", pid=0))
    assert not has_focus_target(FrontAppInfo(name="Safari", pid=-1))
    assert not has_focus_target(None)


def test_has_focus_target_true_for_normal_apps() -> None:
    assert has_focus_target(FrontAppInfo(name="Safari", pid=200))
    assert has_focus_target(FrontAppInfo(name="Chrome", pid=201))
    assert has_focus_target(FrontAppInfo(name="Terminal", pid=202))
    assert has_focus_target(FrontAppInfo(name="Cursor", pid=203))


def test_ax_get_attr_success_returns_value() -> None:
    def _copy_func(*args):
        if len(args) == 2:
            return (0, "focused_element")
        return 0

    assert _ax_get_attr(_copy_func, object(), "AXFocusedUIElement") == "focused_element"


def test_ax_get_attr_error_returns_none() -> None:
    def _copy_func(*args):
        if len(args) == 2:
            raise TypeError
        return (-25205, None)

    assert _ax_get_attr(_copy_func, object(), "AXEditable") is None


def test_ax_get_attr_3arg_success() -> None:
    def _copy_func(*args):
        if len(args) == 2:
            raise TypeError
        return (0, "value")

    assert _ax_get_attr(_copy_func, object(), "AXRole") == "value"
