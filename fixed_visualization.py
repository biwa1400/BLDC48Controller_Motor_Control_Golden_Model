# ============================================================
# Fixed-point Golden Model Visualization
# ============================================================
#
# Generates interactive Plotly HTML and CSV files for:
#
#   1. Converted fixed-point waveform LUT
#   2. 22-phase duty waveforms over one mechanical revolution
#   3. One complete center-aligned PWM frame
#   4. Gate-drive switching edges with exact 40 ns deadtime
#
# All output files are written to:
#
#   sim_result/
#
# The numerical calculations are NOT reimplemented here.
# This module reuses the already validated fixed-point models.
#
# ============================================================

from pathlib import Path
import csv

import plotly.graph_objects as go

from config import (
    LM10_COUNTS,
    NUM_PHASES,
)

from fixed_derived_config import (
    AMPLITUDE_SCALE,
    PWM_CLOCK_HZ,
    PWM_TOP,
)

from fixed_waveform_model import (
    load_waveform_lut,
)

from fixed_motor_model import (
    calculate_fixed_motor,
)

from fixed_pwm_model import (
    PWM_PERIOD_CLOCKS,
    generate_one_pwm_carrier_frame,
    pwm_compare_output,
)

from fixed_gate_drive_model import (
    DEADTIME_CLOCKS,
    DEADTIME_NS,
    generate_continuous_gate_waveform,
    find_raw_pwm_transitions,
)


# ============================================================
# Configuration
# ============================================================

OUTPUT_DIR = Path("sim_result")

REFERENCE_ENCODER_COUNT = 1024

REFERENCE_AMPLITUDE_CMD = (
    AMPLITUDE_SCALE // 2
)

REFERENCE_PHASE_INDEX = 0

MECHANICAL_ANGLE_STEP_DEG = (
    360.0 / LM10_COUNTS
)

PWM_CLOCK_PERIOD_NS = (
    1e9 / PWM_CLOCK_HZ
)


# ============================================================
# Output directory
# ============================================================

def ensure_output_directory() -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


# ============================================================
# Generic HTML writer
# ============================================================

def write_html(
    figure: go.Figure,
    filename: str,
) -> Path:

    path = (
        OUTPUT_DIR / filename
    )

    figure.write_html(
        str(path),
        include_plotlyjs=True,
        full_html=True,
    )

    return path


# ============================================================
# Plot 1
#
# LUT waveform
# ============================================================

def generate_lut_visualization(
    waveform_lut,
) -> tuple[Path, Path]:

    csv_path = (
        OUTPUT_DIR
        / "fixed_lut_waveform.csv"
    )

    html_path = (
        OUTPUT_DIR
        / "fixed_lut_waveform.html"
    )

    angles_deg = []
    values_u13 = []
    normalized_values = []

    with csv_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.writer(file)

        writer.writerow(
            [
                "address",
                "angle_deg",
                "value_u13",
                "normalized_magnitude",
            ]
        )

        for address, value in enumerate(
            waveform_lut
        ):

            angle_deg = (
                address
                * 180.0
                / len(waveform_lut)
            )

            normalized = (
                value
                / 4096.0
            )

            angles_deg.append(
                angle_deg
            )

            values_u13.append(
                value
            )

            normalized_values.append(
                normalized
            )

            writer.writerow(
                [
                    address,
                    angle_deg,
                    value,
                    normalized,
                ]
            )

    figure = go.Figure()

    figure.add_trace(
        go.Scatter(
            x=angles_deg,
            y=normalized_values,
            mode="lines",
            name="LUT magnitude",
            customdata=values_u13,
            hovertemplate=(
                "Angle: %{x:.6f}°"
                "<br>LUT: %{customdata}"
                "<br>Normalized: %{y:.8f}"
                "<extra></extra>"
            ),
        )
    )

    figure.update_layout(
        title=(
            "Fixed-point Waveform LUT "
            "(4096 × 13-bit Half-wave)"
        ),
        xaxis_title=(
            "Half-wave angle (degrees)"
        ),
        yaxis_title=(
            "Normalized LUT magnitude"
        ),
        hovermode="x",
    )

    figure.update_xaxes(
        rangeslider_visible=True
    )

    figure.write_html(
        str(html_path),
        include_plotlyjs=True,
        full_html=True,
    )

    return (
        html_path,
        csv_path,
    )


