"""Numbers as Ukrainian text: 12 345,6 (no-break space groups, decimal comma)."""

GROUP_SEPARATOR = " "


def number(value: float, decimals: int = 0) -> str:
    text = f"{value:,.{decimals}f}"
    return text.replace(",", GROUP_SEPARATOR).replace(".", ",")


def percent(fraction: float, decimals: int = 1) -> str:
    return f"{number(fraction * 100, decimals)}{GROUP_SEPARATOR}%"


def decimals_for(value: float, fractional: int = 1) -> int:
    """0 for whole numbers, `fractional` otherwise."""
    return 0 if float(value).is_integer() else fractional
