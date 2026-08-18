"""Policy helpers used by the exact solver and offline experiments.

Learned-policy modules intentionally are not imported here.  The production
game only needs the exact solver, while offline research can import
``yacht_ai.policies.ml_policy`` directly when its numerical dependencies are
installed.
"""
