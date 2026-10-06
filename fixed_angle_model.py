# ============================================================

# Fixed-point angle Golden Model

# ============================================================

#

# This module models the FPGA angle datapath using integer

# arithmetic only.

#

# The purpose is to provide a bit-exact reference for the

# future SystemVerilog implementation.

#

# Control calculations in this file use:

#

#     integer arithmetic

#     explicit bit masks

#     explicit modulo wrap

#     explicit shifts

#

# Floating-point arithmetic is used ONLY for:

#

#     debug output

#     human-readable degree conversion

#

# It does NOT participate in the fixed-point control path.

#

# ============================================================



from dataclasses import dataclass



from config import (

    LM10_COUNTS,

    POLE_PAIRS,

    NUM_PHASES,

    ENCODER_OFFSET,

    ELECTRICAL_DIRECTION,

    TORQUE_DIRECTION,

)



from fixed_derived_config import (

    ANGLE_BITS,

    ANGLE_MODULUS,

    ANGLE_MASK,

    ANGLE_90,

    ANGLE_DEG_PER_COUNT,

    LM10_BITS,

    ENCODER_TO_ANGLE_SHIFT,

    PHASE_ADVANCE_COUNTS,

    PHASE_OFFSETS,

)





# ============================================================

# Encoder constants

# ============================================================



ENCODER_MODULUS = LM10_COUNTS



ENCODER_MASK = (

    ENCODER_MODULUS - 1

)





# ============================================================

# Trace structure

# ============================================================



@dataclass(frozen=True)

class FixedAngleTrace:

    """

    Complete fixed-point angle calculation trace for one

    encoder sample.



    All angle fields are stored in the FPGA U16 angle format.



    One complete revolution:



        0 ... 65535

        corresponds to

        0 ... 360 degrees



    The phase_angles_u16 tuple contains all 22 final phase

    angles after phase offsets have been applied.

    """



    encoder_count: int



    relative_encoder_count: int



    mechanical_angle_u16: int



    electrical_angle_u16: int



    voltage_angle_u16: int



    control_angle_u16: int



    phase_angles_u16: tuple[int, ...]





# ============================================================

# Validation helpers

# ============================================================



def validate_encoder_count(

    encoder_count: int,

) -> None:

    """

    Validate a raw LM10 encoder count.



    The physical LM10 encoder produces:



        0 ... 4095



    Invalid software test values are rejected rather than

    silently wrapped.

    """



    if not isinstance(

        encoder_count,

        int,

    ):

        raise TypeError(

            "encoder_count must be an integer."

        )



    if not (

        0

        <= encoder_count

        < ENCODER_MODULUS

    ):

        raise ValueError(

            f"encoder_count must be in range "

            f"0..{ENCODER_MODULUS - 1}, "

            f"got {encoder_count}."

        )





def validate_u16_angle(

    angle_u16: int,

) -> None:

    """

    Validate an internal fixed-point angle.

    """



    if not isinstance(

        angle_u16,

        int,

    ):

        raise TypeError(

            "angle_u16 must be an integer."

        )



    if not (

        0

        <= angle_u16

        <= ANGLE_MASK

    ):

        raise ValueError(

            f"angle_u16 must be in range "

            f"0..{ANGLE_MASK}, "

            f"got {angle_u16}."

        )





# ============================================================

# Basic conversion helpers

# ============================================================



def u16_to_degrees(

    angle_u16: int,

) -> float:

    """

    Convert an internal U16 angle to degrees.



    IMPORTANT:

    This function is for diagnostics and plotting only.



    It is NOT part of the FPGA control calculation.

    """



    validate_u16_angle(

        angle_u16

    )



    return (

        angle_u16

        * ANGLE_DEG_PER_COUNT

    )





# ============================================================

# Encoder offset

# ============================================================



def encoder_to_relative_count(

    encoder_count: int,

) -> int:

    """

    Apply the mechanical encoder zero offset.



    FPGA-equivalent operation:



        relative =

            (encoder_count - ENCODER_OFFSET)

            & 0xFFF



    Because the encoder domain is 12-bit unsigned, subtraction

    naturally wraps modulo 4096.



    Example:



        encoder_count = 1024

        ENCODER_OFFSET = 1022



        relative = 2

    """



    validate_encoder_count(

        encoder_count

    )



    relative_count = (

        encoder_count

        - ENCODER_OFFSET

    ) & ENCODER_MASK



    return relative_count





