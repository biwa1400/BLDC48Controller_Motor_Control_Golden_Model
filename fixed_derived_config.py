# ============================================================
# Derived fixed-point FPGA constants
# ============================================================
#
# This file contains constants that are automatically derived
# from:
#
#   config.py
#   fixed_format_config.py
#
# Do NOT manually insert FPGA magic numbers here unless they
# are mathematically derived from the design specification.
#
# The values generated here will later be mirrored exactly
# in the SystemVerilog implementation.
#
# This file also generates a human-readable configuration
# report:
#
#   sim_result/fixed_derived_config.txt
#
# ============================================================

from io import StringIO
from pathlib import Path

from config import (
    LM10_COUNTS,
    POLE_PAIRS,
    NUM_PHASES,
    PHASE_ADVANCE_DEG,
    PWM_FREQUENCY_HZ,
    DEADTIME_LH_NS,
    DEADTIME_HL_NS,
)

from fixed_format_config import (
    CALC_CLOCK_HZ,
    PWM_CLOCK_HZ,
    ANGLE_BITS,
    WAVEFORM_LUT_ADDRESS_BITS,
    WAVEFORM_LUT_DATA_BITS,
    WAVEFORM_LUT_SCALE_BITS,
    AMPLITUDE_BITS,
    AMPLITUDE_FRAC_BITS,
    PWM_TOP_MUST_BE_EVEN,
    ROUNDING_MODE,
)


# ============================================================
# Output files
# ============================================================

SIM_RESULT_DIR = Path("sim_result")

DERIVED_CONFIG_REPORT_FILE = (
    SIM_RESULT_DIR
    / "fixed_derived_config.txt"
)


# ============================================================
# Helper functions
# ============================================================

def round_half_up_positive(value: float) -> int:
    """
    Round a non-negative floating-point value using
    ROUND_HALF_UP semantics.

    Examples:

        1.4 -> 1
        1.5 -> 2
        2.5 -> 3

    Python's built-in round() is intentionally NOT used
    because Python uses ties-to-even rounding.
    """

    if value < 0:
        raise ValueError(
            "round_half_up_positive() only accepts "
            "non-negative values."
        )

    return int(value + 0.5)


# ============================================================
# Internal angle representation
# ============================================================

ANGLE_MODULUS = 1 << ANGLE_BITS

ANGLE_MASK = ANGLE_MODULUS - 1

ANGLE_90 = ANGLE_MODULUS // 4

ANGLE_180 = ANGLE_MODULUS // 2

ANGLE_270 = (
    3 * ANGLE_MODULUS // 4
)

ANGLE_DEG_PER_COUNT = (
    360.0 / ANGLE_MODULUS
)


# ============================================================
# Encoder -> internal angle conversion
# ============================================================

# LM10 currently has:
#
#     4096 counts = 2^12
#
# Internal angle:
#
#     65536 counts = 2^16
#
# Therefore:
#
#     theta_m16 = encoder_relative << 4
#
# is exact.

LM10_BITS = (
    LM10_COUNTS - 1
).bit_length()


if (
    1 << LM10_BITS
) != LM10_COUNTS:

    raise ValueError(
        "LM10_COUNTS must be a power of two "
        "for the current shift-based encoder "
        "conversion."
    )


ENCODER_TO_ANGLE_SHIFT = (
    ANGLE_BITS
    - LM10_BITS
)


if ENCODER_TO_ANGLE_SHIFT < 0:

    raise ValueError(
        "Internal angle width is smaller "
        "than encoder width."
    )


# ============================================================
# Phase advance quantization
# ============================================================

PHASE_ADVANCE_IDEAL_COUNTS = (
    PHASE_ADVANCE_DEG
    / 360.0
    * ANGLE_MODULUS
)


PHASE_ADVANCE_COUNTS = (
    round_half_up_positive(
        PHASE_ADVANCE_IDEAL_COUNTS
    )
)


PHASE_ADVANCE_ACTUAL_DEG = (
    PHASE_ADVANCE_COUNTS
    * 360.0
    / ANGLE_MODULUS
)


