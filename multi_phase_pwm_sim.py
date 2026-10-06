import csv

import plotly.graph_objects as go

from config import NUM_PHASES

from simulation_config import (
    PWM_TEST_ENCODER_COUNT,
    PWM_SIMULATION_SAMPLES,
    MULTI_PHASE_PWM_CSV_FILE,
    MULTI_PHASE_PWM_HTML_FILE,
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

CSV_FILE = MULTI_PHASE_PWM_CSV_FILE

HTML_FILE = MULTI_PHASE_PWM_HTML_FILE


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
# 22 phase angles
#   ->
# 22 phase voltages
#   ->
# 22 PWM duty cycles
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
# Generate all PWM waveforms
# ============================================================

normalized_time = None

all_pwm_outputs = []

all_turn_on = []

all_turn_off = []


for duty in pwm_duties:

    phase_time, pwm_output = (
        generate_center_aligned_pwm(
            duty=duty,
            samples=PWM_SAMPLES,
        )
    )

    turn_on, turn_off = (
        calculate_center_aligned_edges(
            duty
        )
    )

    if normalized_time is None:
        normalized_time = phase_time

    all_pwm_outputs.append(
        pwm_output
    )

    all_turn_on.append(
        turn_on
    )

    all_turn_off.append(
        turn_off
    )


# ============================================================
# Convert normalized PWM-period position to percentage
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

    header = [
        "pwm_period_position_percent"
    ]

    for phase_index in range(
        NUM_PHASES
    ):

        header.append(
            f"phase_{phase_index + 1}_pwm_state"
        )

    writer.writerow(
        header
    )

    for sample_index in range(
        len(time_percent)
    ):

        row = [
            time_percent[sample_index]
        ]

        for phase_index in range(
            NUM_PHASES
        ):

            row.append(
                all_pwm_outputs[
                    phase_index
                ][
                    sample_index
                ]
            )

        writer.writerow(
            row
        )


# ============================================================
# Interactive multi-phase waveform
#
# Each phase receives a vertical offset so the digital
# waveforms can be viewed separately.
# ============================================================

fig = go.Figure()


PHASE_SPACING = 1.5

PWM_HEIGHT = 0.8


for phase_index in range(
    NUM_PHASES
):

    phase_number = (
        phase_index + 1
    )

    # Phase 1 appears at the top.
    vertical_offset = (
        (NUM_PHASES - 1 - phase_index)
        * PHASE_SPACING
    )

    displayed_waveform = [
        vertical_offset
        + pwm_state * PWM_HEIGHT

        for pwm_state in (
            all_pwm_outputs[
                phase_index
            ]
        )
    ]

    custom_data = [
        [
            all_pwm_outputs[
                phase_index
            ][sample_index],

            pwm_duties[
                phase_index
            ] * 100.0,

            phase_voltages[
                phase_index
            ],

            phase_angles_deg[
                phase_index
            ],
        ]

        for sample_index in range(
            len(time_percent)
        )
    ]

    fig.add_trace(
        go.Scatter(
            x=time_percent,

            y=displayed_waveform,

            mode="lines",

            line_shape="hv",

            name=(
                f"Phase {phase_number}"
            ),

            customdata=custom_data,

            hovertemplate=(
                f"<b>Phase {phase_number}</b>"
                "<br><br>"
                "PWM Period Position: "
                "%{x:.3f} %"
                "<br>"
                "PWM Logic State: "
                "%{customdata[0]:.0f}"
                "<br>"
                "PWM Duty Cycle: "
                "%{customdata[1]:.3f} %"
                "<br>"
                "Normalized Phase Voltage: "
                "%{customdata[2]:.6f}"
                "<br>"
                "Phase Modulation Angle: "
                "%{customdata[3]:.3f} deg"
                "<extra></extra>"
            ),
        )
    )


# ============================================================
# PWM center marker
# ============================================================

fig.add_vline(
    x=50.0,

    line_dash="dot",

    annotation_text="PWM Center",

    annotation_position="top",
)


# ============================================================
# Y-axis phase labels
# ============================================================

y_tick_values = []

y_tick_text = []


for phase_index in range(
    NUM_PHASES
):

    vertical_offset = (
        (NUM_PHASES - 1 - phase_index)
        * PHASE_SPACING
    )

    y_tick_values.append(
        vertical_offset
        + PWM_HEIGHT / 2.0
    )

    y_tick_text.append(
        f"Phase {phase_index + 1}"
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
        "Multi-Phase PWM Logic Waveforms"
    ),

    tickmode="array",

    tickvals=y_tick_values,

    ticktext=y_tick_text,

    showgrid=False,
)


# ============================================================
# Layout
# ============================================================

fig.update_layout(
    title=dict(
        text=(
            f"{NUM_PHASES}-Phase "
            "Ideal Center-Aligned PWM"
            "<br>"
            "<sup>"
            f"Encoder Test Position = "
            f"{ENCODER_COUNT} count, "
            f"Mechanical Rotor Angle θm = "
            f"{theta_m_deg:.3f} deg, "
            f"Electrical Angle θe = "
            f"{theta_e_deg:.3f} deg, "
            f"Control Angle = "
            f"{theta_control_deg:.3f} deg"
            "</sup>"
        ),

        x=0.05,
    ),

    height=1100,

    hovermode="closest",

    margin=dict(
        l=110,
        r=80,
        t=120,
        b=90,
    ),

    legend=dict(
        title="PWM Channels",
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
                f"{NUM_PHASES}_phase_"
                "center_aligned_pwm"
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
    f"{NUM_PHASES}-Phase PWM Cycle Simulation"
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


# ============================================================
# Print all phase results
# ============================================================

for phase_index in range(
    NUM_PHASES
):

    print(
        f"Phase {phase_index + 1:2d}: "
        f"angle = "
        f"{phase_angles_deg[phase_index]:10.6f} deg, "
        f"voltage = "
        f"{phase_voltages[phase_index]: .6f}, "
        f"duty = "
        f"{pwm_duties[phase_index] * 100.0:7.3f} %, "
        f"ON = "
        f"{all_turn_on[phase_index] * 100.0:7.3f} %, "
        f"OFF = "
        f"{all_turn_off[phase_index] * 100.0:7.3f} %"
    )


# ============================================================
# Opposite-phase symmetry verification
#
# With an even number of equally spaced phases:
#
# Phase k and Phase k + NUM_PHASES / 2
#
# are 180 electrical degrees apart.
#
# Therefore:
#
# Duty(k) + Duty(opposite) = 1
# ============================================================

max_opposite_duty_error = 0.0


if NUM_PHASES % 2 == 0:

    for phase_index in range(
        NUM_PHASES // 2
    ):

        opposite_index = (
            phase_index
            + NUM_PHASES // 2
        )

        error = abs(
            pwm_duties[phase_index]
            + pwm_duties[opposite_index]
            - 1.0
        )

        max_opposite_duty_error = max(
            max_opposite_duty_error,
            error,
        )


    print()

    print(
        "Maximum opposite-phase duty error:",
        f"{max_opposite_duty_error:.12e}",
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