# ============================================================

# Mechanical angle

# ============================================================



def relative_count_to_mechanical_u16(

    relative_count: int,

) -> int:

    """

    Convert the 12-bit relative encoder count into the internal

    U16 angle representation.



    Current architecture:



        4096 encoder counts

        65536 internal angle counts



    Therefore:



        theta_m16 = relative_count << 4



    This conversion is exact.

    """



    if not isinstance(

        relative_count,

        int,

    ):

        raise TypeError(

            "relative_count must be an integer."

        )



    if not (

        0

        <= relative_count

        < ENCODER_MODULUS

    ):

        raise ValueError(

            f"relative_count must be in range "

            f"0..{ENCODER_MODULUS - 1}, "

            f"got {relative_count}."

        )



    mechanical_angle_u16 = (

        relative_count

        << ENCODER_TO_ANGLE_SHIFT

    ) & ANGLE_MASK



    return mechanical_angle_u16





# ============================================================

# Electrical angle

# ============================================================



def mechanical_to_electrical_u16(

    mechanical_angle_u16: int,

) -> int:

    """

    Convert mechanical angle into electrical angle.



    Mathematical definition:



        theta_e =

            ELECTRICAL_DIRECTION

            * POLE_PAIRS

            * theta_m



    Current configuration:



        ELECTRICAL_DIRECTION = -1

        POLE_PAIRS = 3



    Therefore:



        theta_e = -3 * theta_m



    The final ANGLE_MASK implements modulo-65536 wrap.



    No floating-point arithmetic is used.

    """



    validate_u16_angle(

        mechanical_angle_u16

    )



    electrical_angle_u16 = (

        ELECTRICAL_DIRECTION

        * POLE_PAIRS

        * mechanical_angle_u16

    ) & ANGLE_MASK



    return electrical_angle_u16





# ============================================================

# Voltage vector angle

# ============================================================



def electrical_to_voltage_u16(

    electrical_angle_u16: int,

) -> int:

    """

    Apply the +/-90 degree torque-producing voltage-vector

    offset.



    Mathematical definition:



        theta_v =

            theta_e

            + TORQUE_DIRECTION * 90 degrees



    In U16 angle format:



        90 degrees = 16384



    Current configuration:



        TORQUE_DIRECTION = -1



    therefore:



        theta_v = theta_e - 16384



    The mask implements modulo-65536 wrap.

    """



    validate_u16_angle(

        electrical_angle_u16

    )



    voltage_angle_u16 = (

        electrical_angle_u16

        + TORQUE_DIRECTION

        * ANGLE_90

    ) & ANGLE_MASK



    return voltage_angle_u16





# ============================================================

# Phase advance

# ============================================================



def apply_phase_advance_u16(
    voltage_angle_u16: int,
    phase_advance_u16: int = PHASE_ADVANCE_COUNTS,
) -> int:

    """

    Apply the quantized phase advance.



    Float specification:



        PHASE_ADVANCE_DEG = 10 degrees



    Fixed-point representation:



        PHASE_ADVANCE_COUNTS = 1820



    Actual represented angle:



        9.99755859375 degrees



    Mathematical definition:



        theta_control =

            theta_v

            + TORQUE_DIRECTION

            * PHASE_ADVANCE_COUNTS



    Current TORQUE_DIRECTION = -1, therefore:



        theta_control =

            theta_v - 1820



    The mask implements modulo-65536 wrap.

    """



    validate_u16_angle(

        voltage_angle_u16

    )



    validate_u16_angle(
        phase_advance_u16
    )

    control_angle_u16 = (
        voltage_angle_u16
        + TORQUE_DIRECTION
        * phase_advance_u16
    ) & ANGLE_MASK



    return control_angle_u16





# ============================================================

# Phase angle generation

# ============================================================



def generate_phase_angles_u16(

    control_angle_u16: int,

) -> tuple[int, ...]:

    """

    Generate all fixed-point phase angles.



    For phase k:



        theta_phase[k] =

            theta_control

            - PHASE_OFFSET[k]



    modulo 65536.



    Phase offsets are independently quantized in

    fixed_derived_config.py.



    Opposite phases are guaranteed to differ by exactly

    180 degrees in U16 representation.

    """



    validate_u16_angle(

        control_angle_u16

    )



    phase_angles = tuple(

        (

            control_angle_u16

            - phase_offset

        )

        & ANGLE_MASK



        for phase_offset

        in PHASE_OFFSETS

    )



    assert (

        len(phase_angles)

        == NUM_PHASES

    )



    return phase_angles





