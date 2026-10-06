# ============================================================
# Level 7 SystemVerilog end-to-end Golden vector generator
# ============================================================
#
# Generates bit-exact vectors for:
#
#   encoder_phi
#       + amplitude
#       + runtime phase_advance_u16
#       -> complete motor_drive_core
#       -> 22 committed PWM compare values
#
# The numerical implementation is NOT duplicated here.
# All expected compare values come directly from the validated
# fixed_motor_model / fixed_angle_model / fixed_waveform_model.
#
# Output format:
#
#   encoder amplitude phase_advance compare1 ... compare22
#
# 25 decimal integers per line.
#
# Level 7 vector set:
#
#   15 frozen Level-2 boundary / representative cases
#   17 deterministic pseudo-random cases
#
# Total:
#
#   32 vectors
#   32 * 22 = 704 Golden compare values
#
# ============================================================

from pathlib import Path
import random

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


# ============================================================
# Constants
# ============================================================

NUM_PHASES = 22

NUM_BASE_VECTORS = 15
NUM_RANDOM_VECTORS = 17
NUM_TOTAL_VECTORS = (
    NUM_BASE_VECTORS
    + NUM_RANDOM_VECTORS
)

RANDOM_SEED = 0x48C00007


# ============================================================
# Output path
# ============================================================

OUTPUT_PATH = Path(
    r"C:\project\BLDC48Controller_FPGA_NEW"
) / "tb" / "motor_control" / "data" / "level7_vectors.txt"


# ============================================================
# Frozen base test cases
#
# These are intentionally identical to the validated Level-2
# test cases.
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

BASE_TEST_CASES = (
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
            f"encoder_phi out of range: "
            f"{encoder_phi}"
        )

    if not 0 <= amplitude_cmd <= AMPLITUDE_SCALE:
        raise ValueError(
            f"amplitude_cmd out of legal range: "
            f"{amplitude_cmd}"
        )

    if not 0 <= phase_advance_u16 <= 0xFFFF:
        raise ValueError(
            f"phase_advance_u16 out of range: "
            f"{phase_advance_u16}"
        )


def validate_compare_values(
    case_name: str,
    phase_compares,
) -> None:

    if len(phase_compares) != NUM_PHASES:
        raise AssertionError(
            f"{case_name}: expected "
            f"{NUM_PHASES} compare values, got "
            f"{len(phase_compares)}"
        )

    for (
        phase_index,
        compare_value,
    ) in enumerate(
        phase_compares
    ):

        if not 0 <= compare_value <= 6666:
            raise AssertionError(
                f"{case_name}: "
                f"phase {phase_index} compare "
                f"out of range: "
                f"{compare_value}"
            )


# ============================================================
# Deterministic random cases
# ============================================================

def generate_random_test_cases():

    rng = random.Random(
        RANDOM_SEED
    )

    test_cases = []

    existing_vectors = {
        (
            encoder_phi,
            amplitude_cmd,
            phase_advance_u16,
        )
        for (
            _,
            encoder_phi,
            amplitude_cmd,
            phase_advance_u16,
        ) in BASE_TEST_CASES
    }

    random_index = 0

    while len(test_cases) < NUM_RANDOM_VECTORS:

        encoder_phi = rng.randint(
            0,
            4095,
        )

        amplitude_cmd = rng.randint(
            0,
            AMPLITUDE_SCALE,
        )

        phase_advance_u16 = rng.randint(
            0,
            0xFFFF,
        )

        vector = (
            encoder_phi,
            amplitude_cmd,
            phase_advance_u16,
        )

        if vector in existing_vectors:
            continue

        existing_vectors.add(
            vector
        )

        test_cases.append(
            (
                f"random_{random_index:02d}",
                encoder_phi,
                amplitude_cmd,
                phase_advance_u16,
            )
        )

        random_index += 1

    return tuple(
        test_cases
    )


# ============================================================
# Main
# ============================================================

