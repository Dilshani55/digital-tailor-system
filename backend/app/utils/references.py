"""Following stored references safely.

Records point at each other (PDF -> pattern -> session -> user / customer / photo) and any of them can be
deleted on its own, so a reference may name a record that no longer exists. These helpers answer "missing"
instead of raising, so a page never crashes on such a record.
"""
from bson import DBRef
from mongoengine.errors import DoesNotExist


def ref_id(doc, field):
    """The stored id of a reference as text, WITHOUT loading the referenced record. None when not set."""
    ref = doc._data.get(field)
    if ref is None:
        return None
    return str(getattr(ref, "id", ref))


def deref(doc, field):
    """The referenced record, or None when the reference is empty or its record no longer exists."""
    if doc is None:
        return None
    try:
        value = getattr(doc, field, None)
    except DoesNotExist:
        return None
    return None if isinstance(value, DBRef) else value


def pattern_owner_id(pattern):
    """Id (text) of the user who owns a pattern; None when its session or user record is gone."""
    user = deref(deref(pattern, "session_id"), "user_id")
    uid = getattr(user, "id", None)
    return str(uid) if uid is not None else None
