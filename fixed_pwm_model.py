# ============================================================
# Fixed-point center-aligned PWM Golden Model
# ============================================================
#
# Exact clock-by-clock model of the new FPGA PWM carrier
# and comparator.
#
# Frozen architecture:
#
#   PWM clock = 200 MHz
#   TOP       = 6666
#   CENTER    = 3333
#
# Carrier sequence for one frame:
#
#   0, 1, 2, ... TOP-1,
#   TOP, TOP-1, ... 2, 1
#
# Frame length:
#
#   2 * TOP clocks
#
# Comparator:
#
#   compare == 0:
#       pwm = 0
#
#   compare == TOP:
#       pwm = 1
#
#   otherwise:
#
#       pwm =
#           (carrier < compare)
#           OR
#           (
#               carrier == compare
#               AND direction_down
#           )
#
# This guarantees:
#
#   ON clocks = 2 * compare
#
# and therefore:
#
#   duty = compare / TOP
#
# exactly.
#
# This file does NOT yet model:
#
#   - shadow / active compare registers
#   - complementary High / Low gate outputs
#   - deadtime
#
# ============================================================

from dataclasses import dataclass

from fixed_derived_config import (
    PWM_CLOCK_HZ,
    PWM_TOP,
    PWM_CENTER,
)


# ============================================================
# Derived PWM constants
# ============================================================

PWM_PERIOD_CLOCKS = 2 * PWM_TOP

PWM_CLOCK_PERIOD_S = (
    1.0 / PWM_CLOCK_HZ
)

PWM_PERIOD_S = (
    PWM_PERIOD_CLOCKS
    / PWM_CLOCK_HZ
)

PWM_ACTUAL_FREQUENCY_HZ = (
    PWM_CLOCK_HZ
    / PWM_PERIOD_CLOCKS
)


# ============================================================
# Carrier state
# ============================================================

@dataclass(frozen=True)
class PWMCarrierState:
    clock_index: int
    carrier: int
    direction_down: bool


# ============================================================
# Optional detailed PWM sample
# ============================================================

@dataclass(frozen=True)
class PWMSample:
    clock_index: int
    carrier: int
    direction_down: bool
    compare: int
    pwm: int


# ============================================================
# Compare validation
# ============================================================

def validate_compare(
    compare: int,
) -> None:

    if not isinstance(compare, int):
        raise TypeError(
            "PWM compare must be an integer."
        )

    if not (
        0
        <= compare
        <= PWM_TOP
    ):
        raise ValueError(
            f"PWM compare must be in range "
            f"0..{PWM_TOP}, "
            f"got {compare}"
        )


# ============================================================
# Carrier generation
# ============================================================

def generate_one_pwm_carrier_frame(
) -> tuple[PWMCarrierState, ...]:
    """
    Generate one complete center-aligned carrier frame.

    Example for TOP = 4:

        clock    carrier    direction
          0         0          UP
          1         1          UP
          2         2          UP
          3         3          UP
          4         4          DOWN
          5         3          DOWN
          6         2          DOWN
          7         1          DOWN

    Next clock:

        carrier = 0

    which begins the next frame.

    Therefore:

        frame clocks = 2 * TOP
    """

    states: list[PWMCarrierState] = []

    clock_index = 0

    # --------------------------------------------------------
    # Rising half
    #
    # 0 .. TOP-1
    # --------------------------------------------------------

    for carrier in range(
        PWM_TOP
    ):

        states.append(
            PWMCarrierState(
                clock_index=clock_index,
                carrier=carrier,
                direction_down=False,
            )
        )

        clock_index += 1

    # --------------------------------------------------------
    # Falling half
    #
    # TOP .. 1
    # --------------------------------------------------------

    for carrier in range(
        PWM_TOP,
        0,
        -1,
    ):

        states.append(
            PWMCarrierState(
                clock_index=clock_index,
                carrier=carrier,
                direction_down=True,
            )
        )

        clock_index += 1

    if (
        len(states)
        != PWM_PERIOD_CLOCKS
    ):
        raise AssertionError(
            "Incorrect PWM carrier frame length: "
            f"{len(states)}, "
            f"expected {PWM_PERIOD_CLOCKS}"
        )

    return tuple(states)


