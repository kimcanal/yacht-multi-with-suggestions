"""Yacht web application package."""


def create_app(*args, **kwargs):
    from .factory import create_app as build_app

    return build_app(*args, **kwargs)


__all__ = ["create_app"]
