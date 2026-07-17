"""Compatibility proxies for application-owned services.

New code should access ``current_app.extensions['yacht_services']`` through
``get_services``. The proxies keep existing scripts and tests source-compatible.
"""

from flask import current_app, has_app_context
from werkzeug.local import LocalProxy

from yacht_app.container import AppServices, create_services

_default_services: AppServices | None = None


def get_default_services() -> AppServices:
    global _default_services
    if _default_services is None:
        _default_services = create_services()
    return _default_services


def set_default_services(services: AppServices) -> None:
    global _default_services
    _default_services = services


def get_services() -> AppServices:
    if has_app_context():
        services = current_app.extensions.get("yacht_services")
        if services is not None:
            return services
    return get_default_services()


room_store = LocalProxy(lambda: get_services().room_store)
rooms = LocalProxy(lambda: get_services().rooms)
presence_store = LocalProxy(lambda: get_services().presence_store)
lobby_clients = LocalProxy(lambda: get_services().presence)
single_sessions = LocalProxy(lambda: get_services().single_sessions)
single_sessions_lock = LocalProxy(lambda: get_services().single_sessions_lock)
ai_metrics = LocalProxy(lambda: get_services().ai_metrics)
