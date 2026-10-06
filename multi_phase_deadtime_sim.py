import csv

import plotly.graph_objects as go

from config import (
    NUM_PHASES,
    DEADTIME_LH_NS,
    DEADTIME_HL_NS,
)

from simulation_config import (
    PWM_FREQUENCY_HZ,
    PWM_PERIOD_US,
    PWM_TEST_ENCODER_COUNT,
    PWM_SIMULATION_SAMPLES,
    SIMULATION_SAMPLE_PERIOD_NS,
    MULTI_PHASE_DEADTIME_CSV_FILE,
    MULTI_PHASE_DEADTIME_HTML_FILE,
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
)

from gate_drive_model import (
    calculate_deadtime_gate_edges,
    gate_states_with_deadtime,
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

PWM_PERIOD = (
    PWM_PERIOD_US
)

CSV_FILE = (
    MULTI_PHASE_DEADTIME_CSV_FILE
)

HTML_FILE = (
    MULTI_PHASE_DEADTIME_HTML_FILE
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
# 22 phase voltages
#   ->
# 22 PWM duties
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
# Calculate exact switching edges for all 22 phases
# ============================================================

phase_pwm_edges = []

phase_gate_edges = []


for phase_index in range(
    NUM_PHASES
):

    duty = (
        pwm_duties[
            phase_index
        ]
    )

    (
        turn_on_normalized,
        turn_off_normalized,
    ) = (
        calculate_center_aligned_edges(
            duty
        )
    )

    pwm_turn_on_us = (
        turn_on_normalized
        * PWM_PERIOD
    )

    pwm_turn_off_us = (
        turn_off_normalized
        * PWM_PERIOD
    )


    pwm_edges = {
        "turn_on_us":
            pwm_turn_on_us,

        "turn_off_us":
            pwm_turn_off_us,
    }


    gate_edges = (
        calculate_deadtime_gate_edges(
            pwm_turn_on_us=
                pwm_turn_on_us,

            pwm_turn_off_us=
                pwm_turn_off_us,

            deadtime_lh_ns=
                DEADTIME_LH_NS,

            deadtime_hl_ns=
                DEADTIME_HL_NS,
        )
    )


    phase_pwm_edges.append(
        pwm_edges
    )

    phase_gate_edges.append(
        gate_edges
    )


# ============================================================
# Build common physical-time axis
#
# Start with ordinary simulation samples.
#
# Then insert EVERY exact switching event from all 22 phases.
#
# This means the 40 ns deadtime is represented exactly and
# does not depend on Python sample spacing.
# ============================================================

time_points_us = [
    (
        sample
        / PWM_SAMPLES
        * PWM_PERIOD
    )

    for sample in range(
        PWM_SAMPLES + 1
    )
]


for phase_index in range(
    NUM_PHASES
):

    pwm_edges = (
        phase_pwm_edges[
            phase_index
        ]
    )

    gate_edges = (
        phase_gate_edges[
            phase_index
        ]
    )


    time_points_us.extend(
        [
            pwm_edges[
                "turn_on_us"
            ],

            gate_edges[
                "high_turn_on_us"
            ],

            pwm_edges[
                "turn_off_us"
            ],

            gate_edges[
                "low_turn_on_us"
            ],
        ]
    )


time_points_us = sorted(
    set(
        time_points_us
    )
)


# ============================================================
# Generate all waveforms
#
# Result:
#
#     22 PWM commands
#     22 High gates
#     22 Low gates
#
# Gate outputs:
#
#     44 physical gate-drive logic signals
# ============================================================

all_pwm_outputs = []

all_high_gate_outputs = []

all_low_gate_outputs = []


for phase_index in range(
    NUM_PHASES
):

    pwm_edges = (
        phase_pwm_edges[
            phase_index
        ]
    )

    gate_edges = (
        phase_gate_edges[
            phase_index
        ]
    )


    pwm_output = []

    high_gate_output = []

    low_gate_output = []


    for time_us in time_points_us:

        # ----------------------------------------------------
        # Ideal PWM command
        # ----------------------------------------------------

        if (
            time_us
            >=
            pwm_edges[
                "turn_on_us"
            ]
            and
            time_us
            <
            pwm_edges[
                "turn_off_us"
            ]
        ):

            pwm_state = 1

        else:

            pwm_state = 0


        # ----------------------------------------------------
        # High / Low gate states with deadtime
        # ----------------------------------------------------

        (
            high_gate,
            low_gate,
        ) = (
            gate_states_with_deadtime(
                time_us,
                gate_edges,
            )
        )


        pwm_output.append(
            pwm_state
        )

        high_gate_output.append(
            high_gate
        )

        low_gate_output.append(
            low_gate
        )


    all_pwm_outputs.append(
        pwm_output
    )

    all_high_gate_outputs.append(
        high_gate_output
    )

    all_low_gate_outputs.append(
        low_gate_output
    )


# ============================================================
# Verification
# ============================================================

total_shoot_through_samples = 0

phase_shoot_through_counts = []

deadtime_errors = []


for phase_index in range(
    NUM_PHASES
):

    high_output = (
        all_high_gate_outputs[
            phase_index
        ]
    )

    low_output = (
        all_low_gate_outputs[
            phase_index
        ]
    )


    phase_shoot_through = 0


    for (
        high_gate,
        low_gate,
    ) in zip(
        high_output,
        low_output,
    ):

        if (
            high_gate == 1
            and
            low_gate == 1
        ):

            phase_shoot_through += 1


    phase_shoot_through_counts.append(
        phase_shoot_through
    )

    total_shoot_through_samples += (
        phase_shoot_through
    )


    # --------------------------------------------------------
    # Verify exact physical deadtime
    # --------------------------------------------------------

    gate_edges = (
        phase_gate_edges[
            phase_index
        ]
    )


    measured_lh_ns = (
        (
            gate_edges[
                "high_turn_on_us"
            ]
            -
            gate_edges[
                "low_turn_off_us"
            ]
        )
        * 1000.0
    )


    measured_hl_ns = (
        (
            gate_edges[
                "low_turn_on_us"
            ]
            -
            gate_edges[
                "high_turn_off_us"
            ]
        )
        * 1000.0
    )


    if (
        abs(
            measured_lh_ns
            - DEADTIME_LH_NS
        )
        > 1e-9
    ):

        deadtime_errors.append(
            (
                phase_index + 1,
                "L->H",
                measured_lh_ns,
            )
        )


    if (
        abs(
            measured_hl_ns
            - DEADTIME_HL_NS
        )
        > 1e-9
    ):

        deadtime_errors.append(
            (
                phase_index + 1,
                "H->L",
                measured_hl_ns,
            )
        )


# ============================================================
# Save complete raw data
#
# Columns:
#
# time_us
#
# phase_1_pwm
# phase_1_high
# phase_1_low
#
# ...
#
# phase_22_pwm
# phase_22_high
# phase_22_low
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
        "time_us"
    ]


    for phase_number in range(
        1,
        NUM_PHASES + 1,
    ):

        header.extend(
            [
                (
                    f"phase_"
                    f"{phase_number}_pwm"
                ),

                (
                    f"phase_"
                    f"{phase_number}_high"
                ),

                (
                    f"phase_"
                    f"{phase_number}_low"
                ),
            ]
        )


    writer.writerow(
        header
    )


    for sample_index, time_us in enumerate(
        time_points_us
    ):

        row = [
            time_us
        ]


        for phase_index in range(
            NUM_PHASES
        ):

            row.extend(
                [
                    all_pwm_outputs[
                        phase_index
                    ][
                        sample_index
                    ],

                    all_high_gate_outputs[
                        phase_index
                    ][
                        sample_index
                    ],

                    all_low_gate_outputs[
                        phase_index
                    ][
                        sample_index
                    ],
                ]
            )


        writer.writerow(
            row
        )


# ============================================================
# Interactive plot
#
# One row per phase.
#
# High and Low are displayed together in the same phase row.
#
# IMPORTANT:
#
# Every trace starts with:
#
#     visible="legendonly"
#
# Therefore the HTML initially displays NO waveform.
# ============================================================

fig = go.Figure()


PHASE_SPACING = 2.0

HIGH_LEVEL_OFFSET = 0.75

LOW_LEVEL_OFFSET = 0.25

LOGIC_HEIGHT = 0.35


for phase_index in range(
    NUM_PHASES
):

    phase_number = (
        phase_index + 1
    )

    base_y = (
        (
            NUM_PHASES
            - 1
            - phase_index
        )
        * PHASE_SPACING
    )


    high_output = (
        all_high_gate_outputs[
            phase_index
        ]
    )

    low_output = (
        all_low_gate_outputs[
            phase_index
        ]
    )


    # --------------------------------------------------------
    # High gate
    # --------------------------------------------------------

    high_display = [
        (
            base_y
            + HIGH_LEVEL_OFFSET
            + state * LOGIC_HEIGHT
        )

        for state in high_output
    ]


    fig.add_trace(
        go.Scatter(
            x=time_points_us,

            y=high_display,

            mode="lines",

            line_shape="hv",

            name=(
                f"Phase {phase_number}"
            ),

            legendgroup=(
                f"phase_{phase_number}"
            ),

            legendgrouptitle_text=(
                f"Phase {phase_number}"
            ),

            visible="legendonly",

            customdata=[
                [state, "High"]

                for state in high_output
            ],

            hovertemplate=(
                f"<b>Phase {phase_number}</b>"
                "<br>"
                "Gate: High"
                "<br>"
                "Time: %{x:.9f} µs"
                "<br>"
                "Logic State: "
                "%{customdata[0]:.0f}"
                "<extra></extra>"
            ),
        )
    )


    # --------------------------------------------------------
    # Low gate
    #
    # showlegend=False means the Low trace does not create
    # a second legend item.
    #
    # It still belongs to the same legendgroup.
    # --------------------------------------------------------

    low_display = [
        (
            base_y
            + LOW_LEVEL_OFFSET
            + state * LOGIC_HEIGHT
        )

        for state in low_output
    ]


    fig.add_trace(
        go.Scatter(
            x=time_points_us,

            y=low_display,

            mode="lines",

            line_shape="hv",

            name=(
                f"Phase {phase_number} Low"
            ),

            legendgroup=(
                f"phase_{phase_number}"
            ),

            showlegend=False,

            visible="legendonly",

            customdata=[
                [state, "Low"]

                for state in low_output
            ],

            hovertemplate=(
                f"<b>Phase {phase_number}</b>"
                "<br>"
                "Gate: Low"
                "<br>"
                "Time: %{x:.9f} µs"
                "<br>"
                "Logic State: "
                "%{customdata[0]:.0f}"
                "<extra></extra>"
            ),
        )
    )


# ============================================================
# PWM center marker
# ============================================================

fig.add_vline(
    x=PWM_PERIOD / 2.0,

    line_dash="dot",

    annotation_text="PWM Center",

    annotation_position="top",
)


# ============================================================
# Y-axis phase labels
# ============================================================

phase_tick_values = []

phase_tick_labels = []


for phase_index in range(
    NUM_PHASES
):

    phase_number = (
        phase_index + 1
    )

    base_y = (
        (
            NUM_PHASES
            - 1
            - phase_index
        )
        * PHASE_SPACING
    )


    phase_tick_values.append(
        base_y + 0.6
    )

    phase_tick_labels.append(
        f"Phase {phase_number}"
    )


# ============================================================
# Axes
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
        "22-Phase Gate-Drive Outputs"
    ),

    tickmode="array",

    tickvals=(
        phase_tick_values
    ),

    ticktext=(
        phase_tick_labels
    ),

    showgrid=False,

    range=[
        -1,
        NUM_PHASES
        * PHASE_SPACING
        + 1,
    ],
)


