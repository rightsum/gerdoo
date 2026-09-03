"""
Geometry for pointing the neck at a face.

Kept free of MediaPipe, HTTP and servos so it can be tested in milliseconds.
The tracker around it is a loop; this is the part that decides where to look.
"""

from dataclasses import dataclass

# Servo limits, mirroring the Teensy firmware. Exceeding them does nothing on
# the robot — the firmware constrains too — but clamping here keeps the
# tracker's idea of where the neck is honest.
PAN_MIN, PAN_MAX = 70, 140
TILT_MIN, TILT_MAX = 60, 120
# Where the head looks straight ahead. Found by adjusting the real robot, not
# by averaging the limits — the bracket is not mounted symmetrically, so the
# midpoint of the servo range is not the middle of the room.
PAN_CENTRE = 110
TILT_CENTRE = 110

# Fraction of the frame the face may be off-centre before the neck moves at
# all. Without it the neck hunts continuously around the centre, because the
# detector's box jitters by a pixel or two every frame.
DEADZONE = 0.06

# Degrees of neck movement per unit of normalised error. Low on purpose: an
# over-eager gain overshoots, then corrects, and the head oscillates.
GAIN_PAN = 14.0
GAIN_TILT = 10.0

# Largest single correction. Caps how violently the head can snap toward a face
# that appears at the edge of frame — the SG90s are driving a screen.
MAX_STEP = 6.0


@dataclass(frozen=True)
class Face:
    """A detection, in normalised frame coordinates (0..1)."""
    cx: float
    cy: float
    w: float
    h: float

    @property
    def area(self) -> float:
        return self.w * self.h


def largest(faces: list[Face]) -> Face | None:
    """
    The face occupying the most frame.

    Nearest-looking rather than first-found: the robot should attend to the
    person in front of it, not someone crossing the room behind them.
    """
    return max(faces, key=lambda f: f.area) if faces else None


def centring_error(face: Face) -> tuple[float, float]:
    """
    How far the face is from the centre, as a fraction of the frame.

    Positive x means the face is to the right of centre, positive y means below.
    """
    return face.cx - 0.5, face.cy - 0.5


def _step(error: float, gain: float) -> float:
    if abs(error) < DEADZONE:
        return 0.0
    step = error * gain
    return max(-MAX_STEP, min(MAX_STEP, step))


def next_position(face: Face, pan: float, tilt: float,
                  pan_inverted: bool = True,
                  tilt_inverted: bool = True) -> tuple[float, float]:
    """
    Where the neck should move to put this face in the middle of frame.

    Both axes are inverted, which is a fact about how this gimbal is built
    rather than anything derivable. The camera faces the same way as the robot,
    so a face on the right of the image is to the robot's right and reaching it
    means DECREASING pan. Tilt is inverted for the same kind of reason — the
    firmware already flips the tilt pulse for a reversed mount, and the tracker
    sits on top of that, so raising your head must LOWER the tilt number.
    Verified on the robot: with tilt_inverted=False it chased the wrong way and
    ran into TILT_MAX.
    """
    err_x, err_y = centring_error(face)
    dpan = _step(err_x, GAIN_PAN) * (-1 if pan_inverted else 1)
    dtilt = _step(err_y, GAIN_TILT) * (-1 if tilt_inverted else 1)
    return (
        max(PAN_MIN, min(PAN_MAX, pan + dpan)),
        max(TILT_MIN, min(TILT_MAX, tilt + dtilt)),
    )


def is_centred(face: Face) -> bool:
    """True when the face is close enough that the neck should hold still."""
    err_x, err_y = centring_error(face)
    return abs(err_x) < DEADZONE and abs(err_y) < DEADZONE
