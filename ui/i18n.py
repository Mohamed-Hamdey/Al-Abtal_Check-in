"""
Tiny i18n layer.

We keep all user-visible strings in translations/<lang>.json and look them
up through t("key"). Missing keys return the key itself (so untranslated
strings are visible during development, not silently blank).

The app is Arabic-only for now, so `load("ar")` is called once at startup.
Adding a second language later is just another JSON file and another call
to load() — no screen code changes.
"""

import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from paths import AppPaths
_TRANSLATIONS_DIR = AppPaths.translations_dir()
_strings: dict = {}
_lang: str = "en"


def load(lang: str = "ar") -> None:
    """Load translations for the given language code."""
    global _strings, _lang
    path = os.path.join(_TRANSLATIONS_DIR, f"{lang}.json")
    if not os.path.exists(path):
        _strings = {}
        _lang = lang
        _notify_listeners()
        return
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.pop("_meta", None)
    _strings = data
    _lang = lang
    _notify_listeners()

def current_language() -> str:
    return _lang


def is_rtl() -> bool:
    """True if the current language is right-to-left."""
    return _lang in ("ar", "he", "fa", "ur")


def t(key: str, **kwargs) -> str:
    """
    Look up a translated string by key.
    Supports Python str.format placeholders: t("greeting", name="Ali").
    Missing keys return the key itself, so gaps are visible.
    """
    s = _strings.get(key, key)
    if kwargs:
        try:
            return s.format(**kwargs)
        except Exception:
            return s
    return s

# ---------------------------------------------------------------------------
# Language-change listeners
# ---------------------------------------------------------------------------

_lang_listeners: list = []


def on_language_change(callback) -> None:
    """Register a callback fired after load() switches the language."""
    _lang_listeners.append(callback)


def _notify_listeners() -> None:
    for cb in list(_lang_listeners):
        try:
            cb(_lang)
        except Exception:
            pass