# ============================================================
# Layout
#
# groupclick="togglegroup":
#
# Clicking Phase N in the legend toggles BOTH:
#
#     Phase N High
#     Phase N Low
#
# together.
# ============================================================

fig.update_layout(
    title=dict(
        text=(
            "22-Phase / 44-Gate "
            "Deadtime Simulation"
            "<br>"
            "<sup>"
            f"PWM Frequency = "
            f"{PWM_FREQUENCY_HZ / 1000.0:.3f} kHz, "
            f"PWM Period = "
            f"{PWM_PERIOD:.6f} µs, "
            f"Deadtime L→H = "
            f"{DEADTIME_LH_NS:.3f} ns, "
            f"Deadtime H→L = "
            f"{DEADTIME_HL_NS:.3f} ns, "
            f"Encoder Position = "
            f"{ENCODER_COUNT} count"
            "</sup>"
        ),

        x=0.05,
    ),

    height=1000,

    hovermode="closest",

    legend=dict(
        title="Phases",

        groupclick="togglegroup",
    ),

    margin=dict(
        l=130,
        r=150,
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
                "22_phase_44_gate_deadtime"
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
    "22-Phase / 44-Gate Deadtime Simulation"
)

print(
    "========================================"
)

print()

print(
    "PWM frequency:",
    f"{PWM_FREQUENCY_HZ / 1000.0:.3f}",
    "kHz",
)

print(
    "PWM period:",
    f"{PWM_PERIOD:.9f}",
    "us",
)

print(
    "Simulation resolution:",
    f"{SIMULATION_SAMPLE_PERIOD_NS:.6f}",
    "ns / ordinary sample",
)

print()

print(
    "Encoder position:",
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
    "Deadtime L -> H:",
    f"{DEADTIME_LH_NS:.6f}",
    "ns",
)

print(
    "Deadtime H -> L:",
    f"{DEADTIME_HL_NS:.6f}",
    "ns",
)

print()

print(
    "Total High/Low simultaneous-ON samples:",
    total_shoot_through_samples,
)

print(
    "Deadtime verification errors:",
    len(
        deadtime_errors
    ),
)

print()


for phase_index in range(
    NUM_PHASES
):

    print(
        f"Phase {phase_index + 1:2d}: "
        f"Duty = "
        f"{pwm_duties[phase_index] * 100.0:9.6f} %, "
        f"Shoot-through = "
        f"{phase_shoot_through_counts[phase_index]}"
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