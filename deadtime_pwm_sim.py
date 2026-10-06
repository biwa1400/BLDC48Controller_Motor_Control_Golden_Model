import csv

import plotly.graph_objects as go

from config import (
    DEADTIME_LH_NS,
    DEADTIME_HL_NS,
)

from simulation_config import (
    PWM_FREQUENCY_HZ,
    PWM_PERIOD_US,
    PWM_TEST_ENCODER_COUNT,
    PWM_SIMULATION_SAMPLES,
    DEADTIME_PWM_CSV_FILE,
    DEADTIME_PWM_HTML_FILE,
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
    DEADTIME_PWM_CSV_FILE
)

HTML_FILE = (
    DEADTIME_PWM_HTML_FILE
)


# ============================================================
# Float Golden Model
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
# Calculate ideal PWM switching edges
#
# pwm_model.py returns normalized positions:
#
#     0.0 ... 1.0
# ============================================================

turn_on_normalized, turn_off_normalized = (
    calculate_center_aligned_edges(
        phase1_duty
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


# ============================================================
# Calculate exact deadtime switching events
# ============================================================

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


# ============================================================
# Build plotting time points
#
# Important:
#
# Ordinary simulation samples are included for convenient
# plotting and CSV output.
#
# Exact switching-event times are ALSO inserted explicitly.
#
# Therefore a 40 ns deadtime remains exactly 40 ns even when
# the ordinary simulation sample spacing is larger/coarser.
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


# Add exact event times.
exact_event_times = [
    pwm_turn_on_us,

    gate_edges[
        "high_turn_on_us"
    ],

    pwm_turn_off_us,

    gate_edges[
        "low_turn_on_us"
    ],
]


time_points_us.extend(
    exact_event_times
)


# Remove duplicates and sort.
time_points_us = sorted(
    set(
        time_points_us
    )
)


# ============================================================
# Generate PWM command and gate states
# ============================================================

pwm_output = []

high_gate_output = []

low_gate_output = []


for time_us in time_points_us:

    # --------------------------------------------------------
    # Ideal PWM command
    # --------------------------------------------------------

    if (
        time_us >= pwm_turn_on_us
        and
        time_us < pwm_turn_off_us
    ):

        pwm_state = 1

    else:

        pwm_state = 0


    # --------------------------------------------------------
    # Gate-drive states with deadtime
    # --------------------------------------------------------

    high_gate, low_gate = (
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


# ============================================================
# Verification
# ============================================================

shoot_through_count = 0

both_off_count = 0


for (
    high_gate,
    low_gate,
) in zip(
    high_gate_output,
    low_gate_output,
):

    if (
        high_gate == 1
        and
        low_gate == 1
    ):

        shoot_through_count += 1


    if (
        high_gate == 0
        and
        low_gate == 0
    ):

        both_off_count += 1


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
            "phase_1_pwm_command",
            "phase_1_high_gate",
            "phase_1_low_gate",
        ]
    )


    for (
        time_us,
        pwm_state,
        high_gate,
        low_gate,
    ) in zip(
        time_points_us,
        pwm_output,
        high_gate_output,
        low_gate_output,
    ):

        writer.writerow(
            [
                time_us,
                pwm_state,
                high_gate,
                low_gate,
            ]
        )


# ============================================================
# Plot configuration
# ============================================================

fig = go.Figure()


PWM_OFFSET = 4.0

HIGH_OFFSET = 2.0

LOW_OFFSET = 0.0

LOGIC_HEIGHT = 0.8


# ============================================================
# Helper function
# ============================================================

def add_logic_trace(
    name,
    values,
    offset,
):

    displayed_values = [
        offset
        + value * LOGIC_HEIGHT

        for value in values
    ]


    custom_data = [
        [value]

        for value in values
    ]


    fig.add_trace(
        go.Scatter(
            x=time_points_us,

            y=displayed_values,

            mode="lines",

            line_shape="hv",

            name=name,

            customdata=custom_data,

            hovertemplate=(
                f"<b>{name}</b>"
                "<br><br>"
                "Time: %{x:.9f} µs"
                "<br>"
                "Logic State: "
                "%{customdata[0]:.0f}"
                "<extra></extra>"
            ),
        )
    )


# ============================================================
# Add waveforms
# ============================================================

add_logic_trace(
    "PWM Command",
    pwm_output,
    PWM_OFFSET,
)

add_logic_trace(
    "High Gate",
    high_gate_output,
    HIGH_OFFSET,
)

add_logic_trace(
    "Low Gate",
    low_gate_output,
    LOW_OFFSET,
)


# ============================================================
# PWM center
# ============================================================

fig.add_vline(
    x=PWM_PERIOD / 2.0,

    line_dash="dot",

    annotation_text="PWM Center",

    annotation_position="top",
)


# ============================================================
# Exact switching-event markers
# ============================================================

fig.add_vline(
    x=pwm_turn_on_us,

    line_dash="dash",

    annotation_text="Low OFF",

    annotation_position="bottom",
)


fig.add_vline(
    x=gate_edges[
        "high_turn_on_us"
    ],

    line_dash="dash",

    annotation_text="High ON",

    annotation_position="top",
)


fig.add_vline(
    x=pwm_turn_off_us,

    line_dash="dash",

    annotation_text="High OFF",

    annotation_position="top",
)


fig.add_vline(
    x=gate_edges[
        "low_turn_on_us"
    ],

    line_dash="dash",

    annotation_text="Low ON",

    annotation_position="bottom",
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
            "Phase 1 - Complementary Gate Drive "
            "with Deadtime"
            "<br>"
            "<sup>"
            f"PWM Frequency = "
            f"{PWM_FREQUENCY_HZ / 1000.0:.3f} kHz, "
            f"PWM Period = "
            f"{PWM_PERIOD:.6f} µs, "
            f"Duty = "
            f"{phase1_duty * 100.0:.3f} %, "
            f"Deadtime L→H = "
            f"{DEADTIME_LH_NS:.3f} ns, "
            f"Deadtime H→L = "
            f"{DEADTIME_HL_NS:.3f} ns"
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
                "phase1_deadtime_gate_drive"
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
    "Phase 1 Deadtime Gate Simulation"
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

print()

print(
    "Phase 1 PWM duty:",
    f"{phase1_duty * 100.0:.6f}",
    "%",
)

print()

print(
    "Ideal PWM turn-ON:",
    f"{pwm_turn_on_us:.9f}",
    "us",
)

print(
    "Low Gate OFF:",
    f"{gate_edges['low_turn_off_us']:.9f}",
    "us",
)

print(
    "High Gate ON:",
    f"{gate_edges['high_turn_on_us']:.9f}",
    "us",
)

print(
    "L -> H deadtime:",
    f"{(
        gate_edges['high_turn_on_us']
        - gate_edges['low_turn_off_us']
    ) * 1000.0:.6f}",
    "ns",
)

print()

print(
    "Ideal PWM turn-OFF:",
    f"{pwm_turn_off_us:.9f}",
    "us",
)

print(
    "High Gate OFF:",
    f"{gate_edges['high_turn_off_us']:.9f}",
    "us",
)

print(
    "Low Gate ON:",
    f"{gate_edges['low_turn_on_us']:.9f}",
    "us",
)

print(
    "H -> L deadtime:",
    f"{(
        gate_edges['low_turn_on_us']
        - gate_edges['high_turn_off_us']
    ) * 1000.0:.6f}",
    "ns",
)

print()

print(
    "High/Low simultaneous-ON samples:",
    shoot_through_count,
)

print(
    "Both-OFF samples:",
    both_off_count,
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