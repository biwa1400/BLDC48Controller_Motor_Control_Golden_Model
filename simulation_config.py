from pathlib import Path


# ============================================================
# Simulation configuration
#
# These parameters control how the Python simulations are run.
# They are NOT part of the motor-control algorithm itself.
# ============================================================


# ============================================================
# Simulation result directory
# ============================================================

SIM_RESULT_DIR = Path("sim_result")

SIM_RESULT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# Ideal physical PWM specification
# ============================================================

# Ideal PWM frequency used by the Float Golden Model.
#
# Physical unit:
#     Hz
#
# FPGA clock quantization will be introduced later.
PWM_FREQUENCY_HZ = 15_000.0


# ============================================================
# PWM waveform simulation
# ============================================================

# Encoder position used for PWM waveform tests.
#
# Unit:
#     encoder count
PWM_TEST_ENCODER_COUNT = 1024


# Number of ordinary simulation samples per PWM period.
#
# At 15 kHz:
#
#     PWM period = 66.6666667 us
#
# With 20,000 samples:
#
#     sample spacing ~= 3.333 ns
#
# Exact deadtime switching events are inserted separately,
# so deadtime itself is NOT quantized by this value.
PWM_SIMULATION_SAMPLES = 20_000


# ============================================================
# Derived physical PWM quantities
# ============================================================

PWM_PERIOD_S = (
    1.0 / PWM_FREQUENCY_HZ
)

PWM_PERIOD_US = (
    PWM_PERIOD_S
    * 1_000_000.0
)


SIMULATION_SAMPLE_PERIOD_S = (
    PWM_PERIOD_S
    / PWM_SIMULATION_SAMPLES
)

SIMULATION_SAMPLE_PERIOD_NS = (
    SIMULATION_SAMPLE_PERIOD_S
    * 1_000_000_000.0
)


# ============================================================
# Single-phase ideal PWM
# ============================================================

SINGLE_PWM_CSV_FILE = (
    SIM_RESULT_DIR
    / "single_pwm_cycle.csv"
)

SINGLE_PWM_HTML_FILE = (
    SIM_RESULT_DIR
    / "single_pwm_cycle.html"
)


# ============================================================
# Multi-phase ideal PWM
# ============================================================

MULTI_PHASE_PWM_CSV_FILE = (
    SIM_RESULT_DIR
    / "multi_phase_pwm_cycle.csv"
)

MULTI_PHASE_PWM_HTML_FILE = (
    SIM_RESULT_DIR
    / "multi_phase_pwm_cycle.html"
)


# ============================================================
# Single-phase complementary PWM
# ============================================================

COMPLEMENTARY_PWM_CSV_FILE = (
    SIM_RESULT_DIR
    / "complementary_pwm_cycle.csv"
)

COMPLEMENTARY_PWM_HTML_FILE = (
    SIM_RESULT_DIR
    / "complementary_pwm_cycle.html"
)


# ============================================================
# Single-phase deadtime simulation
# ============================================================

DEADTIME_PWM_CSV_FILE = (
    SIM_RESULT_DIR
    / "deadtime_pwm_cycle.csv"
)

DEADTIME_PWM_HTML_FILE = (
    SIM_RESULT_DIR
    / "deadtime_pwm_cycle.html"
)


# ============================================================
# 22-phase / 44-gate deadtime simulation
# ============================================================

MULTI_PHASE_DEADTIME_CSV_FILE = (
    SIM_RESULT_DIR
    / "multi_phase_deadtime.csv"
)

MULTI_PHASE_DEADTIME_HTML_FILE = (
    SIM_RESULT_DIR
    / "multi_phase_deadtime.html"
)


# ============================================================
# Full mechanical rotation simulation
# ============================================================

FULL_ROTATION_CSV_FILE = (
    SIM_RESULT_DIR
    / "float_full_rotation.csv"
)

FULL_ROTATION_HTML_FILE = (
    SIM_RESULT_DIR
    / "float_full_rotation.html"
)