# ============================================================
# Plot 2
#
# 22-phase duty waveforms over one mechanical revolution
# ============================================================

def generate_22phase_duty_visualization(
    waveform_lut,
) -> tuple[Path, Path]:

    csv_path = (
        OUTPUT_DIR
        / "fixed_22phase_duty.csv"
    )

    html_path = (
        OUTPUT_DIR
        / "fixed_22phase_duty.html"
    )

    mechanical_angles = []

    phase_compares = [
        []
        for _ in range(NUM_PHASES)
    ]

    phase_duties = [
        []
        for _ in range(NUM_PHASES)
    ]

    with csv_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.writer(file)

        header = [
            "encoder_count",
            "mechanical_angle_deg",
        ]

        for phase_index in range(
            NUM_PHASES
        ):

            header.append(
                f"phase_{phase_index + 1}_compare"
            )

            header.append(
                f"phase_{phase_index + 1}_duty"
            )

        writer.writerow(
            header
        )

        for encoder_count in range(
            LM10_COUNTS
        ):

            mechanical_angle_deg = (
                encoder_count
                * MECHANICAL_ANGLE_STEP_DEG
            )

            result = (
                calculate_fixed_motor(
                    encoder_count=encoder_count,
                    amplitude_cmd=(
                        REFERENCE_AMPLITUDE_CMD
                    ),
                    waveform_lut=waveform_lut,
                )
            )

            compares = (
                result.phase_compares
            )

            row = [
                encoder_count,
                mechanical_angle_deg,
            ]

            mechanical_angles.append(
                mechanical_angle_deg
            )

            for phase_index, compare in enumerate(
                compares
            ):

                duty = (
                    compare
                    / PWM_TOP
                )

                phase_compares[
                    phase_index
                ].append(
                    compare
                )

                phase_duties[
                    phase_index
                ].append(
                    duty
                )

                row.append(
                    compare
                )

                row.append(
                    duty
                )

            writer.writerow(
                row
            )

    figure = go.Figure()

    for phase_index in range(
        NUM_PHASES
    ):

        customdata = list(
            zip(
                phase_compares[
                    phase_index
                ],
                [
                    duty * 100.0
                    for duty
                    in phase_duties[
                        phase_index
                    ]
                ],
            )
        )

        figure.add_trace(
            go.Scatter(
                x=mechanical_angles,
                y=[
                    duty * 100.0
                    for duty
                    in phase_duties[
                        phase_index
                    ]
                ],
                mode="lines",
                name=(
                    f"Phase "
                    f"{phase_index + 1}"
                ),
                customdata=customdata,
                hovertemplate=(
                    "Mechanical angle: "
                    "%{x:.6f}°"
                    "<br>Duty: "
                    "%{customdata[1]:.8f}%"
                    "<br>Compare: "
                    "%{customdata[0]}"
                    "<extra></extra>"
                ),
            )
        )

    figure.update_layout(
        title=(
            "Fixed-point 22-phase PWM Duty "
            "over One Mechanical Revolution"
            "<br>"
            f"Amplitude command = "
            f"{REFERENCE_AMPLITUDE_CMD}/"
            f"{AMPLITUDE_SCALE} "
            f"= "
            f"{REFERENCE_AMPLITUDE_CMD / AMPLITUDE_SCALE:.3f}"
        ),
        xaxis_title=(
            "Mechanical angle (degrees)"
        ),
        yaxis_title=(
            "PWM duty (%)"
        ),
        hovermode="x unified",
    )

    figure.update_xaxes(
        rangeslider_visible=True
    )

    figure.write_html(
        str(html_path),
        include_plotlyjs=True,
        full_html=True,
    )

    return (
        html_path,
        csv_path,
    )