# ============================================================
# Bit-exact PWM comparator
# ============================================================

def pwm_compare_output(
    carrier: int,
    direction_down: bool,
    compare: int,
) -> int:
    """
    Exact discrete comparator definition.

    compare = 0:
        always OFF

    compare = TOP:
        always ON

    Interior compare:

        ON if carrier < compare

        OR

        ON if carrier == compare
        while carrier is moving DOWN.
    """

    validate_compare(
        compare
    )

    if not isinstance(carrier, int):
        raise TypeError(
            "Carrier must be an integer."
        )

    if not (
        0
        <= carrier
        <= PWM_TOP
    ):
        raise ValueError(
            f"Carrier must be in range "
            f"0..{PWM_TOP}, "
            f"got {carrier}"
        )

    if compare == 0:
        return 0

    if compare == PWM_TOP:
        return 1

    if carrier < compare:
        return 1

    if (
        carrier == compare
        and direction_down
    ):
        return 1

    return 0


# ============================================================
# Detailed frame generation
# ============================================================

def generate_one_pwm_frame(
    compare: int,
    carrier_frame: tuple[
        PWMCarrierState,
        ...
    ] | None = None,
) -> tuple[PWMSample, ...]:
    """
    Generate detailed clock-by-clock PWM samples.

    This function is useful for:

        - debugging
        - plotting
        - future RTL comparison

    It is intentionally NOT used by the exhaustive validation
    loop because constructing millions of Python objects would
    be unnecessarily slow.
    """

    validate_compare(
        compare
    )

    if carrier_frame is None:
        carrier_frame = (
            generate_one_pwm_carrier_frame()
        )

    if (
        len(carrier_frame)
        != PWM_PERIOD_CLOCKS
    ):
        raise ValueError(
            "Carrier frame has incorrect length."
        )

    samples: list[PWMSample] = []

    for state in carrier_frame:

        pwm = pwm_compare_output(
            carrier=state.carrier,
            direction_down=(
                state.direction_down
            ),
            compare=compare,
        )

        samples.append(
            PWMSample(
                clock_index=(
                    state.clock_index
                ),
                carrier=state.carrier,
                direction_down=(
                    state.direction_down
                ),
                compare=compare,
                pwm=pwm,
            )
        )

    return tuple(samples)


# ============================================================
# Fast direct ON-clock counter
# ============================================================

def count_pwm_on_clocks_fast(
    compare: int,
    carrier_frame: tuple[
        PWMCarrierState,
        ...
    ],
) -> int:
    """
    Count ON clocks without creating PWMSample objects.

    IMPORTANT:

    This still evaluates the actual comparator for every
    carrier state.

    Therefore the exhaustive test remains a real exhaustive
    comparator test.

    We are only removing unnecessary object allocation.
    """

    validate_compare(
        compare
    )

    on_clocks = 0

    for state in carrier_frame:

        on_clocks += pwm_compare_output(
            carrier=state.carrier,
            direction_down=(
                state.direction_down
            ),
            compare=compare,
        )

    return on_clocks


# ============================================================
# Detailed ON-clock counter
# ============================================================

def count_pwm_on_clocks_detailed(
    compare: int,
    carrier_frame: tuple[
        PWMCarrierState,
        ...
    ],
) -> int:
    """
    Reference counter using detailed PWMSample generation.

    Used only for a few selected compare values to verify
    that the detailed frame generator and fast validator agree.
    """

    frame = generate_one_pwm_frame(
        compare=compare,
        carrier_frame=carrier_frame,
    )

    return sum(
        sample.pwm
        for sample
        in frame
    )


# ============================================================
# Duty calculation
# ============================================================

def calculate_pwm_duty_fast(
    compare: int,
    carrier_frame: tuple[
        PWMCarrierState,
        ...
    ],
) -> float:

    on_clocks = (
        count_pwm_on_clocks_fast(
            compare=compare,
            carrier_frame=carrier_frame,
        )
    )

    return (
        on_clocks
        / PWM_PERIOD_CLOCKS
    )


# ============================================================
# Carrier validation
# ============================================================

