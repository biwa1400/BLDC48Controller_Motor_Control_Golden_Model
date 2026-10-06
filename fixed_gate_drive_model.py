# ============================================================
# Fixed-point complementary gate-drive Golden Model
# ============================================================
#
# Purpose
# -------
#
# Convert the already validated fixed-point raw PWM waveform
# into complementary High / Low gate commands with exact
# discrete deadtime.
#
#
# Frozen timing
# -------------
#
# PWM clock:
#
#     200 MHz
#
# Clock period:
#
#     5 ns
#
# Deadtime:
#
#     8 clocks
#
# Therefore:
#
#     8 * 5 ns = 40 ns
#
#
# Fundamental safety rule
# -----------------------
#
#     gate_high AND gate_low == 0
#
# must be true at every clock.
#
#
# Transition behavior
# -------------------
#
# Stable raw PWM = 0:
#
#     High = 0
#     Low  = 1
#
# Stable raw PWM = 1:
#
#     High = 1
#     Low  = 0
#
#
# raw PWM 0 -> 1:
#
#     Low turns OFF immediately.
#
#     Both gates remain OFF during deadtime.
#
#     If the request remains HIGH long enough,
#     High turns ON exactly 8 clocks later.
#
#
# raw PWM 1 -> 0:
#
#     High turns OFF immediately.
#
#     Both gates remain OFF during deadtime.
#
#     If the request remains LOW long enough,
#     Low turns ON exactly 8 clocks later.
#
#
# Short-pulse behavior
# --------------------
#
# If the raw PWM request reverses before the 8-clock deadtime
# expires, the pending transistor MUST NOT turn on.
#
# Instead:
#
#     - both gates remain OFF
#     - the old pending transition is cancelled
#     - a new deadtime interval begins for the new request
#
# Therefore sufficiently narrow raw PWM pulses may disappear
# completely from the final gate waveform.
#
# This is expected and safe behavior.
#
#
# Continuous simulation
# ---------------------
#
# Deadtime is stateful across PWM frame boundaries.
#
# Validation therefore uses multiple consecutive PWM frames
# instead of treating each PWM frame as an isolated waveform.
#
#
# This model deliberately does NOT include:
#
#     - LUT A/B bank switching
#     - shadow/active register timing
#     - CDC
#     - drive_enable
#     - reset sequencing
#     - old DTC compensation
#
# ============================================================

from dataclasses import dataclass

from fixed_derived_config import (
    PWM_CLOCK_HZ,
    PWM_TOP,
    PWM_CENTER,
)

from fixed_pwm_model import (
    PWM_PERIOD_CLOCKS,
    PWMCarrierState,
    generate_one_pwm_carrier_frame,
    pwm_compare_output,
)


# ============================================================
# Deadtime configuration
# ============================================================

DEADTIME_CLOCKS = 8

PWM_CLOCK_PERIOD_S = (
    1.0
    / PWM_CLOCK_HZ
)

PWM_CLOCK_PERIOD_NS = (
    PWM_CLOCK_PERIOD_S
    * 1e9
)

DEADTIME_S = (
    DEADTIME_CLOCKS
    * PWM_CLOCK_PERIOD_S
)

DEADTIME_NS = (
    DEADTIME_S
    * 1e9
)


# ============================================================
# Internal gate-drive state
# ============================================================

@dataclass
class GateDriveState:
    """
    Internal sequential state.

    target_pwm
        Most recent raw PWM request.

    deadtime_counter
        Number of clock intervals remaining before the
        requested transistor may turn ON.

    gate_high / gate_low
        Current output gate states.
    """

    gate_high: int = 0
    gate_low: int = 0

    target_pwm: int = 0

    deadtime_counter: int = 0

    initialized: bool = False


# ============================================================
# Output sample
# ============================================================

@dataclass(frozen=True)
class GateDriveSample:
    global_clock_index: int

    frame_index: int
    frame_clock_index: int

    carrier: int
    direction_down: bool

    compare: int

    raw_pwm: int

    gate_high: int
    gate_low: int

    deadtime_active: bool
    deadtime_counter: int