# ============================================================

# Complete angle pipeline

# ============================================================



def calculate_fixed_angles(
    encoder_count: int,
    phase_advance_u16: int = PHASE_ADVANCE_COUNTS,
) -> FixedAngleTrace:

    """

    Execute the complete fixed-point angle datapath for one

    encoder sample.



    Pipeline:



        encoder_count

            |

            v

        subtract encoder offset

            |

            v

        relative_encoder_count

            |

            v

        << 4

            |

            v

        mechanical_angle_u16

            |

            v

        direction * pole pairs

            |

            v

        electrical_angle_u16

            |

            v

        +/- 90 degrees

            |

            v

        voltage_angle_u16

            |

            v

        quantized phase advance

            |

            v

        control_angle_u16

            |

            v

        subtract 22 phase offsets

            |

            v

        phase_angles_u16[0..21]

    """



    relative_encoder_count = (

        encoder_to_relative_count(

            encoder_count

        )

    )



    mechanical_angle_u16 = (

        relative_count_to_mechanical_u16(

            relative_encoder_count

        )

    )



    electrical_angle_u16 = (

        mechanical_to_electrical_u16(

            mechanical_angle_u16

        )

    )



    voltage_angle_u16 = (

        electrical_to_voltage_u16(

            electrical_angle_u16

        )

    )



    control_angle_u16 = (

        apply_phase_advance_u16(
            voltage_angle_u16,
            phase_advance_u16,
        )

    )



    phase_angles_u16 = (

        generate_phase_angles_u16(

            control_angle_u16

        )

    )



    return FixedAngleTrace(

        encoder_count=encoder_count,

        relative_encoder_count=(

            relative_encoder_count

        ),

        mechanical_angle_u16=(

            mechanical_angle_u16

        ),

        electrical_angle_u16=(

            electrical_angle_u16

        ),

        voltage_angle_u16=(

            voltage_angle_u16

        ),

        control_angle_u16=(

            control_angle_u16

        ),

        phase_angles_u16=(

            phase_angles_u16

        ),

    )





# ============================================================

# Architecture validation

# ============================================================



def validate_fixed_angle_architecture() -> None:

    """

    Run structural tests that must remain true for the current

    fixed-point architecture.

    """



    assert ANGLE_BITS == 16



    assert ANGLE_MODULUS == 65536



    assert ANGLE_MASK == 0xFFFF



    assert ENCODER_MODULUS == 4096



    assert ENCODER_MASK == 0x0FFF



    assert LM10_BITS == 12



    assert (

        ENCODER_TO_ANGLE_SHIFT

        == 4

    )



    assert POLE_PAIRS == 3



    assert NUM_PHASES == 22



    assert (

        len(PHASE_OFFSETS)

        == NUM_PHASES

    )



    assert (

        PHASE_ADVANCE_COUNTS

        == 1820

    )



    # --------------------------------------------------------

    # Encoder offset zero

    # --------------------------------------------------------



    zero_trace = (

        calculate_fixed_angles(

            ENCODER_OFFSET

        )

    )



    assert (

        zero_trace

        .relative_encoder_count

        == 0

    )



    assert (

        zero_trace

        .mechanical_angle_u16

        == 0

    )



    assert (

        zero_trace

        .electrical_angle_u16

        == 0

    )



    # --------------------------------------------------------

    # Known test point: encoder = 1024

    # --------------------------------------------------------



    test_trace = (

        calculate_fixed_angles(

            1024

        )

    )



    assert (

        test_trace

        .relative_encoder_count

        == 2

    )



    assert (

        test_trace

        .mechanical_angle_u16

        == 32

    )



    # -3 * 32 = -96 mod 65536

    assert (

        test_trace

        .electrical_angle_u16

        == (

            -96

            & ANGLE_MASK

        )

    )



    # --------------------------------------------------------

    # Opposite-phase invariant

    # --------------------------------------------------------



    for phase_index in range(

        NUM_PHASES // 2

    ):



        opposite_index = (

            phase_index

            + NUM_PHASES // 2

        )



        expected_opposite = (

            test_trace

            .phase_angles_u16[

                phase_index

            ]

            + ANGLE_MODULUS // 2

        ) & ANGLE_MASK



        assert (

            test_trace

            .phase_angles_u16[

                opposite_index

            ]

            == expected_opposite

        )



    # --------------------------------------------------------

    # Full encoder-domain validation

    # --------------------------------------------------------



    for encoder_count in range(

        ENCODER_MODULUS

    ):



        trace = (

            calculate_fixed_angles(

                encoder_count

            )

        )



        assert (

            0

            <= trace.mechanical_angle_u16

            <= ANGLE_MASK

        )



        assert (

            0

            <= trace.electrical_angle_u16

            <= ANGLE_MASK

        )



        assert (

            0

            <= trace.voltage_angle_u16

            <= ANGLE_MASK

        )



        assert (

            0

            <= trace.control_angle_u16

            <= ANGLE_MASK

        )



        assert (

            len(

                trace.phase_angles_u16

            )

            == NUM_PHASES

        )



        for phase_angle in (

            trace.phase_angles_u16

        ):



            assert (

                0

                <= phase_angle

                <= ANGLE_MASK

            )