def validate_carrier(
    carrier_frame: tuple[
        PWMCarrierState,
        ...
    ],
) -> None:

    assert (
        len(carrier_frame)
        == PWM_PERIOD_CLOCKS
    )

    # --------------------------------------------------------
    # First state
    # --------------------------------------------------------

    first = carrier_frame[0]

    assert (
        first.clock_index
        == 0
    )

    assert (
        first.carrier
        == 0
    )

    assert (
        first.direction_down
        is False
    )

    # --------------------------------------------------------
    # Last rising state
    # --------------------------------------------------------

    last_rising = (
        carrier_frame[
            PWM_TOP - 1
        ]
    )

    assert (
        last_rising.carrier
        == PWM_TOP - 1
    )

    assert (
        last_rising.direction_down
        is False
    )

    # --------------------------------------------------------
    # TOP state
    # --------------------------------------------------------

    top_state = (
        carrier_frame[
            PWM_TOP
        ]
    )

    assert (
        top_state.carrier
        == PWM_TOP
    )

    assert (
        top_state.direction_down
        is True
    )

    # --------------------------------------------------------
    # Final state
    # --------------------------------------------------------

    final_state = (
        carrier_frame[-1]
    )

    assert (
        final_state.clock_index
        == PWM_PERIOD_CLOCKS - 1
    )

    assert (
        final_state.carrier
        == 1
    )

    assert (
        final_state.direction_down
        is True
    )

    # --------------------------------------------------------
    # Rising sequence
    # --------------------------------------------------------

    for index in range(
        PWM_TOP
    ):

        state = (
            carrier_frame[index]
        )

        assert (
            state.clock_index
            == index
        )

        assert (
            state.carrier
            == index
        )

        assert (
            state.direction_down
            is False
        )

    # --------------------------------------------------------
    # Falling sequence
    # --------------------------------------------------------

    for offset in range(
        PWM_TOP
    ):

        index = (
            PWM_TOP
            + offset
        )

        state = (
            carrier_frame[index]
        )

        expected_carrier = (
            PWM_TOP
            - offset
        )

        assert (
            state.clock_index
            == index
        )

        assert (
            state.carrier
            == expected_carrier
        )

        assert (
            state.direction_down
            is True
        )


# ============================================================
# Boundary transition validation
# ============================================================

def validate_frame_boundary(
    carrier_frame: tuple[
        PWMCarrierState,
        ...
    ],
) -> None:
    """
    Verify the conceptual transition from the last state of
    one frame to the first state of the next frame.

    End of frame:

        carrier = 1
        direction = DOWN

    Start of next frame:

        carrier = 0
        direction = UP
    """

    last = carrier_frame[-1]

    first = carrier_frame[0]

    assert (
        last.carrier
        == 1
    )

    assert (
        last.direction_down
        is True
    )

    assert (
        first.carrier
        == 0
    )

    assert (
        first.direction_down
        is False
    )


# ============================================================
# Detailed vs fast implementation validation
# ============================================================

def validate_detailed_vs_fast(
    carrier_frame: tuple[
        PWMCarrierState,
        ...
    ],
) -> None:
    """
    Verify that the optimized counter gives exactly the same
    result as the detailed PWMSample implementation.
    """

    test_compares = (
        0,
        1,
        2,
        PWM_CENTER - 1,
        PWM_CENTER,
        PWM_CENTER + 1,
        PWM_TOP - 2,
        PWM_TOP - 1,
        PWM_TOP,
    )

    for compare in test_compares:

        detailed = (
            count_pwm_on_clocks_detailed(
                compare=compare,
                carrier_frame=carrier_frame,
            )
        )

        fast = (
            count_pwm_on_clocks_fast(
                compare=compare,
                carrier_frame=carrier_frame,
            )
        )

        assert (
            detailed
            == fast
        )


# ============================================================
# Key compare validation
# ============================================================

