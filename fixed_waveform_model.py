# ============================================================
# Fixed-point waveform / amplitude / PWM compare model
# ============================================================
#
# Bit-exact datapath:
#
#   phase_angle_u16
#       -> sign + LUT address
#       -> waveform LUT magnitude
#       -> amplitude multiplication
#       -> PWM scaling
#       -> ROUND_HALF_UP
#       -> PWM compare value
#
# This model intentionally uses integer arithmetic for the
# actual fixed-point datapath.
#
# The waveform LUT is loaded from:
#
#   waveform_lut_4096x13.csv
#
# Expected CSV columns:
#
#   address,angle_deg,value_u13
#
# angle_deg is informational only. The fixed-point datapath
# uses address and value_u13 only.
#
# No PWM carrier timing is modeled here.
# No shadow/active register timing is modeled here.
#
# ============================================================

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
import csv

from fixed_derived_config import (
    ANGLE_MASK,
    WAVEFORM_LUT_DEPTH,
    WAVEFORM_LUT_SCALE,
    WAVEFORM_LUT_STORAGE_MAX,
    LUT_ADDRESS_SHIFT,
    AMPLITUDE_SCALE,
    AMPLITUDE_MAX_COMMAND,
    PWM_CENTER,
    PWM_TOP,
    PWM_SCALE_DENOMINATOR_BITS,
    PWM_ROUNDING_BIAS,
)


# ============================================================
# LUT file configuration
# ============================================================

DEFAULT_LUT_PATH = Path(
    "waveform_lut_4096x13.csv"
)

EXPECTED_CSV_COLUMNS = (
    "address",
    "angle_deg",
    "value_u13",
)


# ============================================================
# Result structure
# ============================================================

@dataclass(frozen=True)
class FixedWaveformResult:
    phase_angle_u16: int

    sign: int
    lut_address: int
    waveform_cmd: int
    amplitude_cmd: int

    product: int
    scaled_product: int
    rounded_scaled_product: int

    delta: int
    compare: int


# ============================================================
# Validation helpers
# ============================================================

def validate_u16_angle(
    angle_u16: int,
) -> None:

    if not isinstance(angle_u16, int):
        raise TypeError(
            "Angle must be an integer."
        )

    if not 0 <= angle_u16 <= ANGLE_MASK:
        raise ValueError(
            f"Angle must be in range "
            f"0..{ANGLE_MASK}, "
            f"got {angle_u16}"
        )


def validate_waveform_value(
    value: int,
) -> None:

    if not isinstance(value, int):
        raise TypeError(
            "Waveform LUT value must be an integer."
        )

    if not 0 <= value <= WAVEFORM_LUT_SCALE:
        raise ValueError(
            f"Waveform LUT value must be in "
            f"legal range "
            f"0..{WAVEFORM_LUT_SCALE}, "
            f"got {value}"
        )


def validate_amplitude_cmd(
    amplitude_cmd: int,
) -> None:

    if not isinstance(amplitude_cmd, int):
        raise TypeError(
            "Amplitude command must be an integer."
        )

    if not (
        0
        <= amplitude_cmd
        <= AMPLITUDE_MAX_COMMAND
    ):
        raise ValueError(
            f"Amplitude command must be in "
            f"legal range "
            f"0..{AMPLITUDE_MAX_COMMAND}, "
            f"got {amplitude_cmd}"
        )


# ============================================================
# LUT loading
# ============================================================

