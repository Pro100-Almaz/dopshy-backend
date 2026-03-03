import enum


class Role(str, enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    CLIENT = "client"
