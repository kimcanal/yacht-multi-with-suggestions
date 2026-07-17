"""Development entrypoint and backward-compatible Flask app export."""

import os

from app_state import get_default_services
from yacht_app import create_app

# Keep module-level compatibility proxies and the exported WSGI app on the same
# service container. Direct create_app() callers receive isolated state.
app = create_app(services=get_default_services())


if __name__ == "__main__":
    host = os.getenv("YACHT_HOST", "0.0.0.0")
    port = int(os.getenv("YACHT_PORT", "8080"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    print(f"Yacht Game Server Running on Port {port}...")
    app.run(host=host, port=port, debug=debug)