def load_waveform_lut(
    path: Path | str = DEFAULT_LUT_PATH,
) -> tuple[int, ...]:
    """
    Load the converted 4096 x 13-bit waveform LUT from CSV.

    Expected format:

        address,angle_deg,value_u13
        0,0.000000000000,0
        1,0.043945312500,...
        ...
        4095,179.956054687500,...

    Requirements:

        - exactly 4096 data rows
        - address must be exactly 0..4095
        - value_u13 must be integer
        - legal waveform range is 0..4096

    angle_deg is checked for valid numeric syntax but is not
    used by the bit-exact datapath.
    """

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            "Waveform LUT CSV file not found: "
            f"{path.resolve()}"
        )

    values: list[int] = []

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        reader = csv.DictReader(file)

        if reader.fieldnames is None:
            raise ValueError(
                "Waveform LUT CSV has no header."
            )

        actual_columns = tuple(
            name.strip()
            for name in reader.fieldnames
        )

        if actual_columns != EXPECTED_CSV_COLUMNS:
            raise ValueError(
                "Unexpected waveform LUT CSV columns.\n"
                f"Expected: {EXPECTED_CSV_COLUMNS}\n"
                f"Actual  : {actual_columns}"
            )

        for row_number, row in enumerate(
            reader,
            start=2,
        ):

            # --------------------------------------------
            # Address
            # --------------------------------------------

            try:
                address = int(
                    row["address"].strip()
                )

            except (
                ValueError,
                TypeError,
                AttributeError,
            ) as exc:

                raise ValueError(
                    f"Invalid address at CSV "
                    f"line {row_number}: "
                    f"{row.get('address')!r}"
                ) from exc

            expected_address = len(values)

            if address != expected_address:
                raise ValueError(
                    f"Unexpected LUT address at "
                    f"CSV line {row_number}: "
                    f"got {address}, "
                    f"expected {expected_address}"
                )

            if not (
                0
                <= address
                < WAVEFORM_LUT_DEPTH
            ):
                raise ValueError(
                    f"LUT address out of range at "
                    f"CSV line {row_number}: "
                    f"{address}"
                )

            # --------------------------------------------
            # Informational angle
            # --------------------------------------------

            try:
                float(
                    row["angle_deg"].strip()
                )

            except (
                ValueError,
                TypeError,
                AttributeError,
            ) as exc:

                raise ValueError(
                    f"Invalid angle_deg at CSV "
                    f"line {row_number}: "
                    f"{row.get('angle_deg')!r}"
                ) from exc

            # --------------------------------------------
            # LUT value
            # --------------------------------------------

            try:
                waveform_value = int(
                    row["value_u13"].strip()
                )

            except (
                ValueError,
                TypeError,
                AttributeError,
            ) as exc:

                raise ValueError(
                    f"Invalid value_u13 at CSV "
                    f"line {row_number}: "
                    f"{row.get('value_u13')!r}"
                ) from exc

            if (
                waveform_value
                > WAVEFORM_LUT_STORAGE_MAX
            ):
                raise ValueError(
                    f"LUT[{address}] = "
                    f"{waveform_value} exceeds "
                    f"13-bit storage maximum "
                    f"{WAVEFORM_LUT_STORAGE_MAX}"
                )

            validate_waveform_value(
                waveform_value
            )

            values.append(
                waveform_value
            )

    if len(values) != WAVEFORM_LUT_DEPTH:
        raise ValueError(
            f"Waveform LUT contains "
            f"{len(values)} entries. "
            f"Expected "
            f"{WAVEFORM_LUT_DEPTH}."
        )

    return tuple(values)


# ============================================================
# Angle -> sign
# ============================================================

def angle_to_waveform_sign(
    angle_u16: int,
) -> int:
    """
    Half-wave sign:

        angle[15] = 0
            positive half-wave

        angle[15] = 1
            negative half-wave
    """

    validate_u16_angle(
        angle_u16
    )

    return (
        angle_u16 >> 15
    ) & 0x1


# ============================================================
# Angle -> LUT address
# ============================================================

def angle_to_lut_address(
    angle_u16: int,
) -> int:
    """
    Convert U16 phase angle into the 12-bit
    half-wave LUT address.

    Current architecture:

        address = angle[14:3]

    because:

        half-wave = 32768 U16 counts

        32768 / 4096
            = 8 angle counts per address

    Therefore the lower 3 angle bits are discarded.

    This truncation is intentional and matches the
    future FPGA implementation.
    """

    validate_u16_angle(
        angle_u16
    )

    address = (
        angle_u16
        >> LUT_ADDRESS_SHIFT
    ) & (
        WAVEFORM_LUT_DEPTH - 1
    )

    return address


