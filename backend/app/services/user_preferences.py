"""Per-user UI and accessibility preferences."""

from __future__ import annotations

from copy import deepcopy

from app.models import User

DEFAULT_PREFERENCES: dict = {
    "theme": "midnight",
    "font_size": 100,
    "reduce_motion": False,
    "colorblind_mode": False,
}


def get_user_preferences(user: User) -> dict:
    merged = deepcopy(DEFAULT_PREFERENCES)
    if user.preferences:
        merged.update(user.preferences)
    merged["theme"] = merged.get("theme") or "midnight"
    merged["font_size"] = max(90, min(130, int(merged.get("font_size", 100))))
    merged["reduce_motion"] = bool(merged.get("reduce_motion", False))
    merged["colorblind_mode"] = bool(merged.get("colorblind_mode", False))
    return merged


def apply_user_preferences(user: User, data: dict) -> dict:
    current = get_user_preferences(user)
    if "theme" in data and data["theme"]:
        current["theme"] = str(data["theme"])
    if "font_size" in data and data["font_size"] is not None:
        current["font_size"] = max(90, min(130, int(data["font_size"])))
    if "reduce_motion" in data and data["reduce_motion"] is not None:
        current["reduce_motion"] = bool(data["reduce_motion"])
    if "colorblind_mode" in data and data["colorblind_mode"] is not None:
        current["colorblind_mode"] = bool(data["colorblind_mode"])
    user.preferences = current
    return current
