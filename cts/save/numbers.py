import math


def normalize_to_owned_exp(value: str) -> tuple[float, int]:
    text = value.strip()
    if "e" in text.lower():
        mant_str, exp_str = text.lower().split("e", 1)
        mant = float(mant_str)
        exp = int(exp_str)
    else:
        mant = float(text)
        exp = 0

    if mant == 0.0:
        return 0.0, 0

    sign = -1.0 if mant < 0 else 1.0
    mant = abs(mant)
    while mant >= 10.0:
        mant /= 10.0
        exp += 1
    while mant < 1.0:
        mant *= 10.0
        exp -= 1
    return sign * mant, exp


def owned_exp_to_decimal(owned: float, exp: int) -> str:
    if owned == 0.0:
        return "0"
    if not math.isfinite(owned):
        return str(owned)
    if exp > 300 or exp < -300:
        return f"{owned:.12g}e{exp}"

    try:
        value = owned * (10.0**exp)
    except OverflowError:
        return f"{owned:.12g}e{exp}"

    if not math.isfinite(value) or value == 0.0:
        return f"{owned:.12g}e{exp}"
    if 1e-6 <= abs(value) < 1e16:
        if abs(value - round(value)) < 1e-9:
            return str(int(round(value)))
        return f"{value:.12g}"
    return f"{owned:.12g}e{exp}"
