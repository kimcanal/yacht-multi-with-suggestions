from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_css = (ROOT / "static/css/base.css").read_text(encoding="utf-8")
        cls.single = (ROOT / "templates/single-game.html").read_text(encoding="utf-8")
        cls.multi = (ROOT / "templates/multi-game.html").read_text(encoding="utf-8")
        cls.winprob = (ROOT / "static/js/winprob.js").read_text(encoding="utf-8")

    def test_mobile_dice_animation_and_unrolled_placeholder_are_shared(self):
        self.assertIn("@keyframes roll3dMobile", self.base_css)
        self.assertIn("scale(0.72)", self.base_css)
        self.assertIn(".die-container.dice-unrolled::after", self.base_css)
        self.assertNotIn("@keyframes roll3d", self.single)
        self.assertNotIn("@keyframes roll3d", self.multi)
        self.assertIn("rollsLeft === 3 && !isRolling", self.single)
        self.assertIn("rollsLeft === 3 && !isRolling", self.multi)

    def test_multiplayer_uses_header_auth_and_sse_fallback(self):
        self.assertIn("'X-Player-Token': playerToken", self.multi)
        self.assertNotIn("qs.set('pt'", self.multi)
        self.assertIn("new EventSource", self.multi)
        self.assertIn("startSyncPolling({immediate: true})", self.multi)

    def test_win_probability_uses_server_endpoint_and_current_metric(self):
        self.assertIn("/api/win-probability", self.winprob)
        self.assertNotIn("CATEGORY_BASELINES", self.winprob)
        self.assertIn("최적 대비 평균 -10.4점", self.single)
        self.assertIn("최적 대비 평균 -10.4점", self.multi)

    def test_recommendation_errors_prefer_user_facing_server_message(self):
        expected = "payload.message || payload.error || 'AI 추천 요청 실패'"
        self.assertIn(expected, self.single)
        self.assertIn(expected, self.multi)


if __name__ == "__main__":
    unittest.main()