PHASE_ADVANCE_ERROR_DEG = (
    PHASE_ADVANCE_ACTUAL_DEG
    - PHASE_ADVANCE_DEG
)


# ============================================================
# Phase offsets
# ============================================================

# Each phase offset is rounded independently.
#
# Do NOT repeatedly add one rounded phase step.
#
# Independent rounding prevents cumulative phase error and
# guarantees that opposite phases remain exactly 180 degrees
# apart in the current 22-phase architecture.

PHASE_OFFSETS = tuple(

    round_half_up_positive(
        phase_index
        * ANGLE_MODULUS
        / NUM_PHASES
    )
    & ANGLE_MASK

    for phase_index
    in range(NUM_PHASES)
)


# ============================================================
# Waveform LUT geometry
# ============================================================

WAVEFORM_LUT_DEPTH = (
    1
    << WAVEFORM_LUT_ADDRESS_BITS
)


WAVEFORM_LUT_SCALE = (
    1
    << WAVEFORM_LUT_SCALE_BITS
)


WAVEFORM_LUT_STORAGE_MAX = (
    (1 << WAVEFORM_LUT_DATA_BITS)
    - 1
)


# One half-wave occupies:
#
#     0 ... 180 degrees
#
# which is exactly half of the U16 angle space.

HALF_WAVE_ANGLE_COUNTS = (
    ANGLE_180
)


if (
    HALF_WAVE_ANGLE_COUNTS
    % WAVEFORM_LUT_DEPTH
) != 0:

    raise ValueError(
        "Half-wave angle range must divide "
        "exactly by LUT depth."
    )


LUT_ANGLE_COUNTS_PER_ADDRESS = (
    HALF_WAVE_ANGLE_COUNTS
    // WAVEFORM_LUT_DEPTH
)


# Current architecture:
#
#     32768 / 4096 = 8
#
# Therefore:
#
#     LUT address = angle[14:3]

LUT_ADDRESS_SHIFT = (
    LUT_ANGLE_COUNTS_PER_ADDRESS
    .bit_length()
    - 1
)


if (
    1 << LUT_ADDRESS_SHIFT
) != LUT_ANGLE_COUNTS_PER_ADDRESS:

    raise ValueError(
        "Current LUT address extraction "
        "requires a power-of-two angle step."
    )


# ============================================================
# Amplitude representation
# ============================================================

AMPLITUDE_SCALE = (
    1
    << AMPLITUDE_FRAC_BITS
)


AMPLITUDE_STORAGE_MAX = (
    (1 << AMPLITUDE_BITS)
    - 1
)


# Legal control range:
#
#     0    = 0.0
#     4096 = 1.0

AMPLITUDE_MAX_COMMAND = (
    AMPLITUDE_SCALE
)


# ============================================================
# PWM carrier
# ============================================================

# Center-aligned triangular PWM:
#
#     f_pwm =
#         f_pwm_clock
#         / (2 * TOP)
#
# Therefore:
#
#     ideal_TOP =
#         f_pwm_clock
#         / (2 * requested_pwm_frequency)

PWM_TOP_IDEAL = (
    PWM_CLOCK_HZ
    / (
        2.0
        * PWM_FREQUENCY_HZ
    )
)


PWM_TOP = (
    round_half_up_positive(
        PWM_TOP_IDEAL
    )
)


# Require even TOP so that:
#
#     PWM_CENTER = PWM_TOP / 2
#
# is exactly an integer.

if (
    PWM_TOP_MUST_BE_EVEN
    and
    PWM_TOP % 2 != 0
):

    lower_even = (
        PWM_TOP - 1
    )

    upper_even = (
        PWM_TOP + 1
    )

    lower_error = abs(
        lower_even
        - PWM_TOP_IDEAL
    )

    upper_error = abs(
        upper_even
        - PWM_TOP_IDEAL
    )

    if (
        lower_error
        <= upper_error
    ):

        PWM_TOP = (
            lower_even
        )

    else:

        PWM_TOP = (
            upper_even
        )


