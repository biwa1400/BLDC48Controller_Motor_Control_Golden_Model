# ============================================================
# Level 2 SystemVerilog test-vector generator
# ============================================================
#
# Generates bit-exact vectors for:
#
#   encoder_phi
#       + amplitude
#       + runtime phase_advance_u16
#       -> 22 PWM compare values
#
# The numerical implementation is NOT duplicated here.
# All expected values come directly from the validated
# fixed_motor_model / fixed_angle_model / fixed_waveform_model.
#
# Output format:
#
#   encoder amplitude phase_advance compare1 ... compare22
#
# 25 decimal integers per line.
#
# ============================================================

from pathlib import Path

from fixed_derived_config import (
    AMPLITUDE_SCALE,
    PHASE_ADVANCE_COUNTS,
)

from fixed_motor_model import (
    calculate_fixed_motor,
)

from fixed_waveform_model import (
    load_waveform_lut,
)


NUM_PHASES = 22


# ============================================================
# Output path
# ============================================================

OUTPUT_PATH = Path(
    r"C:\project\BLDC48Controller_FPGA_NEW"
) / "tb" / "motor_control" / "data" / "level2_vectors.txt"


# ============================================================
# Test cases
# ============================================================
#
# Each tuple:
#
#   (
#       descriptive_name,
#       encoder_phi,
#       amplitude_cmd,
#       phase_advance_u16,
#   )
#
# ============================================================

TEST_CASES = (
    # Frozen reference point.
    (
        "reference",
        1024,
        AMPLITUDE_SCALE // 2,
        PHASE_ADVANCE_COUNTS,
    ),

    # Encoder zero offset.
    (
        "encoder_zero_offset",
        1022,
        AMPLITUDE_SCALE // 2,
        PHASE_ADVANCE_COUNTS,
    ),

    # Raw encoder-domain boundaries / wrap behavior.
    (
        "encoder_raw_min",
        0,
        AMPLITUDE_SCALE // 2,
        PHASE_ADVANCE_COUNTS,
    ),
    (
        "encoder_raw_max",
        4095,
        AMPLITUDE_SCALE // 2,
        PHASE_ADVANCE_COUNTS,
    ),

    # Amplitude boundaries.
    (
        "amplitude_zero",
        1024,
        0,
        PHASE_ADVANCE_COUNTS,
    ),
    (
        "amplitude_full",
        1024,
        AMPLITUDE_SCALE,
        PHASE_ADVANCE_COUNTS,
    ),

    # Runtime phase-advance checks.
    (
        "phase_advance_zero",
        1024,
        AMPLITUDE_SCALE // 2,
        0,
    ),
    (
        "phase_advance_90deg",
        1024,
        AMPLITUDE_SCALE // 2,
        16384,
    ),
    (
        "phase_advance_180deg",
        1024,
        AMPLITUDE_SCALE // 2,
        32768,
    ),
    (
        "phase_advance_270deg",
        1024,
        AMPLITUDE_SCALE // 2,
        49152,
    ),

    # Representative mixed operating points.
    (
        "mixed_1",
        1,
        1024,
        500,
    ),
    (
        "mixed_2",
        777,
        3072,
        4096,
    ),
    (
        "mixed_3",
        2048,
        4096,
        8192,
    ),
    (
        "mixed_4",
        3000,
        1536,
        12345,
    ),
    (
        "mixed_5",
        4094,
        3584,
        65535,
    ),
)


# ============================================================
# Validation helpers
# ============================================================

def validate_test_case(
    encoder_phi: int,
    amplitude_cmd: int,
    phase_advance_u16: int,
) -> None:

    if not 0 <= encoder_phi <= 4095:
        raise ValueError(
            f"encoder_phi out of range: {encoder_phi}"
        )

    if not 0 <= amplitude_cmd <= AMPLITUDE_SCALE:
        raise ValueError(
            f"amplitude_cmd out of legal range: {amplitude_cmd}"
        )

    if not 0 <= phase_advance_u16 <= 0xFFFF:
        raise ValueError(
            f"phase_advance_u16 out of range: "
            f"{phase_advance_u16}"
        )


# ============================================================
# Main
# ============================================================

def main() -> None:

    waveform_lut = load_waveform_lut()

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    lines = []

    print(
        "========================================"
    )
    print(
        " Level 2 Golden vector generation"
    )
    print(
        "========================================"
    )
    print()

    for (
        case_index,
        (
            case_name,
            encoder_phi,
            amplitude_cmd,
            phase_advance_u16,
        ),
    ) in enumerate(
        TEST_CASES
    ):

        validate_test_case(
            encoder_phi,
            amplitude_cmd,
            phase_advance_u16,
        )

        result = calculate_fixed_motor(
            encoder_count=encoder_phi,
            amplitude_cmd=amplitude_cmd,
            waveform_lut=waveform_lut,
            phase_advance_u16=phase_advance_u16,
        )

        if len(
            result.phase_compares
        ) != NUM_PHASES:
            raise AssertionError(
                f"{case_name}: expected "
                f"{NUM_PHASES} compare values, got "
                f"{len(result.phase_compares)}"
            )

        fields = [
            encoder_phi,
            amplitude_cmd,
            phase_advance_u16,
            *result.phase_compares,
        ]

        if len(fields) != 25:
            raise AssertionError(
                f"{case_name}: expected 25 fields, "
                f"got {len(fields)}"
            )

        line = " ".join(
            str(value)
            for value in fields
        )

        lines.append(line)

        print(
            f"[{case_index:02d}] "
            f"{case_name:<24} "
            f"phi={encoder_phi:4d}  "
            f"A={amplitude_cmd:4d}  "
            f"adv={phase_advance_u16:5d}  "
            f"C1={result.phase_compares[0]:4d}  "
            f"C22={result.phase_compares[-1]:4d}"
        )

    OUTPUT_PATH.write_text(
        "\n".join(lines) + "\n",
        encoding="ascii",
    )

    # Re-read the generated file so file formatting itself is
    # validated before it is handed to the SV testbench.
    generated_lines = (
        OUTPUT_PATH
        .read_text(
            encoding="ascii"
        )
        .splitlines()
    )

    if len(
        generated_lines
    ) != len(
        TEST_CASES
    ):
        raise AssertionError(
            "Generated vector count mismatch."
        )

    for (
        line_index,
        line,
    ) in enumerate(
        generated_lines
    ):

        fields = line.split()

        if len(fields) != 25:
            raise AssertionError(
                f"Output line {line_index + 1} "
                f"contains {len(fields)} fields, "
                f"expected 25."
            )

        # Ensure every field is a plain decimal integer.
        tuple(
            int(field, 10)
            for field in fields
        )

    print()
    print(
        f"Generated vectors : "
        f"{len(generated_lines)}"
    )
    print(
        f"Fields per vector : 25"
    )
    print(
        f"Output            : {OUTPUT_PATH}"
    )
    print()
    print(
        "========================================"
    )
    print(
        " LEVEL 2 VECTOR GENERATION PASS"
    )
    print(
        "========================================"
    )


if __name__ == "__main__":
    main()