# ============================================================
# Reference phase compare
# ============================================================

def get_reference_phase_compare(
    waveform_lut,
) -> tuple[int, tuple[int, ...]]:

    result = (
        calculate_fixed_motor(
            encoder_count=(
                REFERENCE_ENCODER_COUNT
            ),
            amplitude_cmd=(
                REFERENCE_AMPLITUDE_CMD
            ),
            waveform_lut=waveform_lut,
        )
    )

    compares = (
        result.phase_compares
    )

    compare = (
        compares[
            REFERENCE_PHASE_INDEX
        ]
    )

    return (
        compare,
        compares,
    )


# ============================================================
# Plot 3
#
# Complete PWM frame
# ============================================================

def generate_pwm_frame_visualization(
    waveform_lut,
) -> tuple[Path, Path]:

    compare, _ = (
        get_reference_phase_compare(
            waveform_lut
        )
    )

    carrier_frame = (
        generate_one_pwm_carrier_frame()
    )

    csv_path = (
        OUTPUT_DIR
        / "fixed_pwm_phase1.csv"
    )

    html_path = (
        OUTPUT_DIR
        / "fixed_pwm_phase1.html"
    )

    time_us = []
    carrier_values = []
    compare_values = []
    raw_pwm_values = []

    with csv_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.writer(file)

        writer.writerow(
            [
                "clock_index",
                "time_us",
                "carrier",
                "direction",
                "compare",
                "raw_pwm",
            ]
        )

        for state in carrier_frame:

            raw_pwm = (
                pwm_compare_output(
                    carrier=state.carrier,
                    direction_down=(
                        state.direction_down
                    ),
                    compare=compare,
                )
            )

            current_time_us = (
                state.clock_index
                * PWM_CLOCK_PERIOD_NS
                / 1000.0
            )

            time_us.append(
                current_time_us
            )

            carrier_values.append(
                state.carrier
            )

            compare_values.append(
                compare
            )

            raw_pwm_values.append(
                raw_pwm
            )

            writer.writerow(
                [
                    state.clock_index,
                    current_time_us,
                    state.carrier,
                    (
                        "DOWN"
                        if state.direction_down
                        else "UP"
                    ),
                    compare,
                    raw_pwm,
                ]
            )

    figure = go.Figure()

    figure.add_trace(
        go.Scatter(
            x=time_us,
            y=carrier_values,
            mode="lines",
            name="Carrier",
            hovertemplate=(
                "Time: %{x:.6f} µs"
                "<br>Carrier: %{y}"
                "<extra></extra>"
            ),
        )
    )

    figure.add_trace(
        go.Scatter(
            x=time_us,
            y=compare_values,
            mode="lines",
            name=(
                f"Phase 1 compare = "
                f"{compare}"
            ),
            hovertemplate=(
                "Time: %{x:.6f} µs"
                "<br>Compare: %{y}"
                "<extra></extra>"
            ),
        )
    )

    # Put raw PWM on a separate y-axis so that 0/1 is easy
    # to inspect without losing the carrier scale.

    figure.add_trace(
        go.Scatter(
            x=time_us,
            y=raw_pwm_values,
            mode="lines",
            line_shape="hv",
            name="Raw PWM",
            yaxis="y2",
            hovertemplate=(
                "Time: %{x:.6f} µs"
                "<br>Raw PWM: %{y}"
                "<extra></extra>"
            ),
        )
    )

    duty = (
        compare
        / PWM_TOP
    )

    figure.update_layout(
        title=(
            "Fixed-point Phase 1 "
            "Center-aligned PWM"
            "<br>"
            f"Encoder = "
            f"{REFERENCE_ENCODER_COUNT}, "
            f"Amplitude = "
            f"{REFERENCE_AMPLITUDE_CMD}/"
            f"{AMPLITUDE_SCALE}, "
            f"Compare = {compare}, "
            f"Duty = {duty * 100.0:.6f}%"
        ),
        xaxis=dict(
            title="Time (µs)",
            rangeslider=dict(
                visible=True
            ),
        ),
        yaxis=dict(
            title="Carrier / Compare",
        ),
        yaxis2=dict(
            title="Raw PWM",
            overlaying="y",
            side="right",
            range=[
                -0.1,
                1.1,
            ],
            tickmode="array",
            tickvals=[
                0,
                1,
            ],
        ),
        hovermode="x unified",
    )

    figure.write_html(
        str(html_path),
        include_plotlyjs=True,
        full_html=True,
    )

    return (
        html_path,
        csv_path,
    )