PWM_CENTER = (
    PWM_TOP // 2
)


PWM_PERIOD_CLOCKS = (
    2 * PWM_TOP
)


PWM_ACTUAL_FREQUENCY_HZ = (
    PWM_CLOCK_HZ
    / PWM_PERIOD_CLOCKS
)


PWM_FREQUENCY_ERROR_HZ = (
    PWM_ACTUAL_FREQUENCY_HZ
    - PWM_FREQUENCY_HZ
)


PWM_FREQUENCY_ERROR_PERCENT = (
    PWM_FREQUENCY_ERROR_HZ
    / PWM_FREQUENCY_HZ
    * 100.0
)


PWM_PERIOD_S = (
    PWM_PERIOD_CLOCKS
    / PWM_CLOCK_HZ
)


PWM_PERIOD_US = (
    PWM_PERIOD_S
    * 1_000_000.0
)


# ============================================================
# Fixed-point PWM scaling
# ============================================================

# Waveform:
#
#     W_real = W / 4096
#
# Amplitude:
#
#     A_real = A / 4096
#
# Therefore:
#
#     W_real * A_real
#
# corresponds to:
#
#     W * A / 2^24

PWM_SCALE_DENOMINATOR_BITS = (
    WAVEFORM_LUT_SCALE_BITS
    + AMPLITUDE_FRAC_BITS
)


PWM_SCALE_DENOMINATOR = (
    1
    << PWM_SCALE_DENOMINATOR_BITS
)


# ROUND_HALF_UP:
#
#     delta =
#
#       (
#           scaled_value
#           + 2^(N-1)
#       )
#       >> N

PWM_ROUNDING_BIAS = (
    1
    << (
        PWM_SCALE_DENOMINATOR_BITS
        - 1
    )
)


# ============================================================
# Arithmetic widths
# ============================================================

# Generic storage width for:
#
#     waveform * amplitude
#
# 13-bit x 13-bit -> 26-bit storage.

WAVEFORM_AMPLITUDE_PRODUCT_BITS = (
    WAVEFORM_LUT_DATA_BITS
    + AMPLITUDE_BITS
)


# Maximum LEGAL control values.
#
# Note:
#
# Although the 13-bit storage can represent values larger
# than 4096, the legal normalized waveform and amplitude
# ranges are both limited to 4096.

MAX_WAVEFORM_AMPLITUDE_PRODUCT = (
    WAVEFORM_LUT_SCALE
    * AMPLITUDE_MAX_COMMAND
)


MAX_PWM_SCALED_VALUE = (
    MAX_WAVEFORM_AMPLITUDE_PRODUCT
    * PWM_CENTER
)


PWM_SCALED_VALUE_BITS = (
    MAX_PWM_SCALED_VALUE
    .bit_length()
)


# ============================================================
# Deadtime
# ============================================================

PWM_CLOCK_PERIOD_NS = (
    1_000_000_000.0
    / PWM_CLOCK_HZ
)


DEADTIME_LH_CLOCKS = (
    round_half_up_positive(
        DEADTIME_LH_NS
        / PWM_CLOCK_PERIOD_NS
    )
)


DEADTIME_HL_CLOCKS = (
    round_half_up_positive(
        DEADTIME_HL_NS
        / PWM_CLOCK_PERIOD_NS
    )
)


DEADTIME_LH_ACTUAL_NS = (
    DEADTIME_LH_CLOCKS
    * PWM_CLOCK_PERIOD_NS
)


DEADTIME_HL_ACTUAL_NS = (
    DEADTIME_HL_CLOCKS
    * PWM_CLOCK_PERIOD_NS
)


DEADTIME_LH_ERROR_NS = (
    DEADTIME_LH_ACTUAL_NS
    - DEADTIME_LH_NS
)


DEADTIME_HL_ERROR_NS = (
    DEADTIME_HL_ACTUAL_NS
    - DEADTIME_HL_NS
)


# ============================================================
# Calculation timing estimate
# ============================================================

