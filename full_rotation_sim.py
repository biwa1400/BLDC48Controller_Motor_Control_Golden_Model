import csv

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import (
    LM10_COUNTS,
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


# ============================================================
# Output files
# ============================================================

CSV_FILE = "float_full_rotation.csv"
HTML_FILE = "float_full_rotation.html"


# ============================================================
# Simulation storage
# ============================================================

encoder_counts = []
mechanical_angles = []
relative_mechanical_angles = []
electrical_angles = []
voltage_vector_angles = []
control_angles = []

all_phase_voltages = [
    [] for _ in range(22)
]

all_phase_duties = [
    [] for _ in range(22)
]


# ============================================================
# CSV header
# ============================================================

header = [
    "encoder_count",
    "mechanical_angle_deg",
    "relative_mechanical_angle_deg",
    "electrical_angle_deg",
    "voltage_vector_angle_deg",
    "control_angle_deg",
]

for i in range(22):
    header.append(
        f"phase_{i + 1}_voltage"
    )

for i in range(22):
    header.append(
        f"phase_{i + 1}_duty"
    )


# ============================================================
# Full mechanical rotation simulation
# ============================================================

with open(
    CSV_FILE,
    "w",
    newline="",
    encoding="utf-8",
) as csv_file:

    writer = csv.writer(csv_file)
    writer.writerow(header)

    for phi in range(LM10_COUNTS):

        # ----------------------------------------------------
        # Encoder -> mechanical angle
        # ----------------------------------------------------

        theta_m_deg = (
            encoder_to_mechanical_angle(phi)
        )

        theta_m_relative_deg = (
            encoder_to_relative_mechanical_angle(phi)
        )

        # ----------------------------------------------------
        # Mechanical -> electrical angle
        # ----------------------------------------------------

        theta_e_deg = (
            mechanical_to_electrical_angle(
                theta_m_relative_deg
            )
        )

        # ----------------------------------------------------
        # Electrical angle -> voltage-vector angle
        # ----------------------------------------------------

        theta_v_deg = (
            electrical_to_voltage_angle(
                theta_e_deg
            )
        )

        # ----------------------------------------------------
        # Apply phase advance
        # ----------------------------------------------------

        theta_control_deg = (
            apply_phase_advance(
                theta_v_deg
            )
        )

        # ----------------------------------------------------
        # Generate 22 phase angles
        # ----------------------------------------------------

        phase_angles_deg = (
            generate_phase_angles(
                theta_control_deg
            )
        )

        # ----------------------------------------------------
        # Ideal sinusoidal modulation
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Ideal PWM duty
        # ----------------------------------------------------

        pwm_duties = (
            calculate_pwm_duties(
                phase_voltages
            )
        )

        # ----------------------------------------------------
        # Save CSV row
        # ----------------------------------------------------

        row = [
            phi,
            theta_m_deg,
            theta_m_relative_deg,
            theta_e_deg,
            theta_v_deg,
            theta_control_deg,
        ]

        row.extend(
            phase_voltages
        )

        row.extend(
            pwm_duties
        )

        writer.writerow(row)

        # ----------------------------------------------------
        # Store plot data
        # ----------------------------------------------------

        encoder_counts.append(
            phi
        )

        mechanical_angles.append(
            theta_m_deg
        )

        relative_mechanical_angles.append(
            theta_m_relative_deg
        )

        electrical_angles.append(
            theta_e_deg
        )

        voltage_vector_angles.append(
            theta_v_deg
        )

        control_angles.append(
            theta_control_deg
        )

        for i in range(22):

            all_phase_voltages[i].append(
                phase_voltages[i]
            )

            all_phase_duties[i].append(
                pwm_duties[i] * 100.0
            )


# ============================================================
# Automatic checks
# ============================================================

phase1_min = min(
    all_phase_duties[0]
)

phase1_max = max(
    all_phase_duties[0]
)

global_min = min(
    min(phase)
    for phase in all_phase_duties
)

global_max = max(
    max(phase)
    for phase in all_phase_duties
)


# ============================================================
# Check opposite-phase duty relationship
#
# Phase k and Phase k+11 should satisfy:
#
#     duty_k + duty_k+11 = 100%
#
# ============================================================

max_opposite_phase_error = 0.0

for phase_index in range(11):

    for sample_index in range(
        LM10_COUNTS
    ):

        duty_sum = (
            all_phase_duties[
                phase_index
            ][sample_index]
            +
            all_phase_duties[
                phase_index + 11
            ][sample_index]
        )

        error = abs(
            duty_sum - 100.0
        )

        max_opposite_phase_error = max(
            max_opposite_phase_error,
            error,
        )


# ============================================================
# Hover data
# ============================================================

hover_data = list(
    zip(
        encoder_counts,
        relative_mechanical_angles,
        electrical_angles,
        voltage_vector_angles,
        control_angles,
    )
)


# ============================================================
# Create interactive Plotly report
# ============================================================

fig = make_subplots(
    rows=2,
    cols=1,

    shared_xaxes=True,

    vertical_spacing=0.12,

    subplot_titles=(
        "Phase 1 PWM Duty Cycle",
        "All 22 Phase PWM Duty Cycles",
    ),
)


# ============================================================
# Plot 1
#
# Phase 1 only.
#
# Important:
# showlegend=False prevents the extra duplicated
# "Phase 1" entry in the legend.
# ============================================================

fig.add_trace(
    go.Scatter(
        x=mechanical_angles,

        y=all_phase_duties[0],

        mode="lines",

        name="Phase 1",

        showlegend=False,

        customdata=hover_data,

        hovertemplate=(
            "<b>Phase 1</b>"
            "<br><br>"
            "Encoder Position: "
            "%{customdata[0]} count"
            "<br>"
            "Mechanical Rotor Angle θm: "
            "%{x:.3f} deg"
            "<br>"
            "Relative Mechanical Angle: "
            "%{customdata[1]:.3f} deg"
            "<br>"
            "Electrical Angle θe: "
            "%{customdata[2]:.3f} deg"
            "<br>"
            "Voltage Vector Angle θv: "
            "%{customdata[3]:.3f} deg"
            "<br>"
            "Control Angle θcontrol: "
            "%{customdata[4]:.3f} deg"
            "<br>"
            "PWM Duty Cycle: "
            "%{y:.3f} %"
            "<extra></extra>"
        ),
    ),

    row=1,
    col=1,
)


# ============================================================
# Plot 2
#
# All 22 phases.
#
# These are the only traces shown in the legend.
# Therefore the legend contains exactly Phase 1 ... Phase 22.
# ============================================================

for i in range(22):

    fig.add_trace(
        go.Scatter(
            x=mechanical_angles,

            y=all_phase_duties[i],

            mode="lines",

            name=f"Phase {i + 1}",

            customdata=hover_data,

            hovertemplate=(
                f"<b>Phase {i + 1}</b>"
                "<br><br>"
                "Encoder Position: "
                "%{customdata[0]} count"
                "<br>"
                "Mechanical Rotor Angle θm: "
                "%{x:.3f} deg"
                "<br>"
                "Relative Mechanical Angle: "
                "%{customdata[1]:.3f} deg"
                "<br>"
                "Electrical Angle θe: "
                "%{customdata[2]:.3f} deg"
                "<br>"
                "Voltage Vector Angle θv: "
                "%{customdata[3]:.3f} deg"
                "<br>"
                "Control Angle θcontrol: "
                "%{customdata[4]:.3f} deg"
                "<br>"
                "PWM Duty Cycle: "
                "%{y:.3f} %"
                "<extra></extra>"
            ),
        ),

        row=2,
        col=1,
    )


# ============================================================
# X axes
# ============================================================

fig.update_xaxes(
    title_text=(
        "Mechanical Rotor Angle θm (deg)"
    ),

    range=[
        0,
        360,
    ],

    showgrid=True,

    row=1,
    col=1,
)

fig.update_xaxes(
    title_text=(
        "Mechanical Rotor Angle θm (deg)"
    ),

    range=[
        0,
        360,
    ],

    showgrid=True,

    row=2,
    col=1,
)


# ============================================================
# Y axes
# ============================================================

fig.update_yaxes(
    title_text=(
        "PWM Duty Cycle (%)"
    ),

    range=[
        0,
        100,
    ],

    showgrid=True,

    row=1,
    col=1,
)

fig.update_yaxes(
    title_text=(
        "PWM Duty Cycle (%)"
    ),

    range=[
        0,
        100,
    ],

    showgrid=True,

    row=2,
    col=1,
)


# ============================================================
# Reference lines
#
# 50% = PWM center
# 25% / 75% = theoretical limits for amplitude 0.5
# ============================================================

for row in (
    1,
    2,
):

    fig.add_hline(
        y=50,

        line_dash="dash",

        annotation_text=(
            "50% center"
        ),

        annotation_position=(
            "bottom right"
        ),

        row=row,
        col=1,
    )

    fig.add_hline(
        y=25,

        line_dash="dot",

        annotation_text=(
            "25% lower limit"
        ),

        annotation_position=(
            "bottom right"
        ),

        row=row,
        col=1,
    )

    fig.add_hline(
        y=75,

        line_dash="dot",

        annotation_text=(
            "75% upper limit"
        ),

        annotation_position=(
            "top right"
        ),

        row=row,
        col=1,
    )


# ============================================================
# General layout
# ============================================================

fig.update_layout(

    title=dict(
        text=(
            "22-Phase Motor Float Golden Model"
            "<br>"
            "<sup>"
            f"Normalized Voltage Amplitude = "
            f"{VOLTAGE_AMPLITUDE}, "
            f"Phase Advance = "
            f"{PHASE_ADVANCE_DEG} deg"
            "</sup>"
        ),

        x=0.05,
    ),

    height=1000,

    hovermode="x unified",

    legend=dict(
        title=(
            "Phase Channels"
        ),

        groupclick=(
            "toggleitem"
        ),
    ),

    margin=dict(
        l=90,
        r=60,
        t=110,
        b=80,
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
        # Mouse-wheel zoom
        "scrollZoom": True,

        # Remove Plotly logo
        "displaylogo": False,

        # Responsive browser window
        "responsive": True,

        # Keep useful toolbar controls
        "modeBarButtonsToRemove": [
            "lasso2d",
        ],

        # PNG export settings
        "toImageButtonOptions": {
            "format": "png",

            "filename": (
                "float_golden_model"
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
    "22-Phase Float Golden Model"
)

print(
    "Full-Rotation Simulation Complete"
)

print(
    "========================================"
)

print()

print(
    "Encoder samples:",
    LM10_COUNTS,
    "count",
)

print(
    "Mechanical rotation:",
    "0 ... 360 deg",
)

print(
    "Normalized voltage amplitude:",
    VOLTAGE_AMPLITUDE,
)

print(
    "Phase advance:",
    PHASE_ADVANCE_DEG,
    "deg",
)

print()

print(
    "----------------------------------------"
)

print(
    "PWM Duty Cycle Results"
)

print(
    "----------------------------------------"
)

print()

print(
    f"Phase 1 minimum duty: "
    f"{phase1_min:.9f} %"
)

print(
    f"Phase 1 maximum duty: "
    f"{phase1_max:.9f} %"
)

print()

print(
    f"All-phase minimum duty: "
    f"{global_min:.9f} %"
)

print(
    f"All-phase maximum duty: "
    f"{global_max:.9f} %"
)

print()

print(
    "Maximum opposite-phase duty error:"
)

print(
    f"{max_opposite_phase_error:.12e} "
    "percentage points"
)

print()

print(
    "----------------------------------------"
)

print(
    "Generated Files"
)

print(
    "----------------------------------------"
)

print()

print(
    "Raw simulation data:"
)

print(
    CSV_FILE
)

print()

print(
    "Interactive waveform report:"
)

print(
    HTML_FILE
)

print()

print(
    "Open the HTML file in Chrome or Edge."
)