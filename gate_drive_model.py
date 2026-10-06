# ============================================================
# Gate-drive model
#
# This module converts PWM commands into High-side and
# Low-side gate-drive signals.
#
# Two models are provided:
#
# 1. Ideal complementary gate drive
#
#       High = PWM
#       Low  = NOT PWM
#
# 2. Complementary gate drive with deadtime
#
#       Turn-OFF:
#           immediate
#
#       Turn-ON:
#           delayed by the specified deadtime
#
# Deadtime is represented directly in physical time.
# ============================================================


# ============================================================
# Ideal complementary gate drive
# ============================================================

def pwm_to_complementary_gates(
    pwm_state,
):
    """
    Convert one PWM logic state into ideal complementary
    High-side and Low-side gate states.

    Deadtime is NOT included.
    """

    high_gate = pwm_state

    low_gate = (
        1 - pwm_state
    )

    return (
        high_gate,
        low_gate,
    )


def generate_complementary_gates(
    pwm_output,
):
    """
    Convert a complete PWM waveform into ideal complementary
    High-side and Low-side gate waveforms.

    Deadtime is NOT included.
    """

    high_gate_output = []

    low_gate_output = []

    for pwm_state in pwm_output:

        high_gate, low_gate = (
            pwm_to_complementary_gates(
                pwm_state
            )
        )

        high_gate_output.append(
            high_gate
        )

        low_gate_output.append(
            low_gate
        )

    return (
        high_gate_output,
        low_gate_output,
    )


# ============================================================
# Deadtime edge calculation
# ============================================================

def calculate_deadtime_gate_edges(
    pwm_turn_on_us,
    pwm_turn_off_us,
    deadtime_lh_ns,
    deadtime_hl_ns,
):
    """
    Calculate exact physical switching times for one
    center-aligned PWM pulse with deadtime.

    Parameters
    ----------
    pwm_turn_on_us:
        Ideal PWM rising-edge time in microseconds.

    pwm_turn_off_us:
        Ideal PWM falling-edge time in microseconds.

    deadtime_lh_ns:
        Low -> High deadtime in nanoseconds.

    deadtime_hl_ns:
        High -> Low deadtime in nanoseconds.


    Switching rule
    --------------

    PWM rising edge:

        Low OFF:
            immediately at pwm_turn_on_us

        High ON:
            pwm_turn_on_us + DEADTIME_LH


    PWM falling edge:

        High OFF:
            immediately at pwm_turn_off_us

        Low ON:
            pwm_turn_off_us + DEADTIME_HL
    """

    deadtime_lh_us = (
        deadtime_lh_ns / 1000.0
    )

    deadtime_hl_us = (
        deadtime_hl_ns / 1000.0
    )


    low_turn_off_us = (
        pwm_turn_on_us
    )

    high_turn_on_us = (
        pwm_turn_on_us
        + deadtime_lh_us
    )


    high_turn_off_us = (
        pwm_turn_off_us
    )

    low_turn_on_us = (
        pwm_turn_off_us
        + deadtime_hl_us
    )


    return {
        "low_turn_off_us":
            low_turn_off_us,

        "high_turn_on_us":
            high_turn_on_us,

        "high_turn_off_us":
            high_turn_off_us,

        "low_turn_on_us":
            low_turn_on_us,
    }


# ============================================================
# Continuous-time gate-state model
# ============================================================

def gate_states_with_deadtime(
    time_us,
    gate_edges,
):
    """
    Calculate High-side and Low-side gate states at an
    arbitrary physical time.

    This function does NOT depend on Python simulation
    sample spacing.

    The switching-event positions are defined directly
    in physical time.
    """

    low_turn_off_us = (
        gate_edges[
            "low_turn_off_us"
        ]
    )

    high_turn_on_us = (
        gate_edges[
            "high_turn_on_us"
        ]
    )

    high_turn_off_us = (
        gate_edges[
            "high_turn_off_us"
        ]
    )

    low_turn_on_us = (
        gate_edges[
            "low_turn_on_us"
        ]
    )


    # --------------------------------------------------------
    # High-side gate
    # --------------------------------------------------------

    if (
        time_us >= high_turn_on_us
        and
        time_us < high_turn_off_us
    ):
        high_gate = 1

    else:
        high_gate = 0


    # --------------------------------------------------------
    # Low-side gate
    #
    # For this single center-aligned PWM period:
    #
    # Low is ON before the PWM rising edge.
    #
    # Low turns OFF immediately at the rising edge.
    #
    # After the PWM falling edge, Low turns ON only after
    # DEADTIME_HL has elapsed.
    # --------------------------------------------------------

    if time_us < low_turn_off_us:

        low_gate = 1

    elif time_us >= low_turn_on_us:

        low_gate = 1

    else:

        low_gate = 0


    return (
        high_gate,
        low_gate,
    )