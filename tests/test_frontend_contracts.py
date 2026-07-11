from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_css = (ROOT / "static/css/base.css").read_text(encoding="utf-8")
        cls.single = (ROOT / "templates/single-game.html").read_text(encoding="utf-8")
        cls.multi = (ROOT / "templates/multi-game.html").read_text(encoding="utf-8")
        cls.score_utils = (ROOT / "static/js/score_utils.js").read_text(encoding="utf-8")
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
        self.assertIn("source.addEventListener('reaction'", self.multi)
        self.assertIn("qs.set('reaction_id', lastReactionId)", self.multi)
        self.assertIn("/api/rooms/${roomCode}/reaction", self.multi)
        self.assertIn("playReactionSound(reaction.code)", self.multi)
        self.assertIn("assets/openmoji/1F602.svg", self.multi)
        self.assertIn("emoji.src = reaction.asset", self.multi)
        self.assertNotIn("/api/rooms/${roomCode}/chat", self.multi)
        self.assertIn("startSyncPolling({immediate: true})", self.multi)

    def test_multiplayer_reactions_vendor_openmoji_assets_and_license(self):
        asset_dir = ROOT / "static/assets/openmoji"
        for filename in ("1F44D.svg", "1F525.svg", "1F602.svg", "1F631.svg", "1F3B2.svg", "1F44F.svg"):
            svg = (asset_dir / filename).read_text(encoding="utf-8")
            self.assertIn('<svg id="emoji"', svg)
        license_text = (asset_dir / "LICENSE.txt").read_text(encoding="utf-8")
        self.assertIn("Creative Commons Attribution-ShareAlike 4.0", license_text)

    def test_win_probability_uses_server_endpoint_and_current_metric(self):
        self.assertIn("/api/win-probability", self.winprob)
        self.assertNotIn("CATEGORY_BASELINES", self.winprob)
        self.assertIn("const FAST_SAMPLES = 30", self.winprob)
        self.assertIn("const REFINED_SAMPLES = 100", self.winprob)
        self.assertIn("REFINED_SAMPLES}회 정밀 계산 중", self.winprob)
        self.assertIn("최적 대비 평균 -10.4점", self.single)
        self.assertIn("최적 대비 평균 -10.4점", self.multi)

    def test_recommendation_errors_prefer_user_facing_server_message(self):
        expected = "payload.message || payload.error || 'AI 추천 요청 실패'"
        self.assertIn(expected, self.single)
        self.assertIn(expected, self.multi)

    def test_upper_bonus_is_explained_once_in_the_overview(self):
        self.assertIn("상단 합계 63점 달성 시 +35점", self.score_utils)
        self.assertIn("+${totals.bonus} 확보", self.score_utils)
        self.assertNotIn("score-item subtotal", self.score_utils)
        self.assertNotIn("renderCompareStatRow('Subtotal'", self.score_utils)


if __name__ == "__main__":
    unittest.main()