# ============================================================
# Raw transition
# ============================================================

@dataclass(frozen=True)
class RawPWMTransition:
    global_clock_index: int

    old_value: int
    new_value: int


# ============================================================
# Validation helpers
# ============================================================

def validate_binary(
    value: int,
    name: str,
) -> None:

    if value not in (
        0,
        1,
    ):
        raise ValueError(
            f"{name} must be 0 or 1, "
            f"got {value}"
        )


def validate_compare(
    compare: int,
) -> None:

    if not isinstance(
        compare,
        int,
    ):
        raise TypeError(
            "compare must be an integer."
        )

    if not (
        0
        <= compare
        <= PWM_TOP
    ):
        raise ValueError(
            f"compare must be in range "
            f"0..{PWM_TOP}, "
            f"got {compare}"
        )


def validate_gate_safety(
    gate_high: int,
    gate_low: int,
) -> None:

    validate_binary(
        gate_high,
        "gate_high",
    )

    validate_binary(
        gate_low,
        "gate_low",
    )

    if (
        gate_high
        and gate_low
    ):
        raise AssertionError(
            "Shoot-through detected: "
            "High and Low are both ON."
        )


# ============================================================
# Initialize state
# ============================================================

def initialize_gate_state(
    raw_pwm: int,
) -> GateDriveState:
    """
    Initialize into the stable state corresponding to the
    first raw PWM value.

    This represents observation of an already-running PWM
    system.

    Reset/startup behavior will be modeled separately when
    the RTL drive-enable/reset architecture is frozen.
    """

    validate_binary(
        raw_pwm,
        "raw_pwm",
    )

    if raw_pwm == 1:

        state = GateDriveState(
            gate_high=1,
            gate_low=0,
            target_pwm=1,
            deadtime_counter=0,
            initialized=True,
        )

    else:

        state = GateDriveState(
            gate_high=0,
            gate_low=1,
            target_pwm=0,
            deadtime_counter=0,
            initialized=True,
        )

    validate_gate_safety(
        state.gate_high,
        state.gate_low,
    )

    return state


# ============================================================
# One 200 MHz gate-drive clock
# ============================================================

def gate_drive_step(
    state: GateDriveState,
    raw_pwm: int,
) -> tuple[int, int]:
    """
    Advance the gate-drive state by exactly one 200 MHz clock.

    Discrete timing definition
    --------------------------

    If raw PWM changes at sample N:

        old transistor is OFF at N

    and if the request remains unchanged:

        new transistor turns ON at N + DEADTIME_CLOCKS

    Therefore:

        elapsed deadtime
            =
        DEADTIME_CLOCKS * PWM clock period

            =
        8 * 5 ns

            =
        40 ns


    Request reversal during deadtime
    --------------------------------

    If raw_pwm changes again before the pending transistor
    turns ON:

        - both gates remain OFF
        - previous pending request is cancelled
        - target_pwm changes
        - deadtime counter restarts

    This naturally suppresses narrow pulses.
    """

    validate_binary(
        raw_pwm,
        "raw_pwm",
    )

    if not state.initialized:
        raise RuntimeError(
            "Gate-drive state is not initialized."
        )

    # --------------------------------------------------------
    # Detect request change.
    # --------------------------------------------------------

    request_changed = (
        raw_pwm
        != state.target_pwm
    )

    if request_changed:

        state.target_pwm = raw_pwm

        # Immediately force both switches OFF.

        state.gate_high = 0
        state.gate_low = 0

        # Start a fresh deadtime interval.
        #
        # At this current sample we are already at the
        # transition instant.
        #
        # We want the requested transistor to turn ON at:
        #
        #     current_index + DEADTIME_CLOCKS
        #
        # Therefore we store DEADTIME_CLOCKS here and
        # decrement on subsequent unchanged samples.

        state.deadtime_counter = (
            DEADTIME_CLOCKS
        )

        validate_gate_safety(
            state.gate_high,
            state.gate_low,
        )

        return (
            state.gate_high,
            state.gate_low,
        )

    # --------------------------------------------------------
    # No new request change.
    #
    # Continue pending deadtime if active.
    # --------------------------------------------------------

    if (
        state.deadtime_counter
        > 0
    ):

        state.deadtime_counter -= 1

        # ----------------------------------------------------
        # Still waiting.
        # ----------------------------------------------------

        if (
            state.deadtime_counter
            > 0
        ):

            state.gate_high = 0
            state.gate_low = 0

            validate_gate_safety(
                state.gate_high,
                state.gate_low,
            )

            return (
                state.gate_high,
                state.gate_low,
            )

        # ----------------------------------------------------
        # Counter has just reached zero.
        #
        # Exactly DEADTIME_CLOCKS clocks have elapsed since
        # the request transition.
        #
        # Requested transistor may now turn ON.
        # ----------------------------------------------------

    # --------------------------------------------------------
    # Stable state or completed deadtime.
    # --------------------------------------------------------

    if (
        state.target_pwm
        == 1
    ):

        state.gate_high = 1
        state.gate_low = 0

    else:

        state.gate_high = 0
        state.gate_low = 1

    validate_gate_safety(
        state.gate_high,
        state.gate_low,
    )

    return (
        state.gate_high,
        state.gate_low,
    )


