"""gettext catalogs shared by frontends; source messages are written in English."""

import gettext
import json
from importlib.resources import files

LANGUAGES = json.loads(
    (files("little_tinker_rig") / "locale/languages.json").read_text(encoding="utf-8")
)
DEFAULT_LANGUAGE = "en"
_language = DEFAULT_LANGUAGE
_translation = gettext.NullTranslations()


def N_(message):
    """Mark a static caption for extraction; translate when rendering it."""
    return message


def language():
    return _language


def set_language(code):
    global _language, _translation
    if code not in LANGUAGES:
        raise ValueError(f"Unknown language: {code}")
    _translation = gettext.translation(
        "little_tinker_rig",
        localedir=str(files("little_tinker_rig") / "locale"),
        languages=[code],
        fallback=True,
    )
    _language = code


def tr(message, **values):
    text = _translation.gettext(message)
    return text.format(**values) if values else text
