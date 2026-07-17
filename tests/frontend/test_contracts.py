import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class FrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_css = (ROOT / "static/css/base.css").read_text(encoding="utf-8")
        cls.single_template = (ROOT / "templates/single-game.html").read_text(encoding="utf-8")
        cls.multi_template = (ROOT / "templates/multi-game.html").read_text(encoding="utf-8")
        cls.single = "\n".join((
            cls.single_template,
            (ROOT / "static/css/pages/single-game.css").read_text(encoding="utf-8"),
            (ROOT / "static/js/pages/single-game.js").read_text(encoding="utf-8"),
        ))
        cls.multi = "\n".join((
            cls.multi_template,
            (ROOT / "static/css/pages/multi-game.css").read_text(encoding="utf-8"),
            (ROOT / "static/js/pages/multi-game.js").read_text(encoding="utf-8"),
        ))
        cls.score_utils = (ROOT / "static/js/score_utils.js").read_text(encoding="utf-8")
        cls.winprob = (ROOT / "static/js/winprob.js").read_text(encoding="utf-8")
        cls.yacht_game = (ROOT / "static/js/yacht_game.js").read_text(encoding="utf-8")

    def test_page_templates_use_base_and_external_assets(self):
        for template in (self.single_template, self.multi_template):
            self.assertIn('{% extends "base.html" %}', template)
            self.assertNotIn('<style>', template)
            self.assertNotRegex(template, r'<script(?![^>]*src=)[^>]*>')

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
        filenames = ("1F44D.svg", "1F525.svg", "1F602.svg", "1F631.svg", "1F3B2.svg", "1F44F.svg")
        for filename in filenames:
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
        self.assertIn("최적 대비 평균 -10.4점", self.multi)

    def test_upper_bonus_is_explained_once_in_the_overview(self):
        self.assertIn("상단 합계 63점 달성 시 +35점", self.score_utils)
        self.assertIn("Upper 총합 63점 이상이면 보너스 35점을 받습니다.", self.score_utils)
        self.assertIn("desc: getUpperHelp(totals)", self.score_utils)
        self.assertIn("desc: getUpperHelp(leftTotals, rightTotals)", self.score_utils)
        self.assertIn('tabindex="0" data-desc=', self.score_utils)
        self.assertIn("+${totals.bonus} 확보", self.score_utils)
        self.assertNotIn("score-item subtotal", self.score_utils)
        self.assertNotIn("renderCompareStatRow('Subtotal'", self.score_utils)

    def test_recommendation_errors_prefer_user_facing_server_message(self):
        expected = "payload.message || payload.error || 'AI 추천 요청 실패'"
        self.assertIn(expected, self.single)
        self.assertIn(expected, self.multi)

    def test_ai_score_hint_uses_actual_zero_score_for_sacrifice_badge(self):
        self.assertIn("calcScore(dice, categoryIndex)", self.yacht_game)
        self.assertIn("if (targetScore !== null) return targetScore <= 0;", self.yacht_game)
        self.assertNotIn(".includes('0점')", self.yacht_game)
        self.assertNotIn("targetRow.type === 'sacrifice' ||", self.yacht_game)

    def test_single_mode_strip_does_not_render_stale_coach_summary_copy(self):
        self.assertIn('id="mode-strip-toggle"', self.single)
        self.assertNotIn('id="mode-summary"', self.single)
        self.assertNotIn('id="coach-note"', self.single)
        self.assertNotIn('솔로 기록 모드입니다', self.single)
        self.assertNotIn('현재는 ${getAiModeDisplayName()} 기준으로 조언', self.single)

    def test_single_ai_mode_uses_compact_buttons_instead_of_explanation_cards(self):
        self.assertIn('class="ai-mode-row"', self.single)
        self.assertIn('data-ai-mode="focused"', self.single)
        self.assertIn('data-ai-mode="cover"', self.single)
        self.assertIn('data-ai-mode="optimal"', self.single)
        self.assertNotIn('class="ai-mode-card"', self.single)
        self.assertNotIn('최적 대비 평균 -10.4점', self.single)

    def test_single_settings_strip_is_collapsed_by_default_on_all_viewports(self):
        self.assertIn('.mode-config-grid {\n            display:none;', self.single)
        self.assertIn('.mode-strip.expanded .mode-config-grid { display:flex; }', self.single)
        self.assertIn("const MODE_STRIP_EXPANDED_KEY = 'yacht_mode_strip_expanded_v2';", self.single)
        self.assertIn("toggleBtn.textContent = expanded ? '설정 접기' : '설정';", self.single)
        self.assertNotIn('function isCompactModeViewport()', self.single)
        self.assertNotIn("window.addEventListener('resize', updateModeStripUI)", self.single)

    def test_single_score_help_sits_with_dice_insights_not_above_scorecard(self):
        self.assertIn('class="single-insight-grid"', self.single)
        self.assertIn('id="score-desc-area" class="ai-breakdown score-help"', self.single)
        insight_index = self.single.index('class="single-insight-grid"')
        help_index = self.single.index('id="score-desc-area"')
        scorecard_area_index = self.single.index('<div class="scorecard-area">')
        scorecard_index = self.single.index('id="scorecard"')
        self.assertLess(insight_index, help_index)
        self.assertLess(help_index, scorecard_area_index)
        self.assertLess(scorecard_area_index, scorecard_index)


if __name__ == "__main__":
    unittest.main()