# ============================================================
# Plot 4
#
# Deadtime waveform
# ============================================================

def generate_deadtime_visualization(
    waveform_lut,
) -> tuple[Path, Path]:

    compare, _ = (
        get_reference_phase_compare(
            waveform_lut
        )
    )

    carrier_frame = (
        generate_one_pwm_carrier_frame()
    )

    # Three continuous frames ensure that the middle frame
    # has valid history and future around both switching edges.

    samples = (
        generate_continuous_gate_waveform(
            compare=compare,
            num_frames=3,
            carrier_frame=carrier_frame,
        )
    )

    transitions = (
        find_raw_pwm_transitions(
            samples
        )
    )

    middle_start = (
        PWM_PERIOD_CLOCKS
    )

    middle_end = (
        2 * PWM_PERIOD_CLOCKS
    )

    middle_transitions = [
        transition
        for transition
        in transitions
        if (
            middle_start
            <= transition.global_clock_index
            < middle_end
        )
    ]

    if not middle_transitions:
        raise AssertionError(
            "No PWM transitions found in middle frame."
        )

    csv_path = (
        OUTPUT_DIR
        / "fixed_deadtime_phase1.csv"
    )

    html_path = (
        OUTPUT_DIR
        / "fixed_deadtime_phase1.html"
    )

    # --------------------------------------------------------
    # CSV:
    #
    # Store the entire middle frame.
    # --------------------------------------------------------

    middle_samples = (
        samples[
            middle_start:
            middle_end
        ]
    )

    with csv_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.writer(file)

        writer.writerow(
            [
                "global_clock_index",
                "frame_clock_index",
                "time_ns_from_frame_start",
                "carrier",
                "compare",
                "raw_pwm",
                "gate_high",
                "gate_low",
                "deadtime_active",
                "deadtime_counter",
            ]
        )

        for sample in middle_samples:

            time_ns = (
                sample.frame_clock_index
                * PWM_CLOCK_PERIOD_NS
            )

            writer.writerow(
                [
                    sample.global_clock_index,
                    sample.frame_clock_index,
                    time_ns,
                    sample.carrier,
                    sample.compare,
                    sample.raw_pwm,
                    sample.gate_high,
                    sample.gate_low,
                    int(
                        sample.deadtime_active
                    ),
                    sample.deadtime_counter,
                ]
            )

    # --------------------------------------------------------
    # HTML:
    #
    # Show windows around both switching edges.
    #
    # We concatenate the useful regions into one physical
    # time axis relative to the middle PWM frame.
    # --------------------------------------------------------

    window_before_clocks = 20
    window_after_clocks = 30

    selected_indices = set()

    for transition in middle_transitions:

        start = max(
            middle_start,
            transition.global_clock_index
            - window_before_clocks,
        )

        end = min(
            middle_end,
            transition.global_clock_index
            + window_after_clocks
            + 1,
        )

        for index in range(
            start,
            end,
        ):
            selected_indices.add(
                index
            )

    selected_indices = sorted(
        selected_indices
    )

    times_ns = []
    raw_values = []
    high_values = []
    low_values = []
    deadtime_counter_values = []

    for index in selected_indices:

        sample = (
            samples[index]
        )

        time_ns = (
            (
                sample.global_clock_index
                - middle_start
            )
            * PWM_CLOCK_PERIOD_NS
        )

        times_ns.append(
            time_ns
        )

        raw_values.append(
            sample.raw_pwm
        )

        # Offset digital signals vertically so they can all be
        # seen clearly in the same plot.

        high_values.append(
            sample.gate_high + 2
        )

        low_values.append(
            sample.gate_low + 4
        )

        deadtime_counter_values.append(
            sample.deadtime_counter
        )

    figure = go.Figure()

    figure.add_trace(
        go.Scatter(
            x=times_ns,
            y=raw_values,
            mode="lines+markers",
            line_shape="hv",
            name="Raw PWM",
            customdata=raw_values,
            hovertemplate=(
                "Time: %{x:.3f} ns"
                "<br>Raw PWM: %{customdata}"
                "<extra></extra>"
            ),
        )
    )

    figure.add_trace(
        go.Scatter(
            x=times_ns,
            y=high_values,
            mode="lines+markers",
            line_shape="hv",
            name="High gate",
            customdata=[
                value - 2
                for value
                in high_values
            ],
            hovertemplate=(
                "Time: %{x:.3f} ns"
                "<br>High: %{customdata}"
                "<extra></extra>"
            ),
        )
    )

    figure.add_trace(
        go.Scatter(
            x=times_ns,
            y=low_values,
            mode="lines+markers",
            line_shape="hv",
            name="Low gate",
            customdata=[
                value - 4
                for value
                in low_values
            ],
            hovertemplate=(
                "Time: %{x:.3f} ns"
                "<br>Low: %{customdata}"
                "<extra></extra>"
            ),
        )
    )

    figure.add_trace(
        go.Scatter(
            x=times_ns,
            y=deadtime_counter_values,
            mode="lines+markers",
            name="Deadtime counter",
            yaxis="y2",
            hovertemplate=(
                "Time: %{x:.3f} ns"
                "<br>Counter: %{y}"
                "<extra></extra>"
            ),
        )
    )

    # --------------------------------------------------------
    # Mark raw PWM transition positions and the corresponding
    # expected turn-on point 40 ns later.
    # --------------------------------------------------------

    for transition_number, transition in enumerate(
        middle_transitions,
        start=1,
    ):

        transition_time_ns = (
            (
                transition.global_clock_index
                - middle_start
            )
            * PWM_CLOCK_PERIOD_NS
        )

        turn_on_time_ns = (
            transition_time_ns
            + DEADTIME_NS
        )

        figure.add_vline(
            x=transition_time_ns,
            line_dash="dash",
            annotation_text=(
                f"T{transition_number}: "
                f"{transition.old_value}"
                f"→"
                f"{transition.new_value}"
            ),
            annotation_position="top",
        )

        figure.add_vline(
            x=turn_on_time_ns,
            line_dash="dot",
            annotation_text=(
                f"+{DEADTIME_NS:.0f} ns"
            ),
            annotation_position="bottom",
        )

    figure.update_layout(
        title=(
            "Fixed-point Phase 1 "
            "Complementary Gate Deadtime"
            "<br>"
            f"8 clocks × "
            f"{PWM_CLOCK_PERIOD_NS:.0f} ns "
            f"= {DEADTIME_NS:.0f} ns"
        ),
        xaxis=dict(
            title=(
                "Time from start of middle "
                "PWM frame (ns)"
            ),
            rangeslider=dict(
                visible=True
            ),
        ),
        yaxis=dict(
            title="Digital signals",
            tickmode="array",
            tickvals=[
                0,
                1,
                2,
                3,
                4,
                5,
            ],
            ticktext=[
                "Raw 0",
                "Raw 1",
                "High 0",
                "High 1",
                "Low 0",
                "Low 1",
            ],
        ),
        yaxis2=dict(
            title="Deadtime counter (clocks)",
            overlaying="y",
            side="right",
            range=[
                0,
                DEADTIME_CLOCKS + 1,
            ],
        ),
        hovermode="x unified",
    )

    figure.write_html(
        str(html_path),
        include_plotlyjs=True,
        full_html=True,
    )

    return (
        html_path,
        csv_path,
    )


