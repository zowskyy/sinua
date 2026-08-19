"""Internal quaternion and Euler-angle utilities.

All quaternions are (w, x, y, z). Angles are in degrees unless noted.
Coordinate convention: Y-up, right-handed.
"""
from __future__ import annotations

import math


# ---------------------------------------------------------------------------
# Quaternion primitives
# ---------------------------------------------------------------------------

def quat_identity() -> tuple[float, float, float, float]:
    return (1.0, 0.0, 0.0, 0.0)


def quat_mul(
    q1: tuple[float, float, float, float],
    q2: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    return (
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
    )


def axis_quat(
    axis: tuple[float, float, float],
    angle_deg: float,
) -> tuple[float, float, float, float]:
    """Quaternion for a rotation of *angle_deg* about *axis* (need not be unit)."""
    ax, ay, az = axis
    mag = math.sqrt(ax * ax + ay * ay + az * az)
    if mag < 1e-10:
        return quat_identity()
    ax, ay, az = ax / mag, ay / mag, az / mag
    half = math.radians(angle_deg) / 2.0
    s = math.sin(half)
    return (math.cos(half), ax * s, ay * s, az * s)


def euler_to_quat(
    rx_deg: float,
    ry_deg: float,
    rz_deg: float,
    order: str,
) -> tuple[float, float, float, float]:
    """Convert intrinsic Euler angles to quaternion.

    *order* is a string like "ZXY" meaning: rotate about Z first, then X in
    the new frame, then Y in the new frame.  Angles are in degrees.
    """
    _axes = {
        "X": (1.0, 0.0, 0.0),
        "Y": (0.0, 1.0, 0.0),
        "Z": (0.0, 0.0, 1.0),
    }
    _angles = {"X": rx_deg, "Y": ry_deg, "Z": rz_deg}
    q = quat_identity()
    for ch in order:
        q = quat_mul(q, axis_quat(_axes[ch], _angles[ch]))
    return q


# ---------------------------------------------------------------------------
# Quaternion → rotation matrix
# ---------------------------------------------------------------------------

def quat_to_matrix(
    q: tuple[float, float, float, float],
) -> tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]:
    """Return a 3×3 row-major rotation matrix for quaternion q=(w,x,y,z)."""
    w, x, y, z = q
    x2, y2, z2 = 2 * x * x, 2 * y * y, 2 * z * z
    xy, xz, yz = 2 * x * y, 2 * x * z, 2 * y * z
    wx, wy, wz = 2 * w * x, 2 * w * y, 2 * w * z
    return (
        (1 - y2 - z2,  xy - wz,      xz + wy),
        (xy + wz,      1 - x2 - z2,  yz - wx),
        (xz - wy,      yz + wx,      1 - x2 - y2),
    )


# ---------------------------------------------------------------------------
# Rotation matrix → Euler angles
# ---------------------------------------------------------------------------

def matrix_to_euler_zxy(
    m: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ],
) -> tuple[float, float, float]:
    """Decompose rotation matrix into intrinsic ZXY Euler angles (degrees).

    Returns (rx, ry, rz) such that euler_to_quat(rx, ry, rz, "ZXY") recreates
    the same rotation (within floating-point tolerance).

    The matrix is assumed to be R = Rz * Rx * Ry (intrinsic ZXY order).

    Near gimbal lock (|rx| ≈ 90°) the decomposition is not unique; rz is
    set to zero and all rotation is absorbed into rx.
    """
    # R[2][1] = sin(rx)
    sx = max(-1.0, min(1.0, m[2][1]))
    rx = math.degrees(math.asin(sx))
    cx = math.cos(math.asin(sx))

    if abs(cx) > 1e-6:
        # ry from R[2][0] = -cx*sin(ry),  R[2][2] = cx*cos(ry)
        ry = math.degrees(math.atan2(-m[2][0], m[2][2]))
        # rz from R[0][1] = -sin(rz)*cx,  R[1][1] = cos(rz)*cx
        rz = math.degrees(math.atan2(-m[0][1], m[1][1]))
    else:
        # Gimbal lock: absorb everything into rx, set rz=0
        ry = math.degrees(math.atan2(m[0][2], m[0][0]))
        rz = 0.0

    return (rx, ry, rz)


def matrix_to_euler(
    m: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ],
    order: str = "ZXY",
) -> tuple[float, float, float]:
    """Convert rotation matrix to Euler angles for the given intrinsic *order*.

    Currently supports ZXY and XYZ; others raise ValueError.
    Returns (rx, ry, rz) in degrees.
    """
    if order == "ZXY":
        return matrix_to_euler_zxy(m)
    if order == "XYZ":
        return _matrix_to_euler_xyz(m)
    raise ValueError(f"Unsupported Euler order {order!r}; supported: 'ZXY', 'XYZ'")


def _matrix_to_euler_xyz(
    m: tuple,
) -> tuple[float, float, float]:
    """Intrinsic XYZ: R = Rx * Ry * Rz.  R[0][2] = sin(ry)."""
    sy = max(-1.0, min(1.0, m[0][2]))
    ry = math.degrees(math.asin(sy))
    cy = math.cos(math.asin(sy))

    if abs(cy) > 1e-6:
        # rx = atan2(-R[1][2], R[2][2]) = atan2(sx*cy, cx*cy)
        rx = math.degrees(math.atan2(-m[1][2], m[2][2]))
        # rz = atan2(-R[0][1], R[0][0]) = atan2(cy*sz, cy*cz)
        rz = math.degrees(math.atan2(-m[0][1], m[0][0]))
    else:
        # Gimbal lock: absorb everything into rx, set rz=0
        sign = 1.0 if sy > 0.0 else -1.0
        rx = math.degrees(math.atan2(sign * m[1][0], m[1][1]))
        rz = 0.0
    return (rx, ry, rz)


def quat_to_euler(
    q: tuple[float, float, float, float],
    order: str = "ZXY",
) -> tuple[float, float, float]:
    """Convert quaternion to intrinsic Euler angles in *order* (degrees)."""
    return matrix_to_euler(quat_to_matrix(q), order)