# ============================================================
# Generate one raw PWM frame
# ============================================================

def generate_raw_pwm_frame(
    compare: int,
    carrier_frame: tuple[
        PWMCarrierState,
        ...
    ],
) -> tuple[int, ...]:

    validate_compare(
        compare
    )

    if (
        len(carrier_frame)
        != PWM_PERIOD_CLOCKS
    ):
        raise ValueError(
            "Carrier frame has incorrect length."
        )

    raw_pwm = []

    for state in carrier_frame:

        raw_pwm.append(
            pwm_compare_output(
                carrier=state.carrier,
                direction_down=(
                    state.direction_down
                ),
                compare=compare,
            )
        )

    return tuple(
        raw_pwm
    )


# ============================================================
# Generate continuous multi-frame waveform
# ============================================================

def generate_continuous_gate_waveform(
    compare: int,
    num_frames: int = 3,
    carrier_frame: tuple[
        PWMCarrierState,
        ...
    ] | None = None,
) -> tuple[
    GateDriveSample,
    ...
]:
    """
    Generate multiple continuous PWM frames.

    GateDriveState is NOT reset at frame boundaries.

    This is essential because deadtime can extend across a
    frame boundary.
    """

    validate_compare(
        compare
    )

    if not isinstance(
        num_frames,
        int,
    ):
        raise TypeError(
            "num_frames must be an integer."
        )

    if (
        num_frames
        < 1
    ):
        raise ValueError(
            "num_frames must be >= 1."
        )

    if carrier_frame is None:

        carrier_frame = (
            generate_one_pwm_carrier_frame()
        )

    raw_frame = (
        generate_raw_pwm_frame(
            compare=compare,
            carrier_frame=carrier_frame,
        )
    )

    if not raw_frame:
        raise AssertionError(
            "Raw PWM frame is empty."
        )

    # --------------------------------------------------------
    # Start in stable state corresponding to the first raw
    # PWM sample.
    # --------------------------------------------------------

    gate_state = (
        initialize_gate_state(
            raw_frame[0]
        )
    )

    samples: list[
        GateDriveSample
    ] = []

    global_clock_index = 0

    for frame_index in range(
        num_frames
    ):

        for frame_clock_index in range(
            PWM_PERIOD_CLOCKS
        ):

            carrier_state = (
                carrier_frame[
                    frame_clock_index
                ]
            )

            raw_pwm = (
                raw_frame[
                    frame_clock_index
                ]
            )

            # ------------------------------------------------
            # First sample already represents initialized
            # stable state.
            # ------------------------------------------------

            if (
                global_clock_index
                == 0
            ):

                gate_high = (
                    gate_state.gate_high
                )

                gate_low = (
                    gate_state.gate_low
                )

            else:

                gate_high, gate_low = (
                    gate_drive_step(
                        state=gate_state,
                        raw_pwm=raw_pwm,
                    )
                )

            samples.append(
                GateDriveSample(
                    global_clock_index=(
                        global_clock_index
                    ),
                    frame_index=(
                        frame_index
                    ),
                    frame_clock_index=(
                        frame_clock_index
                    ),
                    carrier=(
                        carrier_state.carrier
                    ),
                    direction_down=(
                        carrier_state.direction_down
                    ),
                    compare=compare,
                    raw_pwm=raw_pwm,
                    gate_high=gate_high,
                    gate_low=gate_low,
                    deadtime_active=(
                        gate_state.deadtime_counter
                        > 0
                    ),
                    deadtime_counter=(
                        gate_state.deadtime_counter
                    ),
                )
            )

            global_clock_index += 1

    return tuple(
        samples
    )


