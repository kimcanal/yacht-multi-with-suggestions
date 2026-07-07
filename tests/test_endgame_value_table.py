import unittest

from scripts.build_value_table import (
    build_exact_endgame_batch_table,
    build_value_table_from_state,
    mask_from_open_arg,
)


class EndgameValueTableTests(unittest.TestCase):
    def test_batch_value_matches_recursive_single_state(self):
        mask = mask_from_open_arg("Yacht")

        _recursive_values, recursive_value = build_value_table_from_state(
            mask,
            start_upper_total=40,
            start_yacht_bonus=False,
            max_exact_open=1,
            max_states=3000,
        )
        batch_values = build_exact_endgame_batch_table(
            max_open_count=1,
            max_states=3000,
        )

        self.assertAlmostEqual(batch_values[(mask, 40, False)], recursive_value, places=6)


if __name__ == "__main__":
    unittest.main()