def validate_key_compare_values(
    carrier_frame: tuple[
        PWMCarrierState,
        ...
    ],
) -> None:

    # --------------------------------------------------------
    # 0%
    # --------------------------------------------------------

    on_clocks = (
        count_pwm_on_clocks_fast(
            compare=0,
            carrier_frame=carrier_frame,
        )
    )

    assert (
        on_clocks
        == 0
    )

    # --------------------------------------------------------
    # Smallest non-zero duty
    # --------------------------------------------------------

    on_clocks = (
        count_pwm_on_clocks_fast(
            compare=1,
            carrier_frame=carrier_frame,
        )
    )

    assert (
        on_clocks
        == 2
    )

    # --------------------------------------------------------
    # CENTER = exact 50%
    # --------------------------------------------------------

    on_clocks = (
        count_pwm_on_clocks_fast(
            compare=PWM_CENTER,
            carrier_frame=carrier_frame,
        )
    )

    assert (
        on_clocks
        == 2 * PWM_CENTER
    )

    assert (
        on_clocks
        == PWM_TOP
    )

    duty = (
        on_clocks
        / PWM_PERIOD_CLOCKS
    )

    assert (
        duty
        == 0.5
    )

    # --------------------------------------------------------
    # Maximum interior compare
    # --------------------------------------------------------

    on_clocks = (
        count_pwm_on_clocks_fast(
            compare=PWM_TOP - 1,
            carrier_frame=carrier_frame,
        )
    )

    assert (
        on_clocks
        == 2 * (PWM_TOP - 1)
    )

    # --------------------------------------------------------
    # 100%
    # --------------------------------------------------------

    on_clocks = (
        count_pwm_on_clocks_fast(
            compare=PWM_TOP,
            carrier_frame=carrier_frame,
        )
    )

    assert (
        on_clocks
        == PWM_PERIOD_CLOCKS
    )


# ============================================================
# Optimized exhaustive validation
# ============================================================

def validate_all_compare_values(
    carrier_frame: tuple[
        PWMCarrierState,
        ...
    ],
) -> None:
    """
    Exhaustively validate every legal compare value.

    Unlike the previous version, this function does NOT create
    13,332 PWMSample objects for every compare value.

    It directly evaluates the frozen comparator against the
    already generated carrier frame.

    Required invariant:

        ON clocks = 2 * compare
    """

    for compare in range(
        PWM_TOP + 1
    ):

        on_clocks = (
            count_pwm_on_clocks_fast(
                compare=compare,
                carrier_frame=carrier_frame,
            )
        )

        expected_on_clocks = (
            2 * compare
        )

        if (
            on_clocks
            != expected_on_clocks
        ):

            raise AssertionError(
                "PWM ON-clock mismatch:\n"
                f"  compare  = {compare}\n"
                f"  measured = {on_clocks}\n"
                f"  expected = "
                f"{expected_on_clocks}"
            )


# ============================================================
# Fast mathematical consistency validation
# ============================================================

def validate_duty_mapping(
) -> None:
    """
    Validate the exact compare-to-duty relationship.

    Once the exhaustive comparator test has established:

        ON clocks = 2 * compare

    then:

        duty =
            (2 * compare)
            /
            (2 * PWM_TOP)

        duty =
            compare / PWM_TOP

    This loop verifies the arithmetic relationship for every
    legal compare code without another expensive carrier scan.
    """

    for compare in range(
        PWM_TOP + 1
    ):

        on_clocks = (
            2 * compare
        )

        duty_from_clocks = (
            on_clocks
            / PWM_PERIOD_CLOCKS
        )

        duty_from_compare = (
            compare
            / PWM_TOP
        )

        if (
            duty_from_clocks
            != duty_from_compare
        ):

            raise AssertionError(
                "Duty mapping mismatch at "
                f"compare={compare}"
            )


# ============================================================
# Complementary compare validation
# ============================================================

def validate_complementary_compares(
) -> None:
    """
    The waveform stage guarantees opposite phases satisfy:

        compare_a + compare_b = PWM_TOP

    Since the PWM comparator has already been exhaustively
    proven to produce:

        ON = 2 * compare

    complementary compare pairs must satisfy:

        ON_A + ON_B
            =
        2 * PWM_TOP
            =
        PWM_PERIOD_CLOCKS

    This can be checked directly without re-running another
    88 million comparator evaluations.
    """

    for compare_a in range(
        PWM_TOP + 1
    ):

        compare_b = (
            PWM_TOP
            - compare_a
        )

        assert (
            compare_a
            + compare_b
            == PWM_TOP
        )

        on_a = (
            2 * compare_a
        )

        on_b = (
            2 * compare_b
        )

        assert (
            on_a
            + on_b
            == PWM_PERIOD_CLOCKS
        )


