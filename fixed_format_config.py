# ============================================================
# Fixed-point FPGA format configuration
# ============================================================

# ------------------------------------------------------------
# FPGA clocks
# ------------------------------------------------------------

CALC_CLOCK_HZ = 50_000_000
PWM_CLOCK_HZ = 200_000_000


# ------------------------------------------------------------
# Internal angle format
# ------------------------------------------------------------

# Unsigned modulo angle:
#
#   0x0000 =   0 deg
#   0x4000 =  90 deg
#   0x8000 = 180 deg
#   0xC000 = 270 deg
#
# One full revolution = 2^16 counts.

ANGLE_BITS = 16


# ------------------------------------------------------------
# Waveform LUT
# ------------------------------------------------------------

# Half-wave LUT:
#
#   0 ... 180 deg
#
# Address:
#
#   sign     = angle[15]
#   LUT addr = angle[14:3]
#
# Therefore:
#
#   12 address bits
#   4096 entries per bank

WAVEFORM_LUT_ADDRESS_BITS = 12

# Unsigned normalized magnitude:
#
#   0    = 0.0
#   4096 = 1.0
#
# Values above 4096 are reserved.

WAVEFORM_LUT_DATA_BITS = 13

WAVEFORM_LUT_SCALE_BITS = 12

# Runtime waveform switching uses two LUT banks.

LUT_DOUBLE_BUFFER = True


# ------------------------------------------------------------
# Amplitude command
# ------------------------------------------------------------

# Unsigned Q0.12-style representation:
#
#   0    = 0.0
#   1024 = 0.25
#   2048 = 0.5
#   3072 = 0.75
#   4096 = 1.0
#
# Storage width is 13 bits because 1.0 must be represented
# exactly as 4096.

AMPLITUDE_BITS = 13
AMPLITUDE_FRAC_BITS = 12


# ------------------------------------------------------------
# PWM architecture
# ------------------------------------------------------------

# The PWM carrier uses one shared center-aligned
# up/down triangular counter for all phases.
#
# PWM_TOP is derived automatically from:
#
#   PWM_CLOCK_HZ
#   PWM_FREQUENCY_HZ
#
# PWM_TOP is required to be even so that:
#
#   PWM_CENTER = PWM_TOP / 2
#
# is an exact integer.

PWM_TOP_MUST_BE_EVEN = True


# ------------------------------------------------------------
# Fixed-point rounding
# ------------------------------------------------------------

# Explicit rounding policy used by the fixed-point model.
#
# Do not rely on Python round(), because Python uses
# ties-to-even behavior.

ROUNDING_MODE = "ROUND_HALF_UP"