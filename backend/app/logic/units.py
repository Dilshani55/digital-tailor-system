"""
Unit conversions used for showing lengths and areas. Calculation is always in centimetres; these exact factors
are only applied when a value is displayed.

    length  1 in = 2.54 cm     1 yd = 36 in = 91.44 cm      1 m = 100 cm
    area    1 m2 = 10 000 cm2  1 yd2 = 1296 in2 = 8361.2736 cm2

A LENGTH of fabric (metres or yards to buy) and an AREA of fabric (square metres or square yards) are different
quantities and are never mixed: buying "2 yards" of 45 in fabric is 2 yd x 1.25 yd = 2.5 square yards.
"""

CM_PER_INCH = 2.54
INCHES_PER_YARD = 36.0
CM_PER_YARD = CM_PER_INCH * INCHES_PER_YARD          # 91.44
CM_PER_METRE = 100.0
CM2_PER_M2 = 10000.0
IN2_PER_YD2 = INCHES_PER_YARD ** 2                   # 1296
CM2_PER_IN2 = CM_PER_INCH ** 2                       # 6.4516
CM2_PER_YD2 = CM2_PER_IN2 * IN2_PER_YD2              # 8361.2736


def cm_to_in(cm):
    return cm / CM_PER_INCH


def in_to_cm(inches):
    return inches * CM_PER_INCH


def cm_to_m(cm):
    return cm / CM_PER_METRE


def cm_to_yd(cm):
    return cm / CM_PER_YARD


def m_to_yd(m):
    return m * CM_PER_METRE / CM_PER_YARD


def cm2_to_m2(cm2):
    return cm2 / CM2_PER_M2


def cm2_to_yd2(cm2):
    return cm2 / CM2_PER_YD2


def cm2_to_in2(cm2):
    return cm2 / CM2_PER_IN2


def in2_to_yd2(in2):
    return in2 / IN2_PER_YD2


def length_text(cm, unit="cm", digits=1):
    """A length in the user's unit, e.g. '25.4 cm' or '10.0 in'."""
    if cm is None:
        return "-"
    return f"{cm_to_in(cm):.{digits}f} in" if unit == "in" else f"{cm:.{digits}f} cm"


def both_lengths(cm, unit="cm", digits=1):
    """The user's unit first, the other one in brackets: '25.4 cm (10.0 in)'."""
    if cm is None:
        return "-"
    a, b = f"{cm:.{digits}f} cm", f"{cm_to_in(cm):.{digits}f} in"
    return f"{b} ({a})" if unit == "in" else f"{a} ({b})"