# ============================================================
# Print summary
# ============================================================

def print_pwm_summary(
    carrier_frame: tuple[
        PWMCarrierState,
        ...
    ],
) -> None:

    print(
        "========================================"
    )

    print(
        " Fixed center-aligned PWM model"
    )

    print(
        "========================================"
    )

    print()

    print(
        f"PWM clock              : "
        f"{PWM_CLOCK_HZ} Hz"
    )

    print(
        f"PWM clock period       : "
        f"{PWM_CLOCK_PERIOD_S * 1e9:.6f} ns"
    )

    print(
        f"PWM TOP                : "
        f"{PWM_TOP}"
    )

    print(
        f"PWM CENTER             : "
        f"{PWM_CENTER}"
    )

    print(
        f"PWM period clocks      : "
        f"{PWM_PERIOD_CLOCKS}"
    )

    print(
        f"PWM period             : "
        f"{PWM_PERIOD_S * 1e6:.9f} us"
    )

    print(
        f"Actual PWM frequency   : "
        f"{PWM_ACTUAL_FREQUENCY_HZ:.9f} Hz"
    )

    print()

    print(
        "Key compare values"
    )

    print(
        "----------------------------------------"
    )

    test_compares = (
        0,
        1,
        PWM_CENTER - 1,
        PWM_CENTER,
        PWM_CENTER + 1,
        PWM_TOP - 1,
        PWM_TOP,
    )

    for compare in test_compares:

        on_clocks = (
            count_pwm_on_clocks_fast(
                compare=compare,
                carrier_frame=carrier_frame,
            )
        )

        duty = (
            on_clocks
            / PWM_PERIOD_CLOCKS
        )

        print(
            f"compare={compare:4d}  "
            f"ON={on_clocks:5d}/"
            f"{PWM_PERIOD_CLOCKS}  "
            f"duty={duty * 100.0:12.8f}%"
        )

    print()


# ============================================================
# Main
# ============================================================

def main() -> None:

    carrier_frame = (
        generate_one_pwm_carrier_frame()
    )

    print_pwm_summary(
        carrier_frame
    )

    # --------------------------------------------------------
    # Carrier sequence
    # --------------------------------------------------------

    print(
        "Validating carrier sequence..."
    )

    validate_carrier(
        carrier_frame
    )

    validate_frame_boundary(
        carrier_frame
    )

    print(
        "Carrier sequence PASS"
    )

    print()

    # --------------------------------------------------------
    # Detailed implementation cross-check
    # --------------------------------------------------------

    print(
        "Validating detailed vs fast model..."
    )

    validate_detailed_vs_fast(
        carrier_frame
    )

    print(
        "Detailed vs fast model PASS"
    )

    print()

    # --------------------------------------------------------
    # Key compare values
    # --------------------------------------------------------

    print(
        "Validating key compare values..."
    )

    validate_key_compare_values(
        carrier_frame
    )

    print(
        "Key compare values PASS"
    )

    print()

    # --------------------------------------------------------
    # Exhaustive comparator scan
    # --------------------------------------------------------

    print(
        "Scanning all compare values "
        f"0..{PWM_TOP}..."
    )

    validate_all_compare_values(
        carrier_frame
    )

    print(
        "All compare values PASS"
    )

    print()

    # --------------------------------------------------------
    # Exact duty mapping
    # --------------------------------------------------------

    print(
        "Validating exact duty mapping..."
    )

    validate_duty_mapping()

    print(
        "Exact duty mapping PASS"
    )

    print()

    # --------------------------------------------------------
    # Complementary compare pairs
    # --------------------------------------------------------

    print(
        "Validating complementary "
        "compare pairs..."
    )

    validate_complementary_compares()

    print(
        "Complementary compare pairs PASS"
    )

    print()

    print(
        "========================================"
    )

    print(
        " Fixed PWM architecture validation PASS"
    )

    print(
        "========================================"
    )


if __name__ == "__main__":
    main()