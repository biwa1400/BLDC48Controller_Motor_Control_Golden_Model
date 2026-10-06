# ============================================================
# Fixed command update / atomic commit Golden Model
# ============================================================
#
# This module models:
#
#   1. Batch snapshot
#   2. Sequential 22-phase calculation
#   3. compare_shadow[]
#   4. shadow_ready
#   5. Atomic shadow -> active commit
#      at PWM frame boundary only
#
# Important architectural rules:
#
#   - One calculation batch uses one immutable input snapshot.
#
#   - Encoder/amplitude changes during a batch do NOT affect
#     the current batch.
#
#   - compare_active[] never changes when an individual phase
#     calculation finishes.
#
#   - compare_active[] never changes merely because the full
#     shadow vector becomes ready.
#
#   - All 22 active compare values change atomically at the
#     next PWM frame boundary.
#
# This model does NOT yet include:
#
#   - exact 50 MHz FSM timing
#   - 9 clocks / phase timing
#   - LUT dual-bank swap timing
#   - raw PWM generation
#   - complementary gate outputs
#   - deadtime
#
# ============================================================

from dataclasses import dataclass

from config import NUM_PHASES

from fixed_derived_config import (
    AMPLITUDE_SCALE,
    PWM_CENTER,
)

from fixed_angle_model import (
    calculate_fixed_angles,
)

from fixed_waveform_model import (
    load_waveform_lut,
    calculate_fixed_waveform,
)

from fixed_motor_model import (
    calculate_fixed_motor,
)


# ============================================================
# Snapshot
# ============================================================

@dataclass(frozen=True)
class CommandSnapshot:
    """
    Immutable control snapshot captured at the beginning
    of one complete 22-phase calculation batch.
    """

    encoder_count: int
    amplitude_cmd: int
    lut_bank: int


# ============================================================
# Batch state
# ============================================================

@dataclass
class CommandUpdateState:
    """
    State corresponding conceptually to future RTL registers.
    """

    # Current immutable batch snapshot.
    snapshot: CommandSnapshot | None

    # Phase currently being calculated.
    next_phase_index: int

    # Next complete vector under construction.
    compare_shadow: list[int]

    # Current vector used by the PWM engine.
    compare_active: list[int]

    # True only after all 22 shadow values are valid.
    shadow_ready: bool

    # Whether a calculation batch is currently active.
    batch_active: bool

    # Diagnostic counters.
    batch_counter: int
    commit_counter: int


# ============================================================
# State creation
# ============================================================

def create_initial_state() -> CommandUpdateState:
    """
    Initial state.

    The active compare vector is initialized to PWM_CENTER.

    IMPORTANT:
    This does NOT mean the future physical gate outputs should
    automatically be enabled after reset.

    Gate enable / safe reset behavior will be handled later
    in the drive-output layer.

    For this numerical command-update model, CENTER is simply
    a clean deterministic initial compare value.
    """

    return CommandUpdateState(
        snapshot=None,
        next_phase_index=0,
        compare_shadow=[
            PWM_CENTER
            for _ in range(NUM_PHASES)
        ],
        compare_active=[
            PWM_CENTER
            for _ in range(NUM_PHASES)
        ],
        shadow_ready=False,
        batch_active=False,
        batch_counter=0,
        commit_counter=0,
    )


# ============================================================
# State validation
# ============================================================

def validate_state(
    state: CommandUpdateState,
) -> None:

    if len(
        state.compare_shadow
    ) != NUM_PHASES:

        raise AssertionError(
            "compare_shadow has incorrect length."
        )

    if len(
        state.compare_active
    ) != NUM_PHASES:

        raise AssertionError(
            "compare_active has incorrect length."
        )

    if not (
        0
        <= state.next_phase_index
        <= NUM_PHASES
    ):

        raise AssertionError(
            "next_phase_index is out of range."
        )

    if (
        state.batch_active
        and state.snapshot is None
    ):

        raise AssertionError(
            "Active batch has no snapshot."
        )

    if (
        state.shadow_ready
        and state.batch_active
    ):

        raise AssertionError(
            "shadow_ready and batch_active "
            "must not both be true."
        )

    if (
        state.shadow_ready
        and state.next_phase_index
        != NUM_PHASES
    ):

        raise AssertionError(
            "shadow_ready requires all phases "
            "to be complete."
        )


