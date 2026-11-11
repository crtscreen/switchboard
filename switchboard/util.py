import re

def name(value):
    if not re.fullmatch(r"[a-z][a-z0-9_-]{1,19}", value):
        raise ValueError("input error")
    return value

def text(value, limit=500):
    value = value.strip()
    if not value or len(value) > limit:
        raise ValueError(f"use between 1 and {limit} chars")
    if not all(char.isprintable() for char in value):
        raise ValueError("control char not allowed")
    return value