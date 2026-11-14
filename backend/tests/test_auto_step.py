import pytest
from pydantic import ValidationError

from app.core.models.test_case import AutoStep, AutoTarget, AutoType, TargetBy, TestStep


def target(by: TargetBy = TargetBy.TEXT, value: str = "Đăng nhập") -> AutoTarget:
    return AutoTarget(by=by, value=value)


def test_click_needs_target() -> None:
    with pytest.raises(ValidationError):
        AutoStep(type=AutoType.CLICK)


@pytest.mark.parametrize("step_type", [AutoType.FILL, AutoType.SELECT])
def test_fill_and_select_need_target(step_type: AutoType) -> None:
    with pytest.raises(ValidationError):
        AutoStep(type=step_type, value="x")


@pytest.mark.parametrize(
    "step_type",
    [AutoType.GOTO, AutoType.SEE_TEXT, AutoType.NOT_SEE_TEXT, AutoType.URL_IS, AutoType.SELECT],
)
def test_types_that_need_value_reject_empty_value(step_type: AutoType) -> None:
    needs_target = step_type == AutoType.SELECT
    with pytest.raises(ValidationError):
        AutoStep(type=step_type, target=target() if needs_target else None, value="")


@pytest.mark.parametrize(
    "step_type", [AutoType.GOTO, AutoType.SEE_TEXT, AutoType.NOT_SEE_TEXT, AutoType.URL_IS]
)
def test_types_without_target_reject_a_target(step_type: AutoType) -> None:
    with pytest.raises(ValidationError):
        AutoStep(type=step_type, target=target(), value="x")


def test_fill_may_have_empty_value() -> None:
    step = AutoStep(type=AutoType.FILL, target=target(TargetBy.LABEL, "Email"))
    assert step.value == ""


def test_click_value_may_be_empty() -> None:
    assert AutoStep(type=AutoType.CLICK, target=target()).value == ""


def test_value_over_500_chars_rejected() -> None:
    with pytest.raises(ValidationError):
        AutoStep(type=AutoType.GOTO, value="x" * 501)


def test_target_value_over_500_chars_rejected() -> None:
    with pytest.raises(ValidationError):
        AutoStep(type=AutoType.CLICK, target=target(value="x" * 501))


def test_old_step_without_auto_loads() -> None:
    step = TestStep(action="a", expected="")
    assert step.auto is None