# ============================================================

# Human-readable test output

# ============================================================



def print_trace(

    encoder_count: int,

) -> None:

    """

    Print one complete fixed-point angle trace.

    """



    trace = (

        calculate_fixed_angles(

            encoder_count

        )

    )



    print(

        "========================================"

    )



    print(

        " Fixed-point angle model"

    )



    print(

        "========================================"

    )



    print()



    print(

        f"Encoder count        : "

        f"{trace.encoder_count}"

    )



    print(

        f"Relative count       : "

        f"{trace.relative_encoder_count}"

    )



    print()



    print(

        "MECHANICAL ANGLE"

    )



    print(

        "----------------------------------------"

    )



    print(

        f"U16                  : "

        f"{trace.mechanical_angle_u16}"

    )



    print(

        f"Hex                  : "

        f"0x{trace.mechanical_angle_u16:04X}"

    )



    print(

        f"Degrees              : "

        f"{u16_to_degrees(trace.mechanical_angle_u16):.12f}"

    )



    print()



    print(

        "ELECTRICAL ANGLE"

    )



    print(

        "----------------------------------------"

    )



    print(

        f"U16                  : "

        f"{trace.electrical_angle_u16}"

    )



    print(

        f"Hex                  : "

        f"0x{trace.electrical_angle_u16:04X}"

    )



    print(

        f"Degrees              : "

        f"{u16_to_degrees(trace.electrical_angle_u16):.12f}"

    )



    print()



    print(

        "VOLTAGE ANGLE"

    )



    print(

        "----------------------------------------"

    )



    print(

        f"U16                  : "

        f"{trace.voltage_angle_u16}"

    )



    print(

        f"Hex                  : "

        f"0x{trace.voltage_angle_u16:04X}"

    )



    print(

        f"Degrees              : "

        f"{u16_to_degrees(trace.voltage_angle_u16):.12f}"

    )



    print()



    print(

        "CONTROL ANGLE"

    )



    print(

        "----------------------------------------"

    )



    print(

        f"U16                  : "

        f"{trace.control_angle_u16}"

    )



    print(

        f"Hex                  : "

        f"0x{trace.control_angle_u16:04X}"

    )



    print(

        f"Degrees              : "

        f"{u16_to_degrees(trace.control_angle_u16):.12f}"

    )



    print()



    print(

        "PHASE ANGLES"

    )



    print(

        "----------------------------------------"

    )



    for (

        phase_index,

        phase_angle

    ) in enumerate(

        trace.phase_angles_u16

    ):



        print(

            f"Phase "

            f"{phase_index + 1:2d}: "

            f"{phase_angle:5d}  "

            f"0x{phase_angle:04X}  "

            f"{u16_to_degrees(phase_angle):12.8f} deg"

        )



    print()



    print(

        "Architecture validation: PASS"

    )



    print(

        "========================================"

    )





# ============================================================

# Main

# ============================================================



if __name__ == "__main__":



    validate_fixed_angle_architecture()



    print_trace(

        encoder_count=1024

    )