def phase_voltage_to_duty(phase_voltage):
    """
    Convert normalized phase voltage to ideal PWM duty cycle.

    Input:
        phase_voltage
            Normalized phase voltage.
            Expected range: -1.0 ... +1.0

    Output:
        duty
            Normalized PWM duty cycle.
            Range: 0.0 ... 1.0
    """

    return (
        1.0 + phase_voltage
    ) / 2.0


def calculate_pwm_duties(phase_voltages):
    """
    Convert all phase voltages to ideal PWM duty cycles.
    """

    return [
        phase_voltage_to_duty(voltage)
        for voltage in phase_voltages
    ]


def calculate_center_aligned_edges(duty):
    """
    Calculate the switching positions of an ideal
    center-aligned PWM pulse.

    PWM period is normalized to:

        0.0 ... 1.0

    The HIGH pulse is centered at 0.5.

    Example:

        duty = 0.50

        turn_on  = 0.25
        turn_off = 0.75
    """

    turn_on = (
        1.0 - duty
    ) / 2.0

    turn_off = (
        1.0 + duty
    ) / 2.0

    return (
        turn_on,
        turn_off,
    )


def center_aligned_pwm_state(
    normalized_time,
    duty,
):
    """
    Calculate ideal center-aligned PWM logic state
    at one normalized time position.

    normalized_time:
        Position inside one PWM period.
        Range: 0.0 ... 1.0

    duty:
        Normalized duty cycle.
        Range: 0.0 ... 1.0

    Returns:
        0 or 1
    """

    turn_on, turn_off = (
        calculate_center_aligned_edges(
            duty
        )
    )

    if (
        normalized_time >= turn_on
        and
        normalized_time < turn_off
    ):
        return 1

    return 0


def generate_center_aligned_pwm(
    duty,
    samples=2000,
):
    """
    Generate one complete ideal center-aligned
    PWM period.

    Returns:

        normalized_time
            List from 0.0 to 1.0

        pwm_output
            Corresponding PWM logic states
            containing 0 or 1
    """

    normalized_time = []
    pwm_output = []

    for sample in range(
        samples + 1
    ):

        time_position = (
            sample / samples
        )

        pwm_state = (
            center_aligned_pwm_state(
                time_position,
                duty,
            )
        )

        normalized_time.append(
            time_position
        )

        pwm_output.append(
            pwm_state
        )

    return (
        normalized_time,
        pwm_output,
    )