# ============================================================
# Start batch
# ============================================================

def start_batch(
    state: CommandUpdateState,
    encoder_count: int,
    amplitude_cmd: int,
    lut_bank: int = 0,
) -> None:
    """
    Start one new 22-phase calculation batch.

    Encoder, amplitude and LUT-bank selection are captured
    here and remain immutable for the complete batch.
    """

    validate_state(
        state
    )

    if state.batch_active:
        raise RuntimeError(
            "Cannot start a new batch while another "
            "batch is active."
        )

    if state.shadow_ready:
        raise RuntimeError(
            "Cannot overwrite an uncommitted shadow vector."
        )

    if lut_bank not in (
        0,
        1,
    ):
        raise ValueError(
            "LUT bank must be 0 or 1."
        )

    state.snapshot = CommandSnapshot(
        encoder_count=encoder_count,
        amplitude_cmd=amplitude_cmd,
        lut_bank=lut_bank,
    )

    state.next_phase_index = 0

    state.batch_active = True

    state.shadow_ready = False

    state.batch_counter += 1


# ============================================================
# Calculate one phase
# ============================================================

def calculate_next_phase(
    state: CommandUpdateState,
    waveform_lut,
) -> None:
    """
    Complete exactly one phase calculation.

    This function deliberately uses ONLY state.snapshot.

    No external encoder/amplitude input is accepted here.

    That structural choice makes it impossible for a changing
    external command to contaminate a batch after it starts.
    """

    validate_state(
        state
    )

    if not state.batch_active:
        raise RuntimeError(
            "No active calculation batch."
        )

    if state.snapshot is None:
        raise AssertionError(
            "Batch snapshot is missing."
        )

    phase_index = (
        state.next_phase_index
    )

    if not (
        0
        <= phase_index
        < NUM_PHASES
    ):
        raise AssertionError(
            "Invalid phase index during calculation."
        )

    # --------------------------------------------------------
    # Reconstruct the complete angle vector from the frozen
    # encoder snapshot.
    #
    # This is not intended to represent the final RTL's exact
    # per-clock implementation yet.
    #
    # It deliberately reuses the already validated angle
    # Golden Model.
    # --------------------------------------------------------

    angle_trace = calculate_fixed_angles(
        state.snapshot.encoder_count
    )

    phase_angle_u16 = (
        angle_trace.phase_angles_u16[
            phase_index
        ]
    )

    # --------------------------------------------------------
    # Calculate this one phase using the frozen amplitude.
    # --------------------------------------------------------

    phase_result = (
        calculate_fixed_waveform(
            phase_angle_u16=phase_angle_u16,
            amplitude_cmd=(
                state.snapshot.amplitude_cmd
            ),
            waveform_lut=waveform_lut,
        )
    )

    # --------------------------------------------------------
    # Store only into SHADOW.
    #
    # ACTIVE MUST NOT CHANGE HERE.
    # --------------------------------------------------------

    state.compare_shadow[
        phase_index
    ] = phase_result.compare

    state.next_phase_index += 1

    # --------------------------------------------------------
    # Complete batch?
    # --------------------------------------------------------

    if (
        state.next_phase_index
        == NUM_PHASES
    ):

        state.batch_active = False
        state.shadow_ready = True

    validate_state(
        state
    )


# ============================================================
# Calculate complete batch
# ============================================================

def calculate_complete_batch(
    state: CommandUpdateState,
    waveform_lut,
) -> None:
    """
    Finish the current batch phase by phase.
    """

    if not state.batch_active:
        raise RuntimeError(
            "No active calculation batch."
        )

    while state.batch_active:
        calculate_next_phase(
            state=state,
            waveform_lut=waveform_lut,
        )


