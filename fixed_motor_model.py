# ============================================================

# Complete fixed-point motor command Golden Model

# ============================================================

#

# Complete bit-exact numerical chain:

#

#   LM10 encoder count

#       ↓

#   fixed_angle_model

#       ↓

#   control angle

#       ↓

#   22 x phase angles

#       ↓

#   fixed_waveform_model

#       ↓

#   waveform LUT

#       ↓

#   amplitude scaling

#       ↓

#   22 x PWM compare values

#

# This file intentionally does NOT duplicate:

#

#   - angle mathematics

#   - phase offset mathematics

#   - LUT decoding

#   - amplitude multiplication

#   - PWM scaling / rounding

#

# Those operations remain in their already validated modules.

#

# PWM carrier timing is NOT modeled here.

# Shadow/active timing is NOT modeled here.

# Deadtime is NOT modeled here.

#

# ============================================================



from dataclasses import dataclass



from config import (

    LM10_COUNTS,

    NUM_PHASES,

)



from fixed_derived_config import (

    AMPLITUDE_SCALE,

    PWM_CENTER,

    PWM_TOP,

    PHASE_ADVANCE_COUNTS,

)



from fixed_angle_model import (

    FixedAngleTrace,

    calculate_fixed_angles,

)



from fixed_waveform_model import (

    FixedWaveformResult,

    load_waveform_lut,

    calculate_all_phase_compares,

)





# ============================================================

# Complete motor result

# ============================================================



@dataclass(frozen=True)

class FixedMotorResult:

    encoder_count: int

    amplitude_cmd: int



    angle_trace: FixedAngleTrace



    phase_results: tuple[

        FixedWaveformResult,

        ...

    ]



    phase_compares: tuple[int, ...]





# ============================================================

# Complete fixed-point motor calculation

# ============================================================



def calculate_fixed_motor(
    encoder_count: int,
    amplitude_cmd: int,
    waveform_lut,
    phase_advance_u16: int = PHASE_ADVANCE_COUNTS,
) -> FixedMotorResult:

    """

    Calculate the complete fixed-point numerical motor command

    for one encoder sample.



    The result contains:



        - complete angle trace

        - 22 phase angles

        - 22 waveform datapath results

        - 22 final PWM compare values



    No PWM carrier timing is included here.

    """



    # --------------------------------------------------------

    # Angle chain

    # --------------------------------------------------------



    angle_trace = calculate_fixed_angles(

        encoder_count,

        phase_advance_u16,

    )



    if len(

        angle_trace.phase_angles_u16

    ) != NUM_PHASES:



        raise AssertionError(

            "Angle model did not produce "

            f"{NUM_PHASES} phase angles."

        )



    # --------------------------------------------------------

    # Waveform / amplitude / compare chain

    # --------------------------------------------------------



    phase_results = (

        calculate_all_phase_compares(

            phase_angles_u16=(

                angle_trace.phase_angles_u16

            ),

            amplitude_cmd=amplitude_cmd,

            waveform_lut=waveform_lut,

        )

    )



    if len(

        phase_results

    ) != NUM_PHASES:



        raise AssertionError(

            "Waveform model did not produce "

            f"{NUM_PHASES} phase results."

        )



    phase_compares = tuple(

        result.compare

        for result

        in phase_results

    )



    return FixedMotorResult(

        encoder_count=encoder_count,

        amplitude_cmd=amplitude_cmd,

        angle_trace=angle_trace,

        phase_results=phase_results,

        phase_compares=phase_compares,

    )





# ============================================================

# Result printing

# ============================================================



