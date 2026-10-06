# ============================================================
# Fixed-Point Golden Model Configuration
# ============================================================
#
# This file contains FPGA-oriented quantization parameters.
#
# Physical/control specifications belong in config.py.
# Quantization and digital implementation parameters belong here.
# ============================================================


# ------------------------------------------------------------
# FPGA clock
# ------------------------------------------------------------

FPGA_CLOCK_HZ = 200_000_000


# ------------------------------------------------------------
# Internal angle representation
# ------------------------------------------------------------
#
# One complete revolution is represented by an unsigned
# 16-bit phase value:
#
#     0x0000 =   0 degrees
#     0x4000 =  90 degrees
#     0x8000 = 180 degrees
#     0xC000 = 270 degrees
#
# The value wraps naturally at 2^16.
#
# Angle resolution:
#
#     360 / 65536 = 0.0054931640625 degrees / LSB
#
# The LM10 encoder has 4096 counts/revolution, therefore the
# 12-bit encoder angle can be mapped exactly into this format
# by shifting left by 4 bits.
# ------------------------------------------------------------

ANGLE_BITS = 16

ANGLE_FULL_SCALE = 1 << ANGLE_BITS       # 65536
ANGLE_MASK = ANGLE_FULL_SCALE - 1        # 0xFFFF

ANGLE_90 = ANGLE_FULL_SCALE // 4         # 16384
ANGLE_180 = ANGLE_FULL_SCALE // 2        # 32768
ANGLE_270 = 3 * ANGLE_FULL_SCALE // 4    # 49152

ANGLE_LSB_DEG = 360.0 / ANGLE_FULL_SCALE


# ------------------------------------------------------------
# Encoder -> internal angle
# ------------------------------------------------------------

ENCODER_BITS = 12
ENCODER_FULL_SCALE = 1 << ENCODER_BITS   # 4096

ENCODER_TO_ANGLE_SHIFT = ANGLE_BITS - ENCODER_BITS   # 4


# ------------------------------------------------------------
# 22-phase angle offsets
# ------------------------------------------------------------
#
# Ideal phase offset:
#
#     offset[k] = k * 65536 / 22
#
# Each phase is rounded independently to the nearest integer.
#
# IMPORTANT:
# Do not generate each phase by repeatedly adding one rounded
# phase step. Independent offsets prevent cumulative error.
# ------------------------------------------------------------

NUM_PHASES_FIXED = 22

PHASE_OFFSETS = tuple(
    round(k * ANGLE_FULL_SCALE / NUM_PHASES_FIXED)
    for k in range(NUM_PHASES_FIXED)
)