# ============================================================
# PWM frame boundary
# ============================================================

def pwm_frame_boundary(
    state: CommandUpdateState,
) -> bool:
    """
    Process one safe PWM frame boundary.

    If a complete shadow vector is ready:

        compare_shadow -> compare_active

    atomically.

    Otherwise:

        compare_active remains unchanged.

    Returns:

        True  = commit occurred
        False = no commit
    """

    validate_state(
        state
    )

    if not state.shadow_ready:
        return False

    # --------------------------------------------------------
    # Atomic vector commit.
    #
    # Python assignment occurs as a list copy here.
    #
    # Future RTL semantics:
    #
    #   all 22 active registers update on the same
    #   200 MHz clock edge.
    # --------------------------------------------------------

    state.compare_active = (
        state.compare_shadow.copy()
    )

    state.shadow_ready = False

    state.next_phase_index = 0

    state.snapshot = None

    state.commit_counter += 1

    validate_state(
        state
    )

    return True


# ============================================================
# Utility
# ============================================================

def tuple_active(
    state: CommandUpdateState,
) -> tuple[int, ...]:

    return tuple(
        state.compare_active
    )


def tuple_shadow(
    state: CommandUpdateState,
) -> tuple[int, ...]:

    return tuple(
        state.compare_shadow
    )


# ============================================================
# Test 1
#
# Initial state
# ============================================================

def validate_initial_state() -> None:

    state = create_initial_state()

    assert (
        state.snapshot is None
    )

    assert (
        state.batch_active
        is False
    )

    assert (
        state.shadow_ready
        is False
    )

    assert (
        state.next_phase_index
        == 0
    )

    assert all(
        compare == PWM_CENTER
        for compare
        in state.compare_active
    )

    assert all(
        compare == PWM_CENTER
        for compare
        in state.compare_shadow
    )


# ============================================================
# Test 2
#
# Active must not change during batch
# ============================================================

def validate_active_unchanged_during_batch(
    waveform_lut,
) -> None:

    state = create_initial_state()

    original_active = (
        tuple_active(state)
    )

    start_batch(
        state=state,
        encoder_count=1024,
        amplitude_cmd=(
            AMPLITUDE_SCALE // 2
        ),
        lut_bank=0,
    )

    for _ in range(NUM_PHASES):

        calculate_next_phase(
            state=state,
            waveform_lut=waveform_lut,
        )

        assert (
            tuple_active(state)
            == original_active
        )

    assert (
        state.shadow_ready
        is True
    )

    # Even after the complete vector is ready,
    # active must still remain unchanged.

    assert (
        tuple_active(state)
        == original_active
    )


# ============================================================
# Test 3
#
# Shadow must match direct Golden Model
# ============================================================

def validate_shadow_against_motor_model(
    waveform_lut,
) -> None:

    encoder_count = 1024

    amplitude_cmd = (
        AMPLITUDE_SCALE // 2
    )

    state = create_initial_state()

    start_batch(
        state=state,
        encoder_count=encoder_count,
        amplitude_cmd=amplitude_cmd,
        lut_bank=0,
    )

    calculate_complete_batch(
        state=state,
        waveform_lut=waveform_lut,
    )

    reference = calculate_fixed_motor(
        encoder_count=encoder_count,
        amplitude_cmd=amplitude_cmd,
        waveform_lut=waveform_lut,
    )

    assert (
        tuple_shadow(state)
        == reference.phase_compares
    )


# ============================================================
# Test 4
#
# No commit before boundary
# ============================================================