# ============================================================
# Find raw PWM transitions
# ============================================================

def find_raw_pwm_transitions(
    samples: tuple[
        GateDriveSample,
        ...
    ],
) -> tuple[
    RawPWMTransition,
    ...
]:

    transitions = []

    for index in range(
        1,
        len(samples),
    ):

        old_value = (
            samples[
                index - 1
            ].raw_pwm
        )

        new_value = (
            samples[
                index
            ].raw_pwm
        )

        if (
            old_value
            != new_value
        ):

            transitions.append(
                RawPWMTransition(
                    global_clock_index=(
                        samples[
                            index
                        ].global_clock_index
                    ),
                    old_value=old_value,
                    new_value=new_value,
                )
            )

    return tuple(
        transitions
    )


# ============================================================
# Find next raw transition
# ============================================================

def find_next_raw_transition_index(
    samples: tuple[
        GateDriveSample,
        ...
    ],
    start_index: int,
) -> int | None:

    initial_raw = (
        samples[
            start_index
        ].raw_pwm
    )

    for index in range(
        start_index + 1,
        len(samples),
    ):

        if (
            samples[
                index
            ].raw_pwm
            != initial_raw
        ):

            return index

    return None


# ============================================================
# Find requested gate turn-on
# ============================================================

def find_requested_gate_turn_on(
    samples: tuple[
        GateDriveSample,
        ...
    ],
    transition_index: int,
    new_raw_pwm: int,
    search_end_index: int,
) -> int | None:

    validate_binary(
        new_raw_pwm,
        "new_raw_pwm",
    )

    if new_raw_pwm == 1:

        for index in range(
            transition_index,
            search_end_index,
        ):

            if (
                samples[
                    index
                ].gate_high
                == 1
            ):

                return index

    else:

        for index in range(
            transition_index,
            search_end_index,
        ):

            if (
                samples[
                    index
                ].gate_low
                == 1
            ):

                return index

    return None


# ============================================================
# Validate one transition
# ============================================================