# Proposed sequential phase FSM:
#
#   1. PHASE_ANGLE
#   2. LUT_READ
#   3. LUT_WAIT
#   4. LUT_CAPTURE
#   5. MULTIPLY
#   6. PWM_SCALE
#   7. ROUND
#   8. COMPARE
#   9. STORE

CALC_CLOCKS_PER_PHASE_ESTIMATE = 9


CALC_CLOCKS_PER_BATCH_ESTIMATE = (
    CALC_CLOCKS_PER_PHASE_ESTIMATE
    * NUM_PHASES
)


CALC_BATCH_TIME_S_ESTIMATE = (
    CALC_CLOCKS_PER_BATCH_ESTIMATE
    / CALC_CLOCK_HZ
)


CALC_BATCH_TIME_US_ESTIMATE = (
    CALC_BATCH_TIME_S_ESTIMATE
    * 1_000_000.0
)


CALC_FRAME_UTILIZATION_PERCENT = (
    CALC_BATCH_TIME_S_ESTIMATE
    / PWM_PERIOD_S
    * 100.0
)


# ============================================================
# Related clock information
# ============================================================

# Current architecture:
#
#     PWM clock  = 200 MHz
#     CALC clock =  50 MHz
#
# Both are generated from the same PLL.
#
# The ratio should currently be an exact integer.

if (
    PWM_CLOCK_HZ
    % CALC_CLOCK_HZ
) != 0:

    raise ValueError(
        "PWM clock must currently be an integer "
        "multiple of CALC clock."
    )


PWM_TO_CALC_CLOCK_RATIO = (
    PWM_CLOCK_HZ
    // CALC_CLOCK_HZ
)


# ============================================================
# Architecture validation
# ============================================================

assert (
    ROUNDING_MODE
    == "ROUND_HALF_UP"
)


# ------------------------------------------------------------
# Angle validation
# ------------------------------------------------------------

assert ANGLE_MODULUS == 65536

assert ANGLE_MASK == 65535

assert ANGLE_90 == 16384

assert ANGLE_180 == 32768

assert ANGLE_270 == 49152


# ------------------------------------------------------------
# Encoder validation
# ------------------------------------------------------------

assert LM10_COUNTS == 4096

assert LM10_BITS == 12

assert (
    ENCODER_TO_ANGLE_SHIFT
    == 4
)


# ------------------------------------------------------------
# Phase validation
# ------------------------------------------------------------

assert NUM_PHASES == 22

assert len(PHASE_OFFSETS) == NUM_PHASES

assert PHASE_OFFSETS[0] == 0

assert (
    PHASE_OFFSETS[
        NUM_PHASES // 2
    ]
    == ANGLE_180
)


# Opposite phase must be exactly
# 180 degrees apart.

for phase_index in range(
    NUM_PHASES // 2
):

    opposite_index = (
        phase_index
        + NUM_PHASES // 2
    )

    expected_offset = (
        PHASE_OFFSETS[
            phase_index
        ]
        + ANGLE_180
    ) & ANGLE_MASK

    assert (
        PHASE_OFFSETS[
            opposite_index
        ]
        == expected_offset
    )


# ------------------------------------------------------------
# LUT validation
# ------------------------------------------------------------

assert (
    WAVEFORM_LUT_DEPTH
    == 4096
)

assert (
    WAVEFORM_LUT_SCALE
    == 4096
)

assert (
    LUT_ANGLE_COUNTS_PER_ADDRESS
    == 8
)

assert (
    LUT_ADDRESS_SHIFT
    == 3
)

assert (
    WAVEFORM_LUT_SCALE
    <= WAVEFORM_LUT_STORAGE_MAX
)


# ------------------------------------------------------------
# Amplitude validation
# ------------------------------------------------------------

assert (
    AMPLITUDE_SCALE
    == 4096
)

assert (
    AMPLITUDE_MAX_COMMAND
    <= AMPLITUDE_STORAGE_MAX
)


# ------------------------------------------------------------
# PWM validation
# ------------------------------------------------------------

