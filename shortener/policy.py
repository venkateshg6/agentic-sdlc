"""Small versioned business policy; the brownfield agent changes this module."""


def is_expired(expires_at, now):
    return expires_at is not None and expires_at <= now