def print_motor_result(

    result: FixedMotorResult,

) -> None:



    angle = result.angle_trace



    print(

        "========================================"

    )



    print(

        " Complete fixed-point motor result"

    )



    print(

        "========================================"

    )



    print()



    print(

        f"Encoder count        : "

        f"{result.encoder_count}"

    )



    print(

        f"Amplitude command    : "

        f"{result.amplitude_cmd} / "

        f"{AMPLITUDE_SCALE}"

    )



    print()



    print(

        "ANGLE CHAIN"

    )



    print(

        "----------------------------------------"

    )



    print(

        f"Relative encoder     : "

        f"{angle.relative_encoder_count}"

    )



    print(

        f"Mechanical U16       : "

        f"{angle.mechanical_angle_u16} "

        f"(0x{angle.mechanical_angle_u16:04X})"

    )



    print(

        f"Electrical U16       : "

        f"{angle.electrical_angle_u16} "

        f"(0x{angle.electrical_angle_u16:04X})"

    )



    print(

        f"Voltage U16          : "

        f"{angle.voltage_angle_u16} "

        f"(0x{angle.voltage_angle_u16:04X})"

    )



    print(

        f"Control U16          : "

        f"{angle.control_angle_u16} "

        f"(0x{angle.control_angle_u16:04X})"

    )



    print()



    print(

        "22-PHASE OUTPUT"

    )



    print(

        "----------------------------------------"

    )



    print(

        "Phase  Angle   Sign  Addr     W  "

        "Delta  Compare"

    )



    print(

        "-----  ------  ----  ----  ----  "

        "-----  -------"

    )



    for phase_index, phase_result in enumerate(

        result.phase_results

    ):



        print(

            f"{phase_index + 1:5d}  "

            f"{phase_result.phase_angle_u16:04X}    "

            f"{phase_result.sign:1d}    "

            f"{phase_result.lut_address:4d}  "

            f"{phase_result.waveform_cmd:4d}  "

            f"{phase_result.delta:5d}  "

            f"{phase_result.compare:7d}"

        )



    print()





# ============================================================

# Known-point validation

# ============================================================



def validate_known_point(

    waveform_lut,

) -> None:

    """

    Validate the already established encoder reference point:



        encoder_count = 1024



    The angle stage was previously validated as:



        relative encoder = 2

        mechanical U16   = 32

        electrical U16   = 65440

        voltage U16      = 49056

        control U16      = 47236

    """



    result = calculate_fixed_motor(

        encoder_count=1024,

        amplitude_cmd=AMPLITUDE_SCALE // 2,

        waveform_lut=waveform_lut,

    )



    angle = result.angle_trace



    assert (

        angle.relative_encoder_count

        == 2

    )



    assert (

        angle.mechanical_angle_u16

        == 32

    )



    assert (

        angle.electrical_angle_u16

        == 65440

    )



    assert (

        angle.voltage_angle_u16

        == 49056

    )



    assert (

        angle.control_angle_u16

        == 47236

    )



    assert (

        len(

            angle.phase_angles_u16

        )

        == NUM_PHASES

    )



    assert (

        len(

            result.phase_compares

        )

        == NUM_PHASES

    )





# ============================================================

# Opposite-phase validation

# ============================================================



