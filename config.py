# ============================================================
# Motor-control configuration
# ============================================================
#
# This file contains physical and control-level parameters.
#
# It describes WHAT the motor controller should do.
#
# FPGA representation details such as bit widths, LUT widths,
# clock frequencies, and fixed-point formats belong in:
#
#     fixed_format_config.py
#
# Quantized / derived FPGA constants belong in:
#
#     fixed_derived_config.py
#
# ============================================================


# ------------------------------------------------------------
# Encoder configuration
# ------------------------------------------------------------

# LM10 encoder counts per one mechanical revolution
LM10_COUNTS = 4096

# Number of motor pole pairs
POLE_PAIRS = 3

# Number of motor phases
NUM_PHASES = 22

# Encoder count corresponding to the defined mechanical zero
ENCODER_OFFSET = 1022

# Electrical angle direction relative to increasing encoder count
#
# +1 : electrical angle increases with encoder count
# -1 : electrical angle decreases with encoder count
#
# The old FPGA design effectively uses -1.
ELECTRICAL_DIRECTION = -1


# ------------------------------------------------------------
# Voltage-vector / torque direction
# ------------------------------------------------------------

# Defines whether the commanded stator voltage vector is
# +90 degrees or -90 degrees from the rotor electrical angle.
#
# +1 : +90 degrees
# -1 : -90 degrees
TORQUE_DIRECTION = -1


# ------------------------------------------------------------
# Phase advance
# ------------------------------------------------------------

# Additional electrical phase advance in degrees.
#
# This is the Float Golden Model equivalent of the old
# PHASE_ADV control input.
PHASE_ADVANCE_DEG = 10.0


# ------------------------------------------------------------
# Voltage amplitude
# ------------------------------------------------------------

# Normalized sinusoidal voltage amplitude.
#
# 0.0 -> all phase duties are 50%
# 0.5 -> phase duties ideally range from 25% to 75%
# 1.0 -> phase duties ideally range from 0% to 100%
#
# This is the Float Golden Model equivalent of the old
# VS_RHO control input.
VOLTAGE_AMPLITUDE = 0.5


# ------------------------------------------------------------
# PWM physical specification
# ------------------------------------------------------------

# Requested physical PWM switching frequency.
#
# IMPORTANT:
# This is the desired physical/control specification.
#
# The actual FPGA PWM frequency will be derived from:
#
#     PWM_FREQUENCY_HZ
#     PWM_CLOCK_HZ
#     PWM carrier architecture
#
# The resulting integer PWM_TOP and actual frequency are
# calculated automatically in fixed_derived_config.py.
#
# Do NOT manually place PWM_TOP or PWM_CENTER here.
PWM_FREQUENCY_HZ = 15_000.0


# ------------------------------------------------------------
# Dead-time compensation (DTC)
# ------------------------------------------------------------

# Enable/disable dead-time compensation.
#
# IMPORTANT:
# This is NOT the physical gate deadtime.
#
# The old FPGA design used DTC to modify the PWM compare value
# in an attempt to compensate for the average voltage error
# introduced by deadtime.
#
# The old "> 50% -> +DTC, <= 50% -> -DTC" algorithm will NOT
# be copied into the new Float Golden Model.
#
# For now the interface is reserved, but compensation remains
# disabled until a better method (preferably based on phase
# current direction) is implemented.
DTC_ENABLE = False

# Reserved dead-time compensation magnitude.
#
# Physical unit: nanoseconds.
#
# Currently this parameter does NOT participate in calculations
# because DTC_ENABLE is False and the new compensation algorithm
# has not yet been implemented.
DEADTIME_COMPENSATION_NS = 40.0


# ------------------------------------------------------------
# Physical gate-drive deadtime
# ------------------------------------------------------------

# Low-side OFF -> High-side ON deadtime
DEADTIME_LH_NS = 40.0

# High-side OFF -> Low-side ON deadtime
DEADTIME_HL_NS = 40.0