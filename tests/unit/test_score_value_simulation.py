import random
import unittest

from yacht_core.simulation import indexed_die, initial_dice, reroll_from_keep


class ScoreValueSimulationRandomSourceTests(unittest.TestCase):
    def test_indexed_die_is_stable_and_bounded(self):
        first = indexed_die(20260708, 3, 2, 4)
        second = indexed_die(20260708, 3, 2, 4)

        self.assertEqual(first, second)
        self.assertGreaterEqual(first, 1)
        self.assertLessEqual(first, 6)

    def test_indexed_initial_dice_does_not_consume_stream_rng(self):
        rng = random.Random(17)
        before = rng.random()
        dice = initial_dice(rng, 20260708, 5, "indexed")
        after = rng.random()

        control = random.Random(17)
        self.assertEqual(before, control.random())
        self.assertEqual(after, control.random())
        self.assertEqual(len(dice), 5)
        self.assertTrue(all(1 <= value <= 6 for value in dice))

    def test_indexed_reroll_preserves_kept_dice(self):
        rng = random.Random(99)
        dice = [1, 2, 3, 4, 5]

        rerolled = reroll_from_keep(
            rng,
            dice,
            [1, 3],
            seed=20260708,
            turn_index=2,
            roll_step=1,
            random_source="indexed",
        )

        self.assertEqual(rerolled[1], 2)
        self.assertEqual(rerolled[3], 4)
        self.assertNotEqual(rerolled, dice)
        self.assertTrue(all(1 <= value <= 6 for value in rerolled))


if __name__ == "__main__":
    unittest.main()