# ============================================================
# LUT lookup
# ============================================================

def lookup_waveform(
    angle_u16: int,
    waveform_lut: Sequence[int],
) -> tuple[int, int, int]:
    """
    Return:

        sign
        LUT address
        unsigned waveform magnitude
    """

    if len(
        waveform_lut
    ) != WAVEFORM_LUT_DEPTH:

        raise ValueError(
            f"Waveform LUT must contain "
            f"{WAVEFORM_LUT_DEPTH} entries, "
            f"got {len(waveform_lut)}"
        )

    sign = angle_to_waveform_sign(
        angle_u16
    )

    address = angle_to_lut_address(
        angle_u16
    )

    waveform_cmd = int(
        waveform_lut[address]
    )

    validate_waveform_value(
        waveform_cmd
    )

    return (
        sign,
        address,
        waveform_cmd,
    )


# ============================================================
# Waveform x amplitude
# ============================================================

def multiply_waveform_amplitude(
    waveform_cmd: int,
    amplitude_cmd: int,
) -> int:
    """
    Full-precision unsigned multiplication.

        waveform_cmd:
            legal 0..4096

        amplitude_cmd:
            legal 0..4096

        product =
            waveform_cmd
            * amplitude_cmd

    Generic hardware storage:

        13-bit x 13-bit
            -> 26-bit product register

    Maximum legal mathematical value:

        4096 * 4096
            = 16777216
            = 2^24

    No shift.
    No truncation.
    No rounding.
    """

    validate_waveform_value(
        waveform_cmd
    )

    validate_amplitude_cmd(
        amplitude_cmd
    )

    product = (
        waveform_cmd
        * amplitude_cmd
    )

    return product


# ============================================================
# Product -> PWM delta
# ============================================================

def product_to_pwm_delta(
    product: int,
) -> tuple[int, int, int]:
    """
    Convert the waveform/amplitude product into a PWM
    displacement from PWM_CENTER.

    Mathematical equation:

        delta =
            ROUND_HALF_UP(
                product
                * PWM_CENTER
                / 2^24
            )

    Bit-exact implementation:

        scaled_product =
            product * PWM_CENTER

        rounded_scaled_product =
            scaled_product
            + 2^23

        delta =
            rounded_scaled_product
            >> 24

    The shift count and rounding bias come directly from
    fixed_derived_config.py.
    """

    if not isinstance(product, int):
        raise TypeError(
            "Product must be an integer."
        )

    if product < 0:
        raise ValueError(
            f"Product must be unsigned, "
            f"got {product}"
        )

    max_legal_product = (
        WAVEFORM_LUT_SCALE
        * AMPLITUDE_MAX_COMMAND
    )

    if product > max_legal_product:
        raise ValueError(
            f"Product {product} exceeds "
            f"legal maximum "
            f"{max_legal_product}"
        )

    scaled_product = (
        product
        * PWM_CENTER
    )

    rounded_scaled_product = (
        scaled_product
        + PWM_ROUNDING_BIAS
    )

    delta = (
        rounded_scaled_product
        >> PWM_SCALE_DENOMINATOR_BITS
    )

    if not (
        0
        <= delta
        <= PWM_CENTER
    ):
        raise AssertionError(
            f"PWM delta out of range: "
            f"{delta}"
        )

    return (
        scaled_product,
        rounded_scaled_product,
        delta,
    )


# ============================================================
# Sign + delta -> PWM compare
# ============================================================

