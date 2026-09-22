"""gettext catalogs shared by frontends; source messages are kept in Russian."""

import gettext
import json
from importlib.resources import files

LANGUAGES = json.loads(
    (files("pyblocks") / "locale/languages.json").read_text(encoding="utf-8")
)
_language = "ru"
_translation = gettext.NullTranslations()


def language():
    return _language


def set_language(code):
    global _language, _translation
    if code not in LANGUAGES:
        raise ValueError(f"Unknown language: {code}")
    _translation = gettext.translation(
        "pyblocks",
        localedir=str(files("pyblocks") / "locale"),
        languages=[code],
        fallback=code == "ru",
    )
    _language = code


def tr(message, **values):
    text = _translation.gettext(message)
    return text.format(**values) if values else text