def validate_no_early_commit(
    waveform_lut,
) -> None:

    state = create_initial_state()

    initial_active = (
        tuple_active(state)
    )

    start_batch(
        state=state,
        encoder_count=1024,
        amplitude_cmd=(
            AMPLITUDE_SCALE // 2
        ),
        lut_bank=0,
    )

    calculate_complete_batch(
        state=state,
        waveform_lut=waveform_lut,
    )

    assert (
        state.shadow_ready
        is True
    )

    assert (
        tuple_active(state)
        == initial_active
    )

    assert (
        tuple_shadow(state)
        != initial_active
    )


# ============================================================
# Test 5
#
# Atomic commit
# ============================================================

def validate_atomic_commit(
    waveform_lut,
) -> None:

    state = create_initial_state()

    start_batch(
        state=state,
        encoder_count=1024,
        amplitude_cmd=(
            AMPLITUDE_SCALE // 2
        ),
        lut_bank=0,
    )

    calculate_complete_batch(
        state=state,
        waveform_lut=waveform_lut,
    )

    expected_active = (
        tuple_shadow(state)
    )

    old_active = (
        tuple_active(state)
    )

    assert (
        expected_active
        != old_active
    )

    committed = pwm_frame_boundary(
        state
    )

    assert (
        committed
        is True
    )

    assert (
        tuple_active(state)
        == expected_active
    )

    assert (
        state.shadow_ready
        is False
    )

    assert (
        state.commit_counter
        == 1
    )


# ============================================================
# Test 6
#
# Boundary without ready shadow
# ============================================================

def validate_boundary_without_shadow(
) -> None:

    state = create_initial_state()

    before = (
        tuple_active(state)
    )

    committed = pwm_frame_boundary(
        state
    )

    assert (
        committed
        is False
    )

    assert (
        tuple_active(state)
        == before
    )

    assert (
        state.commit_counter
        == 0
    )


# ============================================================
# Test 7
#
# Snapshot coherence
# ============================================================

def validate_snapshot_coherence(
    waveform_lut,
) -> None:
    """
    Simulate external input changes in the middle of a batch.

    Batch A starts with:

        encoder = 1024
        amplitude = 0.5

    After phase 10 we conceptually change external inputs to:

        encoder = 2048
        amplitude = 0.25

    Because calculate_next_phase() accepts no external command
    inputs, the current batch must remain entirely based on
    the original snapshot.

    The next batch may use the new inputs.
    """

    state = create_initial_state()

    original_encoder = 1024

    original_amplitude = (
        AMPLITUDE_SCALE // 2
    )

    new_encoder = 2048

    new_amplitude = (
        AMPLITUDE_SCALE // 4
    )

    # --------------------------------------------------------
    # Start original batch
    # --------------------------------------------------------

    start_batch(
        state=state,
        encoder_count=original_encoder,
        amplitude_cmd=original_amplitude,
        lut_bank=0,
    )

    # --------------------------------------------------------
    # Calculate first 10 phases.
    # --------------------------------------------------------

    for _ in range(10):

        calculate_next_phase(
            state=state,
            waveform_lut=waveform_lut,
        )

    # --------------------------------------------------------
    # External inputs conceptually change HERE.
    #
    # We intentionally do nothing to the snapshot.
    #
    # Continue phases 11..22.
    # --------------------------------------------------------

    while state.batch_active:

        calculate_next_phase(
            state=state,
            waveform_lut=waveform_lut,
        )

    # --------------------------------------------------------
    # Current batch must still equal ORIGINAL input reference.
    # --------------------------------------------------------

    original_reference = (
        calculate_fixed_motor(
            encoder_count=original_encoder,
            amplitude_cmd=original_amplitude,
            waveform_lut=waveform_lut,
        )
    )

    assert (
        tuple_shadow(state)
        == original_reference.phase_compares
    )

    # --------------------------------------------------------
    # Commit original batch.
    # --------------------------------------------------------

    committed = pwm_frame_boundary(
        state
    )

    assert (
        committed
        is True
    )

    assert (
        tuple_active(state)
        == original_reference.phase_compares
    )

    # --------------------------------------------------------
    # NEXT batch now uses changed external inputs.
    # --------------------------------------------------------

    start_batch(
        state=state,
        encoder_count=new_encoder,
        amplitude_cmd=new_amplitude,
        lut_bank=0,
    )

    calculate_complete_batch(
        state=state,
        waveform_lut=waveform_lut,
    )

    new_reference = (
        calculate_fixed_motor(
            encoder_count=new_encoder,
            amplitude_cmd=new_amplitude,
            waveform_lut=waveform_lut,
        )
    )

    assert (
        tuple_shadow(state)
        == new_reference.phase_compares
    )

    assert (
        tuple_shadow(state)
        != original_reference.phase_compares
    )


