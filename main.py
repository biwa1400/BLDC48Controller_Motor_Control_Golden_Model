from config import (
    PHASE_ADVANCE_DEG,
    VOLTAGE_AMPLITUDE,
)

from encoder_model import (
    encoder_to_mechanical_angle,
    encoder_to_relative_mechanical_angle,
    mechanical_to_electrical_angle,
)

from angle_control import (
    electrical_to_voltage_angle,
    apply_phase_advance,
    generate_phase_angles,
)

from modulation import (
    calculate_phase_sines,
    calculate_phase_voltages,
)

from pwm_model import calculate_pwm_duties


phi = 1024


theta_m_deg = encoder_to_mechanical_angle(phi)

theta_m_relative_deg = (
    encoder_to_relative_mechanical_angle(phi)
)

theta_e_deg = mechanical_to_electrical_angle(
    theta_m_relative_deg
)

theta_v_deg = electrical_to_voltage_angle(
    theta_e_deg
)

theta_control_deg = apply_phase_advance(
    theta_v_deg
)

phase_angles_deg = generate_phase_angles(
    theta_control_deg
)

phase_sines = calculate_phase_sines(
    phase_angles_deg
)

phase_voltages = calculate_phase_voltages(
    phase_sines
)

pwm_duties = calculate_pwm_duties(
    phase_voltages
)


print("Encoder count:", phi)
print("Raw mechanical angle:", theta_m_deg, "deg")
print(
    "Relative mechanical angle:",
    theta_m_relative_deg,
    "deg",
)
print("Electrical angle:", theta_e_deg, "deg")
print("Voltage vector angle:", theta_v_deg, "deg")
print("Phase advance:", PHASE_ADVANCE_DEG, "deg")
print("Final control angle:", theta_control_deg, "deg")

print()

print(
    "Normalized voltage amplitude:",
    VOLTAGE_AMPLITUDE,
)

print()

print("22 phase values:")

for i, (
    angle,
    sine_value,
    voltage,
    duty,
) in enumerate(
    zip(
        phase_angles_deg,
        phase_sines,
        phase_voltages,
        pwm_duties,
    ),
    start=1,
):
    print(
        f"Phase {i:2d}: "
        f"angle = {angle:10.6f} deg, "
        f"sin = {sine_value: .6f}, "
        f"voltage = {voltage: .6f}, "
        f"duty = {duty * 100:7.3f}%"
    )