def validate_transition_behavior(
    samples: tuple[
        GateDriveSample,
        ...
    ],
    transition_index: int,
) -> str:
    """
    Validate one raw PWM transition.

    Returns:

        "COMPLETED"

    if the requested transistor successfully turns ON after
    exactly DEADTIME_CLOCKS.

    Returns:

        "SUPPRESSED"

    if raw PWM reverses before deadtime completes and the
    requested transistor correctly never turns ON.
    """

    if not (
        1
        <= transition_index
        < len(samples)
    ):
        raise ValueError(
            "Invalid transition index."
        )

    old_raw = (
        samples[
            transition_index - 1
        ].raw_pwm
    )

    new_raw = (
        samples[
            transition_index
        ].raw_pwm
    )

    if (
        old_raw
        == new_raw
    ):
        raise ValueError(
            "Specified index is not a raw PWM transition."
        )

    # --------------------------------------------------------
    # Old transistor must be OFF immediately.
    # --------------------------------------------------------

    transition_sample = (
        samples[
            transition_index
        ]
    )

    if (
        old_raw == 0
        and new_raw == 1
    ):

        if (
            transition_sample.gate_low
            != 0
        ):
            raise AssertionError(
                "Low gate did not turn OFF "
                "immediately at 0 -> 1 transition."
            )

    elif (
        old_raw == 1
        and new_raw == 0
    ):

        if (
            transition_sample.gate_high
            != 0
        ):
            raise AssertionError(
                "High gate did not turn OFF "
                "immediately at 1 -> 0 transition."
            )

    else:

        raise AssertionError(
            "Invalid binary transition."
        )

    # --------------------------------------------------------
    # Find how long this request survives.
    # --------------------------------------------------------

    next_transition_index = (
        find_next_raw_transition_index(
            samples=samples,
            start_index=transition_index,
        )
    )

    if (
        next_transition_index
        is None
    ):

        search_end_index = (
            len(samples)
        )

        request_length = (
            len(samples)
            - transition_index
        )

    else:

        search_end_index = (
            next_transition_index
        )

        request_length = (
            next_transition_index
            - transition_index
        )

    # --------------------------------------------------------
    # Search for requested transistor turn-on before request
    # changes again.
    # --------------------------------------------------------

    turn_on_index = (
        find_requested_gate_turn_on(
            samples=samples,
            transition_index=(
                transition_index
            ),
            new_raw_pwm=new_raw,
            search_end_index=(
                search_end_index
            ),
        )
    )

    # --------------------------------------------------------
    # Request survives long enough.
    #
    # If the request remains active through sample:
    #
    #     transition + DEADTIME_CLOCKS
    #
    # the requested transistor must turn ON there.
    #
    # This requires:
    #
    #     request_length > DEADTIME_CLOCKS
    #
    # because request_length includes the transition sample.
    # --------------------------------------------------------

    if (
        request_length
        > DEADTIME_CLOCKS
    ):

        expected_turn_on_index = (
            transition_index
            + DEADTIME_CLOCKS
        )

        if (
            turn_on_index
            is None
        ):
            raise AssertionError(
                "Requested transistor should have "
                "turned ON after deadtime but did not."
            )

        if (
            turn_on_index
            != expected_turn_on_index
        ):
            raise AssertionError(
                "Incorrect gate turn-on timing:\n"
                f"  transition index = "
                f"{transition_index}\n"
                f"  expected ON index = "
                f"{expected_turn_on_index}\n"
                f"  actual ON index   = "
                f"{turn_on_index}"
            )

        elapsed_clocks = (
            turn_on_index
            - transition_index
        )

        if (
            elapsed_clocks
            != DEADTIME_CLOCKS
        ):
            raise AssertionError(
                "Incorrect completed deadtime."
            )

        return "COMPLETED"

    # --------------------------------------------------------
    # Request too short.
    #
    # Requested transistor must never turn ON before raw PWM
    # reverses again.
    # --------------------------------------------------------

    if (
        turn_on_index
        is not None
    ):
        raise AssertionError(
            "Short PWM request incorrectly produced "
            "a gate pulse during deadtime."
        )

    return "SUPPRESSED"


# ============================================================
# Safety validation
# ============================================================

def validate_no_overlap(
    samples: tuple[
        GateDriveSample,
        ...
    ],
) -> None:

    for sample in samples:

        if (
            sample.gate_high
            and sample.gate_low
        ):

            raise AssertionError(
                "Gate overlap detected at "
                f"global clock "
                f"{sample.global_clock_index}"
            )


# ============================================================
# Deadtime configuration validation
# ============================================================

def validate_deadtime_configuration() -> None:

    assert (
        PWM_CLOCK_HZ
        == 200_000_000
    )

    assert (
        DEADTIME_CLOCKS
        == 8
    )

    assert abs(
        PWM_CLOCK_PERIOD_NS
        - 5.0
    ) < 1e-12

    assert abs(
        DEADTIME_NS
        - 40.0
    ) < 1e-12


# ============================================================
# Synthetic transition validation
# ============================================================