assert PWM_TOP > 0

if PWM_TOP_MUST_BE_EVEN:

    assert (
        PWM_TOP % 2
        == 0
    )


assert (
    PWM_CENTER * 2
    == PWM_TOP
)


# Current frozen architecture.

assert PWM_TOP == 6666

assert PWM_CENTER == 3333

assert (
    PWM_PERIOD_CLOCKS
    == 13332
)


# ------------------------------------------------------------
# Deadtime validation
# ------------------------------------------------------------

assert (
    DEADTIME_LH_CLOCKS
    == 8
)

assert (
    DEADTIME_HL_CLOCKS
    == 8
)


# ------------------------------------------------------------
# Clock validation
# ------------------------------------------------------------

assert (
    PWM_TO_CALC_CLOCK_RATIO
    == 4
)


# ------------------------------------------------------------
# Calculation timing validation
# ------------------------------------------------------------

assert (
    CALC_BATCH_TIME_S_ESTIMATE
    < PWM_PERIOD_S
)


# ============================================================
# Human-readable report
# ============================================================

def build_fixed_derived_summary() -> str:
    """
    Build a human-readable report containing the important
    derived fixed-point constants.

    Exactly the same report is:

        1. printed to the terminal
        2. saved into sim_result/fixed_derived_config.txt
    """

    output = StringIO()

    def write(line=""):
        output.write(str(line))
        output.write("\n")

    write(
        "========================================"
    )

    write(
        " Fixed-point derived configuration"
    )

    write(
        "========================================"
    )


    # --------------------------------------------------------
    # Angle
    # --------------------------------------------------------

    write()

    write("ANGLE")

    write(
        "----------------------------------------"
    )

    write(
        f"ANGLE_BITS          : "
        f"{ANGLE_BITS}"
    )

    write(
        f"ANGLE_MODULUS       : "
        f"{ANGLE_MODULUS}"
    )

    write(
        f"ANGLE_MASK          : "
        f"0x{ANGLE_MASK:04X}"
    )

    write(
        f"ANGLE_90            : "
        f"{ANGLE_90}"
    )

    write(
        f"ANGLE_180           : "
        f"{ANGLE_180}"
    )

    write(
        f"ANGLE_270           : "
        f"{ANGLE_270}"
    )

    write(
        f"Angle resolution    : "
        f"{ANGLE_DEG_PER_COUNT:.12f} "
        f"deg/count"
    )


    # --------------------------------------------------------
    # Encoder
    # --------------------------------------------------------

    write()

    write("ENCODER")

    write(
        "----------------------------------------"
    )

    write(
        f"LM10 counts         : "
        f"{LM10_COUNTS}"
    )

    write(
        f"LM10 bits           : "
        f"{LM10_BITS}"
    )

    write(
        f"Encoder angle shift : "
        f"{ENCODER_TO_ANGLE_SHIFT}"
    )

    write(
        f"Pole pairs          : "
        f"{POLE_PAIRS}"
    )


    # --------------------------------------------------------
    # Phase advance
    # --------------------------------------------------------

    write()

    write("PHASE ADVANCE")

    write(
        "----------------------------------------"
    )

    write(
        f"Requested angle     : "
        f"{PHASE_ADVANCE_DEG:.12f} deg"
    )

    write(
        f"Ideal counts        : "
        f"{PHASE_ADVANCE_IDEAL_COUNTS:.12f}"
    )

    write(
        f"Quantized counts    : "
        f"{PHASE_ADVANCE_COUNTS}"
    )

    write(
        f"Quantized hex       : "
        f"0x{PHASE_ADVANCE_COUNTS:04X}"
    )

    write(
        f"Actual angle        : "
        f"{PHASE_ADVANCE_ACTUAL_DEG:.12f} deg"
    )

    write(
        f"Error               : "
        f"{PHASE_ADVANCE_ERROR_DEG:+.12f} deg"
    )


    # --------------------------------------------------------
    # Phase offsets
    # --------------------------------------------------------

    write()

    write("PHASE OFFSETS")

    write(
        "----------------------------------------"
    )

    for (
        phase_index,
        offset
    ) in enumerate(PHASE_OFFSETS):

        actual_angle_deg = (
            offset
            * 360.0
            / ANGLE_MODULUS
        )

        ideal_angle_deg = (
            phase_index
            * 360.0
            / NUM_PHASES
        )

        error_deg = (
            actual_angle_deg
            - ideal_angle_deg
        )

        write(
            f"Phase "
            f"{phase_index + 1:2d}: "
            f"{offset:5d}  "
            f"0x{offset:04X}  "
            f"{actual_angle_deg:12.8f} deg  "
            f"error={error_deg:+.8f} deg"
        )


    # --------------------------------------------------------
    # Waveform LUT
    # --------------------------------------------------------

    write()

    write("WAVEFORM LUT")

    write(
        "----------------------------------------"
    )

    write(
        f"Address bits        : "
        f"{WAVEFORM_LUT_ADDRESS_BITS}"
    )

    write(
        f"Data bits           : "
        f"{WAVEFORM_LUT_DATA_BITS}"
    )

    write(
        f"Depth               : "
        f"{WAVEFORM_LUT_DEPTH}"
    )

    write(
        f"Scale               : "
        f"{WAVEFORM_LUT_SCALE}"
    )

    write(
        f"Storage max         : "
        f"{WAVEFORM_LUT_STORAGE_MAX}"
    )

    write(
        f"Angle counts/address: "
        f"{LUT_ANGLE_COUNTS_PER_ADDRESS}"
    )

    write(
        f"Address shift       : "
        f"{LUT_ADDRESS_SHIFT}"
    )


    # --------------------------------------------------------
    # Amplitude
    # --------------------------------------------------------

    write()

    write("AMPLITUDE")

    write(
        "----------------------------------------"
    )

    write(
        f"Storage bits        : "
        f"{AMPLITUDE_BITS}"
    )

    write(
        f"Fraction bits       : "
        f"{AMPLITUDE_FRAC_BITS}"
    )

    write(
        f"Scale               : "
        f"{AMPLITUDE_SCALE}"
    )

    write(
        f"Maximum command     : "
        f"{AMPLITUDE_MAX_COMMAND}"
    )

    write(
        f"Storage max         : "
        f"{AMPLITUDE_STORAGE_MAX}"
    )


    # --------------------------------------------------------
    # Clocks
    # --------------------------------------------------------

    write()

    write("CLOCKS")

    write(
        "----------------------------------------"
    )

    write(
        f"Calculation clock   : "
        f"{CALC_CLOCK_HZ} Hz"
    )

    write(
        f"PWM / gate clock    : "
        f"{PWM_CLOCK_HZ} Hz"
    )

    write(
        f"PWM / CALC ratio    : "
        f"{PWM_TO_CALC_CLOCK_RATIO}:1"
    )

    write(
        f"PWM clock period    : "
        f"{PWM_CLOCK_PERIOD_NS:.6f} ns"
    )


    # --------------------------------------------------------
    # PWM
    # --------------------------------------------------------

    write()

    write("PWM")

    write(
        "----------------------------------------"
    )

    write(
        f"Requested frequency : "
        f"{PWM_FREQUENCY_HZ:.6f} Hz"
    )

    write(
        f"Ideal TOP           : "
        f"{PWM_TOP_IDEAL:.12f}"
    )

    write(
        f"PWM TOP             : "
        f"{PWM_TOP}"
    )

    write(
        f"PWM CENTER          : "
        f"{PWM_CENTER}"
    )

    write(
        f"Period clocks       : "
        f"{PWM_PERIOD_CLOCKS}"
    )

    write(
        f"Actual frequency    : "
        f"{PWM_ACTUAL_FREQUENCY_HZ:.9f} Hz"
    )

    write(
        f"Frequency error     : "
        f"{PWM_FREQUENCY_ERROR_HZ:+.9f} Hz"
    )

    write(
        f"Frequency error     : "
        f"{PWM_FREQUENCY_ERROR_PERCENT:+.9f} %"
    )

    write(
        f"PWM period          : "
        f"{PWM_PERIOD_US:.9f} us"
    )


    # --------------------------------------------------------
    # Fixed-point scaling
    # --------------------------------------------------------

    write()

    write("FIXED-POINT SCALING")

    write(
        "----------------------------------------"
    )

    write(
        f"Scale denominator   : "
        f"2^{PWM_SCALE_DENOMINATOR_BITS}"
    )

    write(
        f"Scale denominator   : "
        f"{PWM_SCALE_DENOMINATOR}"
    )

    write(
        f"Rounding mode       : "
        f"{ROUNDING_MODE}"
    )

    write(
        f"Rounding bias       : "
        f"{PWM_ROUNDING_BIAS}"
    )

    write(
        f"W*A product bits    : "
        f"{WAVEFORM_AMPLITUDE_PRODUCT_BITS}"
    )

    write(
        f"Maximum legal W*A   : "
        f"{MAX_WAVEFORM_AMPLITUDE_PRODUCT}"
    )

    write(
        f"Scaled value bits   : "
        f"{PWM_SCALED_VALUE_BITS}"
    )

    write(
        f"Maximum scaled value: "
        f"{MAX_PWM_SCALED_VALUE}"
    )


    # --------------------------------------------------------
    # Deadtime
    # --------------------------------------------------------

    write()

    write("DEADTIME")

    write(
        "----------------------------------------"
    )

    write(
        f"LH requested        : "
        f"{DEADTIME_LH_NS:.6f} ns"
    )

    write(
        f"LH clocks           : "
        f"{DEADTIME_LH_CLOCKS}"
    )

    write(
        f"LH actual           : "
        f"{DEADTIME_LH_ACTUAL_NS:.6f} ns"
    )

    write(
        f"LH error            : "
        f"{DEADTIME_LH_ERROR_NS:+.6f} ns"
    )

    write(
        f"HL requested        : "
        f"{DEADTIME_HL_NS:.6f} ns"
    )

    write(
        f"HL clocks           : "
        f"{DEADTIME_HL_CLOCKS}"
    )

    write(
        f"HL actual           : "
        f"{DEADTIME_HL_ACTUAL_NS:.6f} ns"
    )

    write(
        f"HL error            : "
        f"{DEADTIME_HL_ERROR_NS:+.6f} ns"
    )


    # --------------------------------------------------------
    # Calculation timing
    # --------------------------------------------------------

    write()

    write("CALCULATION TIMING")

    write(
        "----------------------------------------"
    )

    write(
        f"Clocks / phase      : "
        f"{CALC_CLOCKS_PER_PHASE_ESTIMATE}"
    )

    write(
        f"Clocks / batch      : "
        f"{CALC_CLOCKS_PER_BATCH_ESTIMATE}"
    )

    write(
        f"Batch time          : "
        f"{CALC_BATCH_TIME_US_ESTIMATE:.6f} us"
    )

    write(
        f"Frame utilization   : "
        f"{CALC_FRAME_UTILIZATION_PERCENT:.6f} %"
    )


    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    write()

    write("VALIDATION")

    write(
        "----------------------------------------"
    )

    write(
        "Architecture validation: PASS"
    )

    write()

    write(
        "========================================"
    )

    return output.getvalue()


# ============================================================
# Report output
# ============================================================

def save_fixed_derived_summary():
    """
    Save the derived fixed-point configuration report.
    """

    SIM_RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    report = (
        build_fixed_derived_summary()
    )

    DERIVED_CONFIG_REPORT_FILE.write_text(
        report,
        encoding="utf-8",
    )


def print_fixed_derived_summary():
    """
    Print exactly the same report that is saved to disk.
    """

    print(
        build_fixed_derived_summary(),
        end="",
    )


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":

    save_fixed_derived_summary()

    print_fixed_derived_summary()

    print()

    print(
        "Saved derived configuration to:"
    )

    print(
        DERIVED_CONFIG_REPORT_FILE
    )