def delta_to_pwm_compare(
    sign: int,
    delta: int,
) -> int:
    """
    Positive half-wave:

        compare =
            PWM_CENTER + delta

    Negative half-wave:

        compare =
            PWM_CENTER - delta
    """

    if sign not in (
        0,
        1,
    ):
        raise ValueError(
            f"Sign must be 0 or 1, "
            f"got {sign}"
        )

    if not isinstance(delta, int):
        raise TypeError(
            "Delta must be an integer."
        )

    if not (
        0
        <= delta
        <= PWM_CENTER
    ):
        raise ValueError(
            f"Delta must be in range "
            f"0..{PWM_CENTER}, "
            f"got {delta}"
        )

    if sign == 0:

        compare = (
            PWM_CENTER
            + delta
        )

    else:

        compare = (
            PWM_CENTER
            - delta
        )

    if not (
        0
        <= compare
        <= PWM_TOP
    ):
        raise AssertionError(
            f"PWM compare out of range: "
            f"{compare}"
        )

    return compare


# ============================================================
# Complete single-phase datapath
# ============================================================

def calculate_fixed_waveform(
    phase_angle_u16: int,
    amplitude_cmd: int,
    waveform_lut: Sequence[int],
) -> FixedWaveformResult:
    """
    Complete bit-exact fixed-point datapath for
    one motor phase.
    """

    validate_u16_angle(
        phase_angle_u16
    )

    validate_amplitude_cmd(
        amplitude_cmd
    )

    (
        sign,
        lut_address,
        waveform_cmd,
    ) = lookup_waveform(
        phase_angle_u16,
        waveform_lut,
    )

    product = (
        multiply_waveform_amplitude(
            waveform_cmd,
            amplitude_cmd,
        )
    )

    (
        scaled_product,
        rounded_scaled_product,
        delta,
    ) = product_to_pwm_delta(
        product
    )

    compare = (
        delta_to_pwm_compare(
            sign,
            delta,
        )
    )

    return FixedWaveformResult(
        phase_angle_u16=phase_angle_u16,
        sign=sign,
        lut_address=lut_address,
        waveform_cmd=waveform_cmd,
        amplitude_cmd=amplitude_cmd,
        product=product,
        scaled_product=scaled_product,
        rounded_scaled_product=rounded_scaled_product,
        delta=delta,
        compare=compare,
    )


# ============================================================
# Multi-phase datapath
# ============================================================

def calculate_all_phase_compares(
    phase_angles_u16: Sequence[int],
    amplitude_cmd: int,
    waveform_lut: Sequence[int],
) -> tuple[FixedWaveformResult, ...]:
    """
    Calculate waveform/PWM compare values for all
    supplied phases.

    The same amplitude command and the same LUT contents
    are used for the complete phase set.
    """

    validate_amplitude_cmd(
        amplitude_cmd
    )

    return tuple(
        calculate_fixed_waveform(
            phase_angle_u16=angle,
            amplitude_cmd=amplitude_cmd,
            waveform_lut=waveform_lut,
        )
        for angle
        in phase_angles_u16
    )


# ============================================================
# Architecture validation
# ============================================================

