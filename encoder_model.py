from config import (
    LM10_COUNTS,
    POLE_PAIRS,
    ENCODER_OFFSET,
    ELECTRICAL_DIRECTION,
)


def encoder_to_mechanical_angle(phi):
    return phi / LM10_COUNTS * 360.0


def encoder_to_relative_mechanical_angle(phi):
    relative_count = (phi - ENCODER_OFFSET) % LM10_COUNTS
    return relative_count / LM10_COUNTS * 360.0


def mechanical_to_electrical_angle(theta_m_deg):
    return (
        ELECTRICAL_DIRECTION
        * POLE_PAIRS
        * theta_m_deg
    ) % 360.0