def main() -> None:

    print(
        "========================================"
    )
    print(
        " Level 7 Golden vector generation"
    )
    print(
        "========================================"
    )
    print()

    # --------------------------------------------------------
    # Load the exact LUT used by the validated Golden Model.
    #
    # Use the same load_waveform_lut() interface already used
    # by the validated Level-2 vector generator.
    # --------------------------------------------------------

    waveform_lut = load_waveform_lut()

    # --------------------------------------------------------
    # Build complete deterministic test set.
    # --------------------------------------------------------

    random_test_cases = (
        generate_random_test_cases()
    )

    test_cases = (
        BASE_TEST_CASES
        + random_test_cases
    )

    if len(BASE_TEST_CASES) != NUM_BASE_VECTORS:
        raise AssertionError(
            "Base vector count mismatch: "
            f"{len(BASE_TEST_CASES)} != "
            f"{NUM_BASE_VECTORS}"
        )

    if len(random_test_cases) != NUM_RANDOM_VECTORS:
        raise AssertionError(
            "Random vector count mismatch: "
            f"{len(random_test_cases)} != "
            f"{NUM_RANDOM_VECTORS}"
        )

    if len(test_cases) != NUM_TOTAL_VECTORS:
        raise AssertionError(
            "Total vector count mismatch: "
            f"{len(test_cases)} != "
            f"{NUM_TOTAL_VECTORS}"
        )

    # --------------------------------------------------------
    # Prepare output directory.
    # --------------------------------------------------------

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    lines = []

    total_compare_count = 0

    # --------------------------------------------------------
    # Generate Golden vectors.
    # --------------------------------------------------------

    for (
        case_index,
        (
            case_name,
            encoder_phi,
            amplitude_cmd,
            phase_advance_u16,
        ),
    ) in enumerate(
        test_cases
    ):

        validate_test_case(
            encoder_phi,
            amplitude_cmd,
            phase_advance_u16,
        )

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # This is the exact existing Fixed-Point Golden Model
        # interface.
        #
        # No motor-control arithmetic is duplicated here.
        # ----------------------------------------------------

        result = calculate_fixed_motor(
            encoder_count=encoder_phi,
            amplitude_cmd=amplitude_cmd,
            waveform_lut=waveform_lut,
            phase_advance_u16=phase_advance_u16,
        )

        validate_compare_values(
            case_name,
            result.phase_compares,
        )

        fields = [
            encoder_phi,
            amplitude_cmd,
            phase_advance_u16,
            *result.phase_compares,
        ]

        if len(fields) != 25:
            raise AssertionError(
                f"{case_name}: expected "
                f"25 fields, got "
                f"{len(fields)}"
            )

        line = " ".join(
            str(value)
            for value in fields
        )

        lines.append(
            line
        )

        total_compare_count += (
            len(
                result.phase_compares
            )
        )

        print(
            f"[{case_index:02d}] "
            f"{case_name:<24} "
            f"phi={encoder_phi:4d}  "
            f"A={amplitude_cmd:4d}  "
            f"adv={phase_advance_u16:5d}  "
            f"C1={result.phase_compares[0]:4d}  "
            f"C22={result.phase_compares[-1]:4d}"
        )

    # --------------------------------------------------------
    # Validate total compare count.
    # --------------------------------------------------------

    expected_compare_count = (
        NUM_TOTAL_VECTORS
        * NUM_PHASES
    )

    if total_compare_count != expected_compare_count:
        raise AssertionError(
            "Golden compare count mismatch: "
            f"{total_compare_count} != "
            f"{expected_compare_count}"
        )

    # --------------------------------------------------------
    # Write vector file.
    #
    # Keep format deliberately simple for old VCS:
    #
    #   decimal integers only
    #   whitespace separated
    #   one vector per line
    #   no header
    # --------------------------------------------------------

    OUTPUT_PATH.write_text(
        "\n".join(lines) + "\n",
        encoding="ascii",
    )

    # --------------------------------------------------------
    # Re-read generated file.
    #
    # Validate the actual file handed to SystemVerilog.
    # --------------------------------------------------------

    generated_lines = (
        OUTPUT_PATH
        .read_text(
            encoding="ascii"
        )
        .splitlines()
    )

    if len(generated_lines) != NUM_TOTAL_VECTORS:
        raise AssertionError(
            "Generated vector count mismatch: "
            f"{len(generated_lines)} != "
            f"{NUM_TOTAL_VECTORS}"
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
                f"Output line "
                f"{line_index + 1} "
                f"contains "
                f"{len(fields)} fields, "
                f"expected 25."
            )

        # Ensure every field is a plain decimal integer.
        tuple(
            int(
                field,
                10,
            )
            for field in fields
        )

    # --------------------------------------------------------
    # Final summary
    # --------------------------------------------------------

    print()
    print(
        f"Generated vectors : "
        f"{len(generated_lines)}"
    )
    print(
        f"Base vectors      : "
        f"{len(BASE_TEST_CASES)}"
    )
    print(
        f"Random vectors    : "
        f"{len(random_test_cases)}"
    )
    print(
        f"Random seed       : "
        f"0x{RANDOM_SEED:08X}"
    )
    print(
        f"Phases per vector : "
        f"{NUM_PHASES}"
    )
    print(
        "Fields per vector : 25"
    )
    print(
        f"Golden compares   : "
        f"{total_compare_count}"
    )
    print(
        f"Output            : "
        f"{OUTPUT_PATH}"
    )
    print()

    print(
        "========================================"
    )
    print(
        " LEVEL 7 VECTOR GENERATION PASS"
    )
    print(
        "========================================"
    )


if __name__ == "__main__":
    main()