def validate_synthetic_transitions() -> None:

    # --------------------------------------------------------
    # 0 -> 1
    # --------------------------------------------------------

    state = (
        initialize_gate_state(0)
    )

    assert (
        state.gate_high,
        state.gate_low,
    ) == (
        0,
        1,
    )

    # Transition sample N.

    result = gate_drive_step(
        state,
        1,
    )

    assert (
        result
        == (
            0,
            0,
        )
    )

    # N+1 ... N+7 remain OFF.

    for _ in range(
        DEADTIME_CLOCKS - 1
    ):

        result = gate_drive_step(
            state,
            1,
        )

        assert (
            result
            == (
                0,
                0,
            )
        )

    # N+8 turns High ON.

    result = gate_drive_step(
        state,
        1,
    )

    assert (
        result
        == (
            1,
            0,
        )
    )

    # --------------------------------------------------------
    # 1 -> 0
    # --------------------------------------------------------

    result = gate_drive_step(
        state,
        0,
    )

    assert (
        result
        == (
            0,
            0,
        )
    )

    for _ in range(
        DEADTIME_CLOCKS - 1
    ):

        result = gate_drive_step(
            state,
            0,
        )

        assert (
            result
            == (
                0,
                0,
            )
        )

    result = gate_drive_step(
        state,
        0,
    )

    assert (
        result
        == (
            0,
            1,
        )
    )


# ============================================================
# Synthetic short-pulse validation
# ============================================================

def validate_synthetic_short_pulse() -> None:
    """
    Explicitly prove that a request shorter than the deadtime
    cannot turn the requested transistor ON.
    """

    state = (
        initialize_gate_state(0)
    )

    # --------------------------------------------------------
    # Request High, but hold it for only 2 clocks.
    # --------------------------------------------------------

    result_0 = gate_drive_step(
        state,
        1,
    )

    result_1 = gate_drive_step(
        state,
        1,
    )

    assert (
        result_0
        == (
            0,
            0,
        )
    )

    assert (
        result_1
        == (
            0,
            0,
        )
    )

    # --------------------------------------------------------
    # Request reverses before 8 clocks.
    #
    # High must never have turned ON.
    # --------------------------------------------------------

    result_2 = gate_drive_step(
        state,
        0,
    )

    assert (
        result_2
        == (
            0,
            0,
        )
    )

    assert (
        state.gate_high
        == 0
    )

    # --------------------------------------------------------
    # Now keep Low request stable long enough.
    # --------------------------------------------------------

    for _ in range(
        DEADTIME_CLOCKS - 1
    ):

        result = gate_drive_step(
            state,
            0,
        )

        assert (
            result
            == (
                0,
                0,
            )
        )

    result = gate_drive_step(
        state,
        0,
    )

    assert (
        result
        == (
            0,
            1,
        )
    )


# ============================================================
# Constant-output validation
# ============================================================

def validate_constant_outputs(
    carrier_frame: tuple[
        PWMCarrierState,
        ...
    ],
) -> None:

    # --------------------------------------------------------
    # compare = 0
    # --------------------------------------------------------

    samples = (
        generate_continuous_gate_waveform(
            compare=0,
            num_frames=2,
            carrier_frame=carrier_frame,
        )
    )

    assert all(
        sample.raw_pwm == 0
        for sample
        in samples
    )

    assert all(
        sample.gate_high == 0
        for sample
        in samples
    )

    assert all(
        sample.gate_low == 1
        for sample
        in samples
    )

    # --------------------------------------------------------
    # compare = TOP
    # --------------------------------------------------------

    samples = (
        generate_continuous_gate_waveform(
            compare=PWM_TOP,
            num_frames=2,
            carrier_frame=carrier_frame,
        )
    )

    assert all(
        sample.raw_pwm == 1
        for sample
        in samples
    )

    assert all(
        sample.gate_high == 1
        for sample
        in samples
    )

    assert all(
        sample.gate_low == 0
        for sample
        in samples
    )


# ============================================================
# Validate one compare value
# ============================================================

