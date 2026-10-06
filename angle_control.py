from config import (
    NUM_PHASES,
    TORQUE_DIRECTION,
    PHASE_ADVANCE_DEG,
)


def electrical_to_voltage_angle(theta_e_deg):
    return (
        theta_e_deg
        + TORQUE_DIRECTION * 90.0
    ) % 360.0


def apply_phase_advance(theta_v_deg):
    return (
        theta_v_deg
        + TORQUE_DIRECTION * PHASE_ADVANCE_DEG
    ) % 360.0


def generate_phase_angles(theta_control_deg):
    phase_step_deg = 360.0 / NUM_PHASES

    return [
        (theta_control_deg - i * phase_step_deg) % 360.0
        for i in range(NUM_PHASES)
    ]