import enum


class Role(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    ARENA_MANAGER = "arena_manager"
    BOXING_MANAGER = "boxing_manager"
    FOOTBALL_MANAGER = "football_manager"
    CLIENT = "client"
