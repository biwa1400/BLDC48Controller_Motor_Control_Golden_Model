import math

from config import VOLTAGE_AMPLITUDE


def calculate_phase_sines(phase_angles_deg):
    return [
        math.sin(math.radians(angle))
        for angle in phase_angles_deg
    ]


def calculate_phase_voltages(phase_sines):
    return [
        VOLTAGE_AMPLITUDE * sine_value
        for sine_value in phase_sines
    ]