def validate_compare_deadtime(
    compare: int,
    carrier_frame: tuple[
        PWMCarrierState,
        ...
    ],
) -> tuple[int, int]:
    """
    Validate one compare value using 3 continuous frames.

    Returns:

        completed_transition_count,
        suppressed_transition_count
    """

    samples = (
        generate_continuous_gate_waveform(
            compare=compare,
            num_frames=3,
            carrier_frame=carrier_frame,
        )
    )

    validate_no_overlap(
        samples
    )

    transitions = (
        find_raw_pwm_transitions(
            samples
        )
    )

    completed = 0
    suppressed = 0

    # --------------------------------------------------------
    # Validate transitions whose transition point is in the
    # middle frame.
    #
    # This gives us one full frame of history before and one
    # full frame of future after the frame under test.
    # --------------------------------------------------------

    middle_start = (
        PWM_PERIOD_CLOCKS
    )

    middle_end = (
        2
        * PWM_PERIOD_CLOCKS
    )

    for transition in transitions:

        transition_index = (
            transition.global_clock_index
        )

        if not (
            middle_start
            <= transition_index
            < middle_end
        ):
            continue

        result = (
            validate_transition_behavior(
                samples=samples,
                transition_index=(
                    transition_index
                ),
            )
        )

        if (
            result
            == "COMPLETED"
        ):

            completed += 1

        elif (
            result
            == "SUPPRESSED"
        ):

            suppressed += 1

        else:

            raise AssertionError(
                "Unknown transition result."
            )

    return (
        completed,
        suppressed,
    )


# ============================================================
# Representative PWM validation
# ============================================================

def validate_representative_pwm_values(
    carrier_frame: tuple[
        PWMCarrierState,
        ...
    ],
) -> None:

    test_compares = (
        1,
        2,
        4,
        7,
        8,
        9,
        16,
        PWM_CENTER - 1,
        PWM_CENTER,
        PWM_CENTER + 1,
        PWM_TOP - 16,
        PWM_TOP - 9,
        PWM_TOP - 8,
        PWM_TOP - 7,
        PWM_TOP - 4,
        PWM_TOP - 2,
        PWM_TOP - 1,
    )

    for compare in test_compares:

        validate_compare_deadtime(
            compare=compare,
            carrier_frame=carrier_frame,
        )


# ============================================================
# Explicit narrow-pulse validation
# ============================================================

def validate_narrow_pwm_suppression(
    carrier_frame: tuple[
        PWMCarrierState,
        ...
    ],
) -> None:
    """
    compare=1 produces only two raw ON clocks per PWM period.

    A 2-clock request is much shorter than the 8-clock
    deadtime.

    Therefore the High-side pulse must be completely
    suppressed.
    """

    compare = 1

    samples = (
        generate_continuous_gate_waveform(
            compare=compare,
            num_frames=3,
            carrier_frame=carrier_frame,
        )
    )

    # Inspect only the middle frame.

    middle_samples = (
        samples[
            PWM_PERIOD_CLOCKS:
            2 * PWM_PERIOD_CLOCKS
        ]
    )

    # Raw PWM must contain some HIGH requests.

    assert any(
        sample.raw_pwm == 1
        for sample
        in middle_samples
    )

    # But High gate must never actually turn ON because the
    # pulse is shorter than deadtime.

    assert all(
        sample.gate_high == 0
        for sample
        in middle_samples
    )

    validate_no_overlap(
        samples
    )


# ============================================================
# Normal 50% PWM validation
# ============================================================

def validate_center_pwm(
    carrier_frame: tuple[
        PWMCarrierState,
        ...
    ],
) -> None:

    completed, suppressed = (
        validate_compare_deadtime(
            compare=PWM_CENTER,
            carrier_frame=carrier_frame,
        )
    )

    # Two transitions in the middle frame.
    # Both should complete normally.

    assert (
        completed
        == 2
    )

    assert (
        suppressed
        == 0
    )


# ============================================================
# Print reference example
# ============================================================