# ============================================================
# Test 8
#
# Partial batch must never commit
# ============================================================

def validate_partial_batch_cannot_commit(
    waveform_lut,
) -> None:

    state = create_initial_state()

    initial_active = (
        tuple_active(state)
    )

    start_batch(
        state=state,
        encoder_count=1024,
        amplitude_cmd=(
            AMPLITUDE_SCALE // 2
        ),
        lut_bank=0,
    )

    # Calculate only 10 of 22 phases.

    for _ in range(10):

        calculate_next_phase(
            state=state,
            waveform_lut=waveform_lut,
        )

    assert (
        state.batch_active
        is True
    )

    assert (
        state.shadow_ready
        is False
    )

    # PWM frame boundary occurs before batch completion.

    committed = pwm_frame_boundary(
        state
    )

    assert (
        committed
        is False
    )

    assert (
        tuple_active(state)
        == initial_active
    )

    # Finish remaining phases.

    calculate_complete_batch(
        state=state,
        waveform_lut=waveform_lut,
    )

    assert (
        state.shadow_ready
        is True
    )

    # Still no active change until another boundary.

    assert (
        tuple_active(state)
        == initial_active
    )

    committed = pwm_frame_boundary(
        state
    )

    assert (
        committed
        is True
    )

    assert (
        tuple_active(state)
        != initial_active
    )


# ============================================================
# Test 9
#
# Multiple sequential batches
# ============================================================

def validate_multiple_batches(
    waveform_lut,
) -> None:

    state = create_initial_state()

    test_commands = (
        (
            1024,
            AMPLITUDE_SCALE // 2,
        ),
        (
            1200,
            AMPLITUDE_SCALE // 4,
        ),
        (
            2048,
            AMPLITUDE_SCALE,
        ),
        (
            3000,
            0,
        ),
        (
            4095,
            AMPLITUDE_SCALE // 2,
        ),
    )

    expected_commit_count = 0

    for (
        encoder_count,
        amplitude_cmd,
    ) in test_commands:

        start_batch(
            state=state,
            encoder_count=encoder_count,
            amplitude_cmd=amplitude_cmd,
            lut_bank=0,
        )

        calculate_complete_batch(
            state=state,
            waveform_lut=waveform_lut,
        )

        reference = (
            calculate_fixed_motor(
                encoder_count=encoder_count,
                amplitude_cmd=amplitude_cmd,
                waveform_lut=waveform_lut,
            )
        )

        assert (
            tuple_shadow(state)
            == reference.phase_compares
        )

        # Active still contains previous frame's vector.

        committed = pwm_frame_boundary(
            state
        )

        assert (
            committed
            is True
        )

        expected_commit_count += 1

        assert (
            state.commit_counter
            == expected_commit_count
        )

        assert (
            tuple_active(state)
            == reference.phase_compares
        )


# ============================================================
# Diagnostic example
# ============================================================