# ============================================================
# Print reference point
# ============================================================

def print_reference_point(
    waveform_lut,
) -> None:

    compare, compares = (
        get_reference_phase_compare(
            waveform_lut
        )
    )

    print(
        f"Reference encoder       : "
        f"{REFERENCE_ENCODER_COUNT}"
    )

    print(
        f"Reference amplitude     : "
        f"{REFERENCE_AMPLITUDE_CMD}/"
        f"{AMPLITUDE_SCALE}"
    )

    print(
        f"Reference amplitude     : "
        f"{REFERENCE_AMPLITUDE_CMD / AMPLITUDE_SCALE:.6f}"
    )

    print(
        f"Phase 1 compare         : "
        f"{compare}"
    )

    print(
        f"Phase 1 duty            : "
        f"{compare / PWM_TOP * 100.0:.8f}%"
    )

    print()

    print(
        "22 phase compares:"
    )

    for phase_index, phase_compare in enumerate(
        compares,
        start=1,
    ):

        print(
            f"  Phase "
            f"{phase_index:2d}: "
            f"compare="
            f"{phase_compare:4d}  "
            f"duty="
            f"{phase_compare / PWM_TOP * 100.0:11.8f}%"
        )


# ============================================================
# Main
# ============================================================

def main() -> None:

    ensure_output_directory()

    print(
        "========================================"
    )

    print(
        " Fixed-point visualization"
    )

    print(
        "========================================"
    )

    print()

    print(
        "Loading waveform LUT..."
    )

    waveform_lut = (
        load_waveform_lut()
    )

    print(
        "Waveform LUT loaded"
    )

    print()

    print_reference_point(
        waveform_lut
    )

    print()

    # --------------------------------------------------------
    # LUT
    # --------------------------------------------------------

    print(
        "Generating LUT visualization..."
    )

    lut_html, lut_csv = (
        generate_lut_visualization(
            waveform_lut
        )
    )

    print(
        f"  HTML : {lut_html}"
    )

    print(
        f"  CSV  : {lut_csv}"
    )

    print()

    # --------------------------------------------------------
    # 22 phase duty
    # --------------------------------------------------------

    print(
        "Generating 22-phase duty visualization..."
    )

    duty_html, duty_csv = (
        generate_22phase_duty_visualization(
            waveform_lut
        )
    )

    print(
        f"  HTML : {duty_html}"
    )

    print(
        f"  CSV  : {duty_csv}"
    )

    print()

    # --------------------------------------------------------
    # PWM frame
    # --------------------------------------------------------

    print(
        "Generating Phase 1 PWM visualization..."
    )

    pwm_html, pwm_csv = (
        generate_pwm_frame_visualization(
            waveform_lut
        )
    )

    print(
        f"  HTML : {pwm_html}"
    )

    print(
        f"  CSV  : {pwm_csv}"
    )

    print()

    # --------------------------------------------------------
    # Deadtime
    # --------------------------------------------------------

    print(
        "Generating Phase 1 deadtime visualization..."
    )

    deadtime_html, deadtime_csv = (
        generate_deadtime_visualization(
            waveform_lut
        )
    )

    print(
        f"  HTML : {deadtime_html}"
    )

    print(
        f"  CSV  : {deadtime_csv}"
    )

    print()

    print(
        "========================================"
    )

    print(
        " Fixed visualization generation PASS"
    )

    print(
        "========================================"
    )


if __name__ == "__main__":
    main()