def validate_fixed_waveform_architecture(
    waveform_lut: Sequence[int],
) -> None:
    """
    Validate the important frozen architectural invariants.
    """

    # --------------------------------------------------------
    # LUT depth
    # --------------------------------------------------------

    if len(
        waveform_lut
    ) != WAVEFORM_LUT_DEPTH:

        raise AssertionError(
            "Incorrect waveform LUT depth."
        )

    # --------------------------------------------------------
    # LUT legality
    # --------------------------------------------------------

    for address, value in enumerate(
        waveform_lut
    ):

        if not (
            0
            <= value
            <= WAVEFORM_LUT_SCALE
        ):

            raise AssertionError(
                f"Illegal LUT value at "
                f"address {address}: "
                f"{value}"
            )

    # --------------------------------------------------------
    # Sign decoding
    # --------------------------------------------------------

    assert (
        angle_to_waveform_sign(
            0x0000
        )
        == 0
    )

    assert (
        angle_to_waveform_sign(
            0x7FFF
        )
        == 0
    )

    assert (
        angle_to_waveform_sign(
            0x8000
        )
        == 1
    )

    assert (
        angle_to_waveform_sign(
            0xFFFF
        )
        == 1
    )

    # --------------------------------------------------------
    # LUT address decoding
    # --------------------------------------------------------

    assert (
        angle_to_lut_address(
            0x0000
        )
        == 0
    )

    assert (
        angle_to_lut_address(
            0x0007
        )
        == 0
    )

    assert (
        angle_to_lut_address(
            0x0008
        )
        == 1
    )

    assert (
        angle_to_lut_address(
            0x4000
        )
        == 2048
    )

    assert (
        angle_to_lut_address(
            0x7FFF
        )
        == 4095
    )

    assert (
        angle_to_lut_address(
            0x8000
        )
        == 0
    )

    assert (
        angle_to_lut_address(
            0xC000
        )
        == 2048
    )

    assert (
        angle_to_lut_address(
            0xFFFF
        )
        == 4095
    )

    # --------------------------------------------------------
    # Zero amplitude
    #
    # All phases must become exactly neutral:
    #
    #     delta   = 0
    #     compare = PWM_CENTER
    # --------------------------------------------------------

    test_angles = (
        0x0000,
        0x1234,
        0x4000,
        0x7FFF,
        0x8000,
        0xA123,
        0xC000,
        0xFFFF,
    )

    for angle in test_angles:

        result = (
            calculate_fixed_waveform(
                phase_angle_u16=angle,
                amplitude_cmd=0,
                waveform_lut=waveform_lut,
            )
        )

        assert (
            result.delta
            == 0
        )

        assert (
            result.compare
            == PWM_CENTER
        )

    # --------------------------------------------------------
    # Full-scale arithmetic
    #
    # W = 4096
    # A = 4096
    #
    # product = 2^24
    #
    # Therefore:
    #
    # delta = PWM_CENTER
    # --------------------------------------------------------

    full_product = (
        multiply_waveform_amplitude(
            waveform_cmd=WAVEFORM_LUT_SCALE,
            amplitude_cmd=AMPLITUDE_SCALE,
        )
    )

    assert (
        full_product
        == (1 << 24)
    )

    (
        _,
        _,
        full_delta,
    ) = product_to_pwm_delta(
        full_product
    )

    assert (
        full_delta
        == PWM_CENTER
    )

    # Positive full scale -> TOP

    assert (
        delta_to_pwm_compare(
            sign=0,
            delta=full_delta,
        )
        == PWM_TOP
    )

    # Negative full scale -> zero

    assert (
        delta_to_pwm_compare(
            sign=1,
            delta=full_delta,
        )
        == 0
    )

    # --------------------------------------------------------
    # Half-wave antisymmetry
    #
    # theta and theta + 180 degrees:
    #
    #     same LUT address
    #     same magnitude
    #     opposite sign
    #
    # therefore:
    #
    #     compare(theta)
    #       +
    #     compare(theta + 180 deg)
    #
    #       = 2 * PWM_CENTER
    #       = PWM_TOP
    #
    # Check every U16 angle in the positive half-wave.
    # --------------------------------------------------------

    for angle in range(
        0x8000
    ):

        opposite_angle = (
            angle
            + 0x8000
        ) & ANGLE_MASK

        first = (
            calculate_fixed_waveform(
                phase_angle_u16=angle,
                amplitude_cmd=AMPLITUDE_SCALE,
                waveform_lut=waveform_lut,
            )
        )

        opposite = (
            calculate_fixed_waveform(
                phase_angle_u16=opposite_angle,
                amplitude_cmd=AMPLITUDE_SCALE,
                waveform_lut=waveform_lut,
            )
        )

        assert (
            first.lut_address
            == opposite.lut_address
        )

        assert (
            first.sign
            != opposite.sign
        )

        assert (
            first.waveform_cmd
            == opposite.waveform_cmd
        )

        assert (
            first.delta
            == opposite.delta
        )

        assert (
            first.compare
            + opposite.compare
            == PWM_TOP
        )