def print_reference_commit_example(
    waveform_lut,
) -> None:

    state = create_initial_state()

    print(
        "Initial active compares:"
    )

    print(
        tuple_active(state)
    )

    print()

    start_batch(
        state=state,
        encoder_count=1024,
        amplitude_cmd=(
            AMPLITUDE_SCALE // 2
        ),
        lut_bank=0,
    )

    # --------------------------------------------------------
    # First 10 phases
    # --------------------------------------------------------

    for _ in range(10):

        calculate_next_phase(
            state=state,
            waveform_lut=waveform_lut,
        )

    print(
        "After 10 / 22 phases:"
    )

    print(
        f"  batch_active = "
        f"{state.batch_active}"
    )

    print(
        f"  shadow_ready = "
        f"{state.shadow_ready}"
    )

    print(
        "  active       = "
        f"{tuple_active(state)}"
    )

    print()

    # --------------------------------------------------------
    # Boundary during partial batch
    # --------------------------------------------------------

    committed = pwm_frame_boundary(
        state
    )

    print(
        "PWM boundary during partial batch:"
    )

    print(
        f"  committed    = "
        f"{committed}"
    )

    print(
        "  active       = "
        f"{tuple_active(state)}"
    )

    print()

    # --------------------------------------------------------
    # Finish batch
    # --------------------------------------------------------

    calculate_complete_batch(
        state=state,
        waveform_lut=waveform_lut,
    )

    print(
        "After 22 / 22 phases:"
    )

    print(
        f"  batch_active = "
        f"{state.batch_active}"
    )

    print(
        f"  shadow_ready = "
        f"{state.shadow_ready}"
    )

    print(
        "  shadow       = "
        f"{tuple_shadow(state)}"
    )

    print(
        "  active       = "
        f"{tuple_active(state)}"
    )

    print()

    # --------------------------------------------------------
    # Safe commit
    # --------------------------------------------------------

    committed = pwm_frame_boundary(
        state
    )

    print(
        "Next PWM frame boundary:"
    )

    print(
        f"  committed    = "
        f"{committed}"
    )

    print(
        f"  shadow_ready = "
        f"{state.shadow_ready}"
    )

    print(
        "  active       = "
        f"{tuple_active(state)}"
    )

    print()


# ============================================================
# Main
# ============================================================

def main() -> None:

    waveform_lut = (
        load_waveform_lut()
    )

    print(
        "========================================"
    )

    print(
        " Fixed command update model"
    )

    print(
        "========================================"
    )

    print()

    # --------------------------------------------------------
    # Example
    # --------------------------------------------------------

    print_reference_commit_example(
        waveform_lut
    )

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    print(
        "Validating initial state..."
    )

    validate_initial_state()

    print(
        "Initial state PASS"
    )

    print()

    print(
        "Validating active stability "
        "during batch..."
    )

    validate_active_unchanged_during_batch(
        waveform_lut
    )

    print(
        "Active stability PASS"
    )

    print()

    print(
        "Validating shadow against "
        "complete motor model..."
    )

    validate_shadow_against_motor_model(
        waveform_lut
    )

    print(
        "Shadow reference PASS"
    )

    print()

    print(
        "Validating no early commit..."
    )

    validate_no_early_commit(
        waveform_lut
    )

    print(
        "No early commit PASS"
    )

    print()

    print(
        "Validating atomic commit..."
    )

    validate_atomic_commit(
        waveform_lut
    )

    print(
        "Atomic commit PASS"
    )

    print()

    print(
        "Validating empty boundary..."
    )

    validate_boundary_without_shadow()

    print(
        "Empty boundary PASS"
    )

    print()

    print(
        "Validating batch snapshot "
        "coherence..."
    )

    validate_snapshot_coherence(
        waveform_lut
    )

    print(
        "Batch snapshot coherence PASS"
    )

    print()

    print(
        "Validating partial-batch "
        "boundary behavior..."
    )

    validate_partial_batch_cannot_commit(
        waveform_lut
    )

    print(
        "Partial-batch boundary PASS"
    )

    print()

    print(
        "Validating multiple batches..."
    )

    validate_multiple_batches(
        waveform_lut
    )

    print(
        "Multiple batches PASS"
    )

    print()

    print(
        "========================================"
    )

    print(
        " Command update architecture "
        "validation PASS"
    )

    print(
        "========================================"
    )


if __name__ == "__main__":
    main()