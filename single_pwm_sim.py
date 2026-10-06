import csv

import plotly.graph_objects as go

from simulation_config import (
    PWM_TEST_ENCODER_COUNT,
    PWM_SIMULATION_SAMPLES,
    SINGLE_PWM_CSV_FILE,
    SINGLE_PWM_HTML_FILE,
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
    calculate_center_aligned_edges,
    generate_center_aligned_pwm,
)


# ============================================================
# Simulation parameters
# ============================================================

ENCODER_COUNT = PWM_TEST_ENCODER_COUNT

PWM_SAMPLES = PWM_SIMULATION_SAMPLES

CSV_FILE = SINGLE_PWM_CSV_FILE

HTML_FILE = SINGLE_PWM_HTML_FILE


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
# Phase angle
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
# PWM generation itself is implemented in pwm_model.py.
#
# This file only configures, runs, records and visualizes
# the simulation.
# ============================================================

normalized_time, pwm_output = (
    generate_center_aligned_pwm(
        duty=phase1_duty,
        samples=PWM_SAMPLES,
    )
)


turn_on, turn_off = (
    calculate_center_aligned_edges(
        phase1_duty
    )
)


# ============================================================
# Convert normalized PWM-period position to percentage
#
# 0.0 ... 1.0
#
# becomes:
#
# 0 ... 100 %
# ============================================================

time_percent = [
    time_position * 100.0
    for time_position in normalized_time
]


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
            "pwm_period_position_percent",
            "phase_1_pwm_state",
        ]
    )

    for (
        time_pct,
        pwm_state,
    ) in zip(
        time_percent,
        pwm_output,
    ):

        writer.writerow(
            [
                time_pct,
                pwm_state,
            ]
        )


# ============================================================
# Interactive waveform
# ============================================================

fig = go.Figure()


fig.add_trace(
    go.Scatter(
        x=time_percent,

        y=pwm_output,

        mode="lines",

        line_shape="hv",

        name="Phase 1 PWM",

        hovertemplate=(
            "<b>Phase 1 PWM</b>"
            "<br><br>"
            "PWM Period Position: "
            "%{x:.3f} %"
            "<br>"
            "PWM Logic State: "
            "%{y:.0f}"
            "<extra></extra>"
        ),
    )
)


# ============================================================
# Switching-edge markers
# ============================================================

fig.add_vline(
    x=turn_on * 100.0,

    line_dash="dash",

    annotation_text="Turn ON",

    annotation_position="top",
)


fig.add_vline(
    x=turn_off * 100.0,

    line_dash="dash",

    annotation_text="Turn OFF",

    annotation_position="top",
)


# ============================================================
# PWM center marker
# ============================================================

fig.add_vline(
    x=50.0,

    line_dash="dot",

    annotation_text="PWM Center",

    annotation_position="bottom",
)


# ============================================================
# Axis configuration
# ============================================================

fig.update_xaxes(
    title_text=(
        "Position Within One PWM Period (%)"
    ),

    range=[
        0,
        100,
    ],

    showgrid=True,
)


fig.update_yaxes(
    title_text=(
        "Phase 1 PWM Logic State"
    ),

    tickmode="array",

    tickvals=[
        0,
        1,
    ],

    ticktext=[
        "LOW (0)",
        "HIGH (1)",
    ],

    range=[
        -0.2,
        1.2,
    ],

    showgrid=True,
)


# ============================================================
# Layout
# ============================================================

fig.update_layout(
    title=dict(
        text=(
            "Phase 1 - Ideal Center-Aligned PWM"
            "<br>"
            "<sup>"
            f"Encoder Position = "
            f"{ENCODER_COUNT} count, "
            f"Mechanical Rotor Angle θm = "
            f"{theta_m_deg:.3f} deg, "
            f"Phase 1 Normalized Voltage = "
            f"{phase1_voltage:.6f}, "
            f"PWM Duty Cycle = "
            f"{phase1_duty * 100.0:.3f}%"
            "</sup>"
        ),

        x=0.05,
    ),

    height=600,

    hovermode="x",

    margin=dict(
        l=100,
        r=60,
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
                "phase1_center_aligned_pwm"
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
    "Single PWM Cycle Simulation"
)

print(
    "========================================"
)

print()

print(
    "Encoder test position:",
    ENCODER_COUNT,
    "count",
)

print(
    "PWM simulation resolution:",
    PWM_SAMPLES,
    "samples / PWM period",
)

print()

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
    "PWM turn-ON position:",
    f"{turn_on * 100.0:.6f}",
    "% of PWM period",
)

print(
    "PWM turn-OFF position:",
    f"{turn_off * 100.0:.6f}",
    "% of PWM period",
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