# ============================================================
# Diagnostic output
# ============================================================

def print_result(
    result: FixedWaveformResult,
) -> None:

    print(
        f"angle=0x{result.phase_angle_u16:04X}  "
        f"sign={result.sign}  "
        f"addr={result.lut_address:4d}  "
        f"W={result.waveform_cmd:4d}  "
        f"A={result.amplitude_cmd:4d}  "
        f"P={result.product:8d}  "
        f"delta={result.delta:4d}  "
        f"compare={result.compare:4d}"
    )


# ============================================================
# Main
# ============================================================

def main() -> None:

    print(
        "========================================"
    )

    print(
        " Fixed waveform model"
    )

    print(
        "========================================"
    )

    print()

    # --------------------------------------------------------
    # Load LUT
    # --------------------------------------------------------

    waveform_lut = (
        load_waveform_lut()
    )

    print(
        "Waveform LUT loaded successfully"
    )

    print(
        f"File       : "
        f"{DEFAULT_LUT_PATH}"
    )

    print(
        f"Entries    : "
        f"{len(waveform_lut)}"
    )

    print(
        f"Minimum    : "
        f"{min(waveform_lut)}"
    )

    print(
        f"Maximum    : "
        f"{max(waveform_lut)}"
    )

    print()

    print(
        f"LUT[0]     : "
        f"{waveform_lut[0]}"
    )

    print(
        f"LUT[1024]  : "
        f"{waveform_lut[1024]}"
    )

    print(
        f"LUT[2048]  : "
        f"{waveform_lut[2048]}"
    )

    print(
        f"LUT[3072]  : "
        f"{waveform_lut[3072]}"
    )

    print(
        f"LUT[4095]  : "
        f"{waveform_lut[4095]}"
    )

    # --------------------------------------------------------
    # Locate actual peak
    # --------------------------------------------------------

    peak_value = max(
        waveform_lut
    )

    peak_address = (
        waveform_lut.index(
            peak_value
        )
    )

    peak_angle_deg = (
        peak_address
        * 180.0
        / WAVEFORM_LUT_DEPTH
    )

    print()

    print(
        f"Peak value : "
        f"{peak_value}"
    )

    print(
        f"Peak addr  : "
        f"{peak_address}"
    )

    print(
        f"Peak angle : "
        f"{peak_angle_deg:.9f} deg"
    )

    # --------------------------------------------------------
    # Half-amplitude diagnostic
    # --------------------------------------------------------

    amplitude_cmd = (
        AMPLITUDE_SCALE // 2
    )

    print()

    print(
        "----------------------------------------"
    )

    print(
        " Half-amplitude test"
    )

    print(
        "----------------------------------------"
    )

    print(
        f"Amplitude command: "
        f"{amplitude_cmd} / "
        f"{AMPLITUDE_SCALE}"
    )

    print()

    test_angles = (
        0x0000,
        0x2000,
        0x4000,
        0x6000,
        0x7FFF,
        0x8000,
        0xA000,
        0xC000,
        0xE000,
        0xFFFF,
    )

    for angle in test_angles:

        result = (
            calculate_fixed_waveform(
                phase_angle_u16=angle,
                amplitude_cmd=amplitude_cmd,
                waveform_lut=waveform_lut,
            )
        )

        print_result(
            result
        )

    # --------------------------------------------------------
    # Full architecture validation
    # --------------------------------------------------------

    print()

    print(
        "----------------------------------------"
    )

    print(
        " Architecture validation"
    )

    print(
        "----------------------------------------"
    )

    validate_fixed_waveform_architecture(
        waveform_lut
    )

    print(
        "Fixed waveform architecture "
        "validation PASS"
    )

    print()

    print(
        "========================================"
    )


if __name__ == "__main__":
    main()