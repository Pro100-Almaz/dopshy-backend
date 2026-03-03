import enum


class SurfaceType(str, enum.Enum):
    NATURAL_GRASS = "natural_grass"
    ARTIFICIAL_TURF = "artificial_turf"
    FUTSAL = "futsal"


class FieldSize(str, enum.Enum):
    FIVE_V_FIVE = "5v5"
    SEVEN_V_SEVEN = "7v7"
    ELEVEN_V_ELEVEN = "11v11"
