import csv

import plotly.graph_objects as go

from simulation_config import (
    PWM_FREQUENCY_HZ,
    PWM_PERIOD_US,
    PWM_TEST_ENCODER_COUNT,
    PWM_SIMULATION_SAMPLES,
    SIMULATION_SAMPLE_PERIOD_NS,
    COMPLEMENTARY_PWM_CSV_FILE,
    COMPLEMENTARY_PWM_HTML_FILE,
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

from pwm_model import (
    calculate_pwm_duties,
    generate_center_aligned_pwm,
)

from gate_drive_model import (
    generate_complementary_gates,
)


# ============================================================
# Simulation parameters
# ============================================================

ENCODER_COUNT = (
    PWM_TEST_ENCODER_COUNT
)

PWM_SAMPLES = (
    PWM_SIMULATION_SAMPLES
)

PWM_FREQUENCY = (
    PWM_FREQUENCY_HZ
)

PWM_PERIOD = (
    PWM_PERIOD_US
)

CSV_FILE = (
    COMPLEMENTARY_PWM_CSV_FILE
)

HTML_FILE = (
    COMPLEMENTARY_PWM_HTML_FILE
)


# ============================================================
# Float Golden Model
#
# Encoder
#   ->
# Mechanical angle
#   ->
# Electrical angle
#   ->
# Voltage-vector angle
#   ->
# Control angle
#   ->
# Phase voltage
#   ->
# PWM duty
# ============================================================

theta_m_deg = (
    encoder_to_mechanical_angle(
        ENCODER_COUNT
    )
)

theta_m_relative_deg = (
    encoder_to_relative_mechanical_angle(
        ENCODER_COUNT
    )
)

theta_e_deg = (
    mechanical_to_electrical_angle(
        theta_m_relative_deg
    )
)

theta_v_deg = (
    electrical_to_voltage_angle(
        theta_e_deg
    )
)

theta_control_deg = (
    apply_phase_advance(
        theta_v_deg
    )
)

phase_angles_deg = (
    generate_phase_angles(
        theta_control_deg
    )
)

phase_sines = (
    calculate_phase_sines(
        phase_angles_deg
    )
)

phase_voltages = (
    calculate_phase_voltages(
        phase_sines
    )
)

pwm_duties = (
    calculate_pwm_duties(
        phase_voltages
    )
)


# ============================================================
# Select Phase 1
# ============================================================

phase1_voltage = (
    phase_voltages[0]
)

phase1_duty = (
    pwm_duties[0]
)


# ============================================================
# Generate ideal center-aligned PWM
#
# The PWM model still works in normalized time:
#
#     0.0 ... 1.0
#
# Here we convert that normalized position into
# real physical time in microseconds.
# ============================================================

normalized_time, pwm_output = (
    generate_center_aligned_pwm(
        duty=phase1_duty,
        samples=PWM_SAMPLES,
    )
)


# ============================================================
# Convert normalized time to physical time
#
# 0.0 ... 1.0
#
# becomes:
#
# 0 ... PWM_PERIOD_US
# ============================================================

time_us = [
    time_position * PWM_PERIOD
    for time_position in normalized_time
]


# ============================================================
# Generate ideal complementary gate signals
#
# Deadtime is intentionally NOT applied yet.
# ============================================================

high_gate_output, low_gate_output = (
    generate_complementary_gates(
        pwm_output
    )
)


# ============================================================
# Verification
#
# Without deadtime:
#
#     High + Low = 1
#
# and:
#
#     High AND Low = 0
# ============================================================

complement_error_count = 0

shoot_through_count = 0


for (
    high_gate,
    low_gate,
) in zip(
    high_gate_output,
    low_gate_output,
):

    if (
        high_gate + low_gate
        != 1
    ):
        complement_error_count += 1

    if (
        high_gate == 1
        and
        low_gate == 1
    ):
        shoot_through_count += 1


# ============================================================
# Save raw simulation data
# ============================================================

with open(
    CSV_FILE,
    "w",
    newline="",
    encoding="utf-8",
) as csv_file:

    writer = csv.writer(
        csv_file
    )

    writer.writerow(
        [
            "time_us",
            "pwm_period_position_percent",
            "phase_1_pwm_command",
            "phase_1_high_gate",
            "phase_1_low_gate",
        ]
    )

    for (
        time_position_us,
        pwm_state,
        high_gate,
        low_gate,
    ) in zip(
        time_us,
        pwm_output,
        high_gate_output,
        low_gate_output,
    ):

        writer.writerow(
            [
                time_position_us,

                (
                    time_position_us
                    / PWM_PERIOD
                    * 100.0
                ),

                pwm_state,

                high_gate,

                low_gate,
            ]
        )


# ============================================================
# Interactive waveform
#
# Vertical offsets are used only for visualization.
# The X-axis is now real physical time.
# ============================================================

fig = go.Figure()


PWM_OFFSET = 4.0

HIGH_OFFSET = 2.0

LOW_OFFSET = 0.0

LOGIC_HEIGHT = 0.8


# ============================================================
# PWM command
# ============================================================

pwm_display = [
    PWM_OFFSET
    + state * LOGIC_HEIGHT

    for state in pwm_output
]


fig.add_trace(
    go.Scatter(
        x=time_us,

        y=pwm_display,

        mode="lines",

        line_shape="hv",

        name="PWM Command",

        customdata=pwm_output,

        hovertemplate=(
            "<b>Phase 1 PWM Command</b>"
            "<br><br>"
            "Time: %{x:.6f} µs"
            "<br>"
            "PWM State: %{customdata:.0f}"
            "<extra></extra>"
        ),
    )
)


# ============================================================
# High-side gate
# ============================================================

high_display = [
    HIGH_OFFSET
    + state * LOGIC_HEIGHT

    for state in high_gate_output
]


fig.add_trace(
    go.Scatter(
        x=time_us,

        y=high_display,

        mode="lines",

        line_shape="hv",

        name="High Gate",

        customdata=high_gate_output,

        hovertemplate=(
            "<b>Phase 1 High Gate</b>"
            "<br><br>"
            "Time: %{x:.6f} µs"
            "<br>"
            "Gate State: %{customdata:.0f}"
            "<extra></extra>"
        ),
    )
)


# ============================================================
# Low-side gate
# ============================================================

low_display = [
    LOW_OFFSET
    + state * LOGIC_HEIGHT

    for state in low_gate_output
]


fig.add_trace(
    go.Scatter(
        x=time_us,

        y=low_display,

        mode="lines",

        line_shape="hv",

        name="Low Gate",

        customdata=low_gate_output,

        hovertemplate=(
            "<b>Phase 1 Low Gate</b>"
            "<br><br>"
            "Time: %{x:.6f} µs"
            "<br>"
            "Gate State: %{customdata:.0f}"
            "<extra></extra>"
        ),
    )
)


# ============================================================
# PWM center marker
# ============================================================

pwm_center_us = (
    PWM_PERIOD / 2.0
)


fig.add_vline(
    x=pwm_center_us,

    line_dash="dot",

    annotation_text="PWM Center",

    annotation_position="top",
)


# ============================================================
# Axis configuration
# ============================================================

fig.update_xaxes(
    title_text=(
        "Time Within One PWM Period (µs)"
    ),

    range=[
        0,
        PWM_PERIOD,
    ],

    showgrid=True,
)


fig.update_yaxes(
    title_text=(
        "Phase 1 Gate-Drive Logic Signals"
    ),

    tickmode="array",

    tickvals=[
        PWM_OFFSET + LOGIC_HEIGHT / 2.0,
        HIGH_OFFSET + LOGIC_HEIGHT / 2.0,
        LOW_OFFSET + LOGIC_HEIGHT / 2.0,
    ],

    ticktext=[
        "PWM Command",
        "High Gate",
        "Low Gate",
    ],

    range=[
        -0.5,
        5.3,
    ],

    showgrid=False,
)


# ============================================================
# Layout
# ============================================================

fig.update_layout(
    title=dict(
        text=(
            "Phase 1 - Ideal Complementary Gate Drive"
            "<br>"
            "<sup>"
            f"PWM Frequency = "
            f"{PWM_FREQUENCY / 1000.0:.3f} kHz, "
            f"PWM Period = "
            f"{PWM_PERIOD:.6f} µs, "
            f"Encoder Test Position = "
            f"{ENCODER_COUNT} count, "
            f"Mechanical Rotor Angle θm = "
            f"{theta_m_deg:.3f} deg, "
            f"Phase 1 Duty = "
            f"{phase1_duty * 100.0:.3f} %, "
            "Deadtime = NOT APPLIED"
            "</sup>"
        ),

        x=0.05,
    ),

    height=650,

    hovermode="closest",

    margin=dict(
        l=140,
        r=80,
        t=120,
        b=90,
    ),
)


# ============================================================
# Save interactive HTML
# ============================================================

fig.write_html(
    HTML_FILE,

    include_plotlyjs=True,

    full_html=True,

    config={
        "scrollZoom": True,

        "displaylogo": False,

        "responsive": True,

        "toImageButtonOptions": {
            "format": "png",

            "filename": (
                "phase1_complementary_gate_drive"
            ),

            "scale": 2,
        },
    },
)


# ============================================================
# Terminal report
# ============================================================

print()

print(
    "========================================"
)

print(
    "Phase 1 Complementary Gate Simulation"
)

print(
    "========================================"
)

print()

print(
    "PWM frequency:",
    f"{PWM_FREQUENCY / 1000.0:.3f}",
    "kHz",
)

print(
    "PWM period:",
    f"{PWM_PERIOD:.9f}",
    "us",
)

print(
    "Simulation samples:",
    PWM_SAMPLES,
)

print(
    "Simulation sample spacing:",
    f"{SIMULATION_SAMPLE_PERIOD_NS:.6f}",
    "ns",
)

print()

print(
    "Encoder test position:",
    ENCODER_COUNT,
    "count",
)

print(
    "Mechanical rotor angle:",
    f"{theta_m_deg:.6f}",
    "deg",
)

print(
    "Electrical angle:",
    f"{theta_e_deg:.6f}",
    "deg",
)

print(
    "Control angle:",
    f"{theta_control_deg:.6f}",
    "deg",
)

print()

print(
    "Phase 1 normalized voltage:",
    f"{phase1_voltage:.6f}",
)

print(
    "Phase 1 PWM duty cycle:",
    f"{phase1_duty * 100.0:.6f}",
    "%",
)

print()

print(
    "Complement errors:",
    complement_error_count,
)

print(
    "High/Low simultaneous-ON samples:",
    shoot_through_count,
)

print()

print(
    "Generated raw data:",
    CSV_FILE,
)

print(
    "Generated interactive report:",
    HTML_FILE,
)