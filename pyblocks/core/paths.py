"""User-owned libraries are independent of programs and installation paths."""

from platformdirs import user_data_path


def personal_collection():
    directory = user_data_path("pyblocks-studio", appauthor=False)
    if not directory.is_absolute():
        raise ValueError("The user data directory must be an absolute path")
    return (directory / "blocks").resolve()
