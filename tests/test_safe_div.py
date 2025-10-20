from app.utils.math import safe_div


def test_safe_div_handles_zero():
    assert safe_div(10, 0) == 0.0


def test_safe_div_precision():
    assert safe_div(1, 3) == 0.33
