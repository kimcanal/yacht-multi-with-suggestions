import unittest

from app_state import rooms
from yacht_app import create_app
from yacht_app.container import create_services


class AppFactoryTests(unittest.TestCase):
    def test_factory_calls_receive_isolated_mutable_state(self):
        first = create_app({"TESTING": True}, initialize_runtime=False)
        second = create_app({"TESTING": True}, initialize_runtime=False)

        self.assertIsNot(
            first.extensions["yacht_services"],
            second.extensions["yacht_services"],
        )

        with first.app_context():
            rooms["FIRST"] = {"players": ["alpha"]}
            self.assertIn("FIRST", rooms)

        with second.app_context():
            self.assertNotIn("FIRST", rooms)

    def test_factory_uses_explicit_service_container(self):
        services = create_services()
        app = create_app(
            {"TESTING": True},
            services=services,
            initialize_runtime=False,
        )

        self.assertIs(app.extensions["yacht_services"], services)


if __name__ == "__main__":
    unittest.main()