def validate_opposite_phases(

    result: FixedMotorResult,

) -> None:

    """

    With 22 equally spaced phases:



        phase 1  <-> phase 12

        phase 2  <-> phase 13

        ...

        phase 11 <-> phase 22



    Their angles differ by exactly 180 degrees.



    With the half-wave LUT architecture this means:



        same LUT magnitude

        opposite sign

        same delta



    and therefore:



        compare[k]

        +

        compare[k + 11]

        =

        PWM_TOP

    """



    half_phase_count = (

        NUM_PHASES // 2

    )



    for phase_index in range(

        half_phase_count

    ):



        opposite_index = (

            phase_index

            + half_phase_count

        )



        first = (

            result.phase_results[

                phase_index

            ]

        )



        opposite = (

            result.phase_results[

                opposite_index

            ]

        )



        expected_opposite_angle = (

            first.phase_angle_u16

            + 0x8000

        ) & 0xFFFF



        assert (

            opposite.phase_angle_u16

            == expected_opposite_angle

        )



        assert (

            first.lut_address

            == opposite.lut_address

        )



        assert (

            first.waveform_cmd

            == opposite.waveform_cmd

        )



        assert (

            first.sign

            != opposite.sign

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

# Zero-amplitude validation

# ============================================================



def validate_zero_amplitude(

    waveform_lut,

) -> None:

    """

    At amplitude = 0 every phase must be exactly at PWM_CENTER,

    independent of encoder position.

    """



    for encoder_count in range(

        LM10_COUNTS

    ):



        result = calculate_fixed_motor(

            encoder_count=encoder_count,

            amplitude_cmd=0,

            waveform_lut=waveform_lut,

        )



        for compare in (

            result.phase_compares

        ):



            assert (

                compare

                == PWM_CENTER

            )





# ============================================================

# Full encoder rotation validation

# ============================================================



def validate_full_encoder_rotation(

    waveform_lut,

) -> tuple[int, int]:

    """

    Scan all 4096 encoder positions.



    Validate:



        - exactly 22 phase outputs

        - all compare values are legal

        - all opposite phase pairs remain complementary

        - complete model remains valid through wrap-around



    Returns:



        global minimum compare

        global maximum compare

    """



    global_min_compare = PWM_TOP

    global_max_compare = 0



    for encoder_count in range(

        LM10_COUNTS

    ):



        result = calculate_fixed_motor(

            encoder_count=encoder_count,

            amplitude_cmd=AMPLITUDE_SCALE // 2,

            waveform_lut=waveform_lut,

        )



        assert (

            len(

                result.phase_compares

            )

            == NUM_PHASES

        )



        validate_opposite_phases(

            result

        )



        for compare in (

            result.phase_compares

        ):



            assert (

                0

                <= compare

                <= PWM_TOP

            )



            global_min_compare = min(

                global_min_compare,

                compare,

            )



            global_max_compare = max(

                global_max_compare,

                compare,

            )



    return (

        global_min_compare,

        global_max_compare,

    )





# ============================================================

# Main

# ============================================================



def main() -> None:



    waveform_lut = (

        load_waveform_lut()

    )



    print(

        "Waveform LUT loaded successfully"

    )



    print()



    # --------------------------------------------------------

    # Known reference point

    # --------------------------------------------------------



    print(

        "Validating known encoder point..."

    )



    validate_known_point(

        waveform_lut

    )



    print(

        "Known encoder point PASS"

    )



    print()



    # --------------------------------------------------------

    # Display phi = 1024

    # --------------------------------------------------------



    reference_result = (

        calculate_fixed_motor(

            encoder_count=1024,

            amplitude_cmd=AMPLITUDE_SCALE // 2,

            waveform_lut=waveform_lut,

        )

    )



    print_motor_result(

        reference_result

    )



    validate_opposite_phases(

        reference_result

    )



    print(

        "Reference-point opposite phases PASS"

    )



    print()



    # --------------------------------------------------------

    # Zero amplitude

    # --------------------------------------------------------



    print(

        "Scanning zero-amplitude behavior..."

    )



    validate_zero_amplitude(

        waveform_lut

    )



    print(

        "Zero-amplitude full rotation PASS"

    )



    print()



    # --------------------------------------------------------

    # Full encoder scan

    # --------------------------------------------------------



    print(

        "Scanning all encoder positions..."

    )



    (

        minimum_compare,

        maximum_compare,

    ) = validate_full_encoder_rotation(

        waveform_lut

    )



    print(

        "Full encoder rotation PASS"

    )



    print()



    print(

        f"Global compare minimum : "

        f"{minimum_compare}"

    )



    print(

        f"Global compare maximum : "

        f"{maximum_compare}"

    )



    print()



    print(

        "========================================"

    )



    print(

        " Complete fixed numerical chain PASS"

    )



    print(

        "========================================"

    )





if __name__ == "__main__":

    main()