def print_reference_example(
    carrier_frame: tuple[
        PWMCarrierState,
        ...
    ],
) -> None:

    compare = (
        PWM_CENTER
    )

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
        2
        * PWM_PERIOD_CLOCKS
    )

    print(
        f"Reference compare       : "
        f"{compare}"
    )

    print(
        f"Reference raw duty      : "
        f"{compare / PWM_TOP * 100.0:.8f}%"
    )

    print(
        f"Middle frame            : "
        f"{middle_start} .. "
        f"{middle_end - 1}"
    )

    transition_number = 0

    for transition in transitions:

        index = (
            transition.global_clock_index
        )

        if not (
            middle_start
            <= index
            < middle_end
        ):
            continue

        transition_number += 1

        result = (
            validate_transition_behavior(
                samples=samples,
                transition_index=index,
            )
        )

        if (
            result
            == "COMPLETED"
        ):

            turn_on_index = (
                index
                + DEADTIME_CLOCKS
            )

            elapsed_ns = (
                DEADTIME_CLOCKS
                * PWM_CLOCK_PERIOD_NS
            )

            print(
                f"Transition "
                f"{transition_number}: "
                f"clock {index:5d}, "
                f"{transition.old_value} -> "
                f"{transition.new_value}, "
                f"gate ON at "
                f"{turn_on_index:5d}, "
                f"deadtime = "
                f"{DEADTIME_CLOCKS} clocks "
                f"= {elapsed_ns:.3f} ns"
            )

        else:

            print(
                f"Transition "
                f"{transition_number}: "
                f"clock {index:5d}, "
                f"{transition.old_value} -> "
                f"{transition.new_value}, "
                f"pulse suppressed"
            )


# ============================================================
# Print narrow-pulse example
# ============================================================

def print_narrow_pulse_example(
    carrier_frame: tuple[
        PWMCarrierState,
        ...
    ],
) -> None:

    compare = 1

    completed, suppressed = (
        validate_compare_deadtime(
            compare=compare,
            carrier_frame=carrier_frame,
        )
    )

    print(
        f"Narrow-pulse compare    : "
        f"{compare}"
    )

    print(
        f"Raw duty                : "
        f"{compare / PWM_TOP * 100.0:.8f}%"
    )

    print(
        f"Completed transitions   : "
        f"{completed}"
    )

    print(
        f"Suppressed transitions  : "
        f"{suppressed}"
    )


# ============================================================
# Main
# ============================================================

def main() -> None:

    carrier_frame = (
        generate_one_pwm_carrier_frame()
    )

    print(
        "========================================"
    )

    print(
        " Fixed complementary gate-drive model"
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
        f"{PWM_CLOCK_PERIOD_NS:.6f} ns"
    )

    print(
        f"Deadtime clocks        : "
        f"{DEADTIME_CLOCKS}"
    )

    print(
        f"Deadtime               : "
        f"{DEADTIME_NS:.6f} ns"
    )

    print()

    # --------------------------------------------------------
    # Reference 50% PWM
    # --------------------------------------------------------

    print(
        "Normal PWM reference"
    )

    print(
        "----------------------------------------"
    )

    print_reference_example(
        carrier_frame
    )

    print()

    # --------------------------------------------------------
    # Narrow pulse
    # --------------------------------------------------------

    print(
        "Narrow-pulse reference"
    )

    print(
        "----------------------------------------"
    )

    print_narrow_pulse_example(
        carrier_frame
    )

    print()

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    print(
        "Validating deadtime configuration..."
    )

    validate_deadtime_configuration()

    print(
        "Deadtime configuration PASS"
    )

    print()

    print(
        "Validating synthetic transitions..."
    )

    validate_synthetic_transitions()

    print(
        "Synthetic transitions PASS"
    )

    print()

    print(
        "Validating synthetic short pulse..."
    )

    validate_synthetic_short_pulse()

    print(
        "Synthetic short pulse PASS"
    )

    print()

    print(
        "Validating constant PWM outputs..."
    )

    validate_constant_outputs(
        carrier_frame
    )

    print(
        "Constant PWM outputs PASS"
    )

    print()

    print(
        "Validating normal 50% PWM..."
    )

    validate_center_pwm(
        carrier_frame
    )

    print(
        "Normal 50% PWM PASS"
    )

    print()

    print(
        "Validating narrow PWM suppression..."
    )

    validate_narrow_pwm_suppression(
        carrier_frame
    )

    print(
        "Narrow PWM suppression PASS"
    )

    print()

    print(
        "Validating representative "
        "PWM compare values..."
    )

    validate_representative_pwm_values(
        carrier_frame
    )

    print(
        "Representative PWM values PASS"
    )

    print()

    print(
        "========================================"
    )

    print(
        " Fixed gate-drive validation PASS"
    )

    print(
        "========================================"
    )


if __name__ == "__main__":
    main()