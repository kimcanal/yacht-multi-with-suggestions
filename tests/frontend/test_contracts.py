import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class FrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_css = (ROOT / "static/css/base.css").read_text(encoding="utf-8")
        cls.intro_template = (ROOT / "templates/intro.html").read_text(encoding="utf-8")
        cls.single_template = (ROOT / "templates/single-game.html").read_text(encoding="utf-8")
        cls.single_table_template = (ROOT / "templates/single-game-table.html").read_text(encoding="utf-8")
        cls.multi_template = (ROOT / "templates/multi-game.html").read_text(encoding="utf-8")
        cls.multi_table_template = (ROOT / "templates/multi-game-table.html").read_text(encoding="utf-8")
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
        cls.ai_panel = (ROOT / "static/js/ai_panel.js").read_text(encoding="utf-8")
        cls.winprob = (ROOT / "static/js/winprob.js").read_text(encoding="utf-8")
        cls.yacht_game = (ROOT / "static/js/yacht_game.js").read_text(encoding="utf-8")
        cls.game_layout = (ROOT / "static/js/game_layout.js").read_text(encoding="utf-8")
        cls.table_layout_css = (ROOT / "static/css/pages/multi-game-table.css").read_text(encoding="utf-8")
        cls.single_table_layout_css = (ROOT / "static/css/pages/single-game-table.css").read_text(encoding="utf-8")

    def test_page_templates_use_base_and_external_assets(self):
        for template in (
            self.intro_template,
            self.single_template,
            self.single_table_template,
            self.multi_template,
            self.multi_table_template,
        ):
            self.assertIn('{% extends "base.html" %}', template)
            self.assertNotIn('<style>', template)
            self.assertNotRegex(template, r'<script(?![^>]*src=)[^>]*>')

    def test_local_static_assets_use_versioned_urls(self):
        for template in (
            self.intro_template,
            self.single_template,
            self.single_table_template,
            self.multi_template,
            self.multi_table_template,
        ):
            for line in template.splitlines():
                if "url_for('static'" in line:
                    self.assertIn(', v=', line)

    def test_intro_guide_covers_turns_scoring_ai_and_multiplayer_features(self):
        self.assertIn('id="turn-flow"', self.intro_template)
        self.assertIn('id="scoring"', self.intro_template)
        self.assertIn('id="first-game"', self.intro_template)
        self.assertIn('id="ai-guide"', self.intro_template)
        self.assertIn('id="multiplayer-guide"', self.intro_template)
        self.assertIn('상단 합계가 63 이상이면 Upper Bonus +35', self.intro_template)
        self.assertIn('조건을 못 맞춘 칸도 기록할 수 있지만 그 칸은 0점으로 닫힙니다.', self.intro_template)
        self.assertIn('최적 판단 모드', self.intro_template)
        self.assertIn('추천은 자동으로 플레이하지 않습니다.', self.intro_template)
        self.assertIn('👍·🔥·😂·😱·🎲·👏', self.intro_template)

    def test_2d_dice_and_unrolled_placeholder_are_shared(self):
        self.assertIn("@keyframes roll2d", self.base_css)
        self.assertIn('.die[data-value="6"] .face-6', self.base_css)
        self.assertNotIn("@keyframes roll3d", self.base_css)
        self.assertIn(".die-container.dice-unrolled::after", self.base_css)
        self.assertNotIn("@keyframes roll3d", self.single)
        self.assertNotIn("@keyframes roll3d", self.multi)
        self.assertIn("rollsLeft === 3 && !isRolling", self.single)
        self.assertIn("rollsLeft === 3 && !isRolling", self.multi)
        self.assertIn(".die-container.dice-unrolled::after", self.base_css)
        self.assertIn("background: linear-gradient(135deg, #ffffff, #dbe6ea);", self.base_css)

    def test_roll_sound_uses_one_resumable_shared_audio_context(self):
        self.assertIn("let gameAudioContext = null;", self.yacht_game)
        self.assertIn("function playDiceRollSound()", self.yacht_game)
        self.assertIn("ctx.resume().then(safelyPlay)", self.yacht_game)
        self.assertIn("playDiceRollSound();", self.single)
        self.assertIn("playDiceRollSound();", self.multi)
        self.assertIn("function playScoreSelectSound()", self.yacht_game)
        self.assertIn("playScoreSelectSound();", self.single)
        self.assertIn("playScoreSelectSound();", self.multi)
        self.assertIn("function playTurnToastSound() {\n    withGameAudio", self.yacht_game)
        self.assertIn("noiseGain.gain.setValueAtTime(0.2, now);", self.yacht_game)
        self.assertIn("osc.frequency.setValueAtTime(880, now);", self.yacht_game)

    def test_dice_roll_cycles_faces_before_landing_on_the_server_result(self):
        self.assertIn("function startDiceRollAnimation", self.yacht_game)
        self.assertIn("function stopDiceRollAnimation", self.yacht_game)
        self.assertIn("nextRollingFace", self.yacht_game)
        self.assertIn("startDiceRollAnimation(keptForRoll);", self.single)
        self.assertIn("startDiceRollAnimation(keptForRoll);", self.multi)
        self.assertIn("stopDiceRollAnimation();", self.single)
        self.assertIn("stopDiceRollAnimation();", self.multi)
        self.assertIn("@keyframes diceLand", self.base_css)

    def test_current_score_top_three_sits_between_dice_and_roll(self):
        for template in (self.single_template, self.single_table_template, self.multi_template, self.multi_table_template):
            dice_grid = template.index('id="dice-grid"')
            quick_targets = template.index('id="quick-score-targets"')
            roll_button = template.index('id="roll-btn"')
            self.assertLess(dice_grid, quick_targets)
            self.assertLess(quick_targets, roll_button)
        self.assertIn("function updateQuickScoreTargets", self.score_utils)
        self.assertIn("현재 점수 TOP 3", self.score_utils)
        self.assertIn("@media (max-width: 1024px)", self.base_css)
        self.assertIn(".quick-score-targets { display: none !important; }", self.base_css)

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

    def test_roll_uses_a_snapshot_of_the_keep_mask(self):
        self.assertIn("const keptForRoll = [...kept];", self.single)
        self.assertIn("const keptForRoll = [...kept];", self.multi)
        self.assertIn("kept: keptForRoll", self.single)
        self.assertIn("kept: keptForRoll", self.multi)

    def test_alternate_table_layout_keeps_the_same_game_contract(self):
        self.assertIn('class="table-game-shell"', self.multi_table_template)
        self.assertIn('id="dice-grid"', self.multi_table_template)
        self.assertIn('id="scorecard"', self.multi_table_template)
        self.assertIn('id="ai-breakdown"', self.multi_table_template)
        self.assertIn("css/pages/multi-game-table.css", self.multi_table_template)
        self.assertIn("js/pages/multi-game.js", self.multi_table_template)

    def test_desktop_defaults_to_table_while_mobile_keeps_the_original_layout(self):
        self.assertIn("js/game_layout.js", self.multi_template)
        self.assertIn("js/game_layout.js", self.single_template)
        self.assertIn("(min-width: 1025px)", self.game_layout)
        self.assertNotIn("layout=classic", self.game_layout)
        self.assertIn("window.location.replace", self.game_layout)

    def test_table_panels_reserve_scrollbar_space_for_text_updates(self):
        self.assertIn("height: calc(100dvh - 28px)", self.table_layout_css)
        self.assertIn("grid-template-rows: minmax(0, 1fr)", self.table_layout_css)
        self.assertIn("overflow-y: scroll", self.table_layout_css)
        self.assertIn("scrollbar-gutter: stable", self.table_layout_css)
        self.assertIn("transform: translateY(clamp(16px, 3vh, 36px));", self.table_layout_css)

    def test_single_table_layout_keeps_ranked_session_and_game_controls(self):
        self.assertIn('class="table-game-shell single-table-game-shell"', self.single_table_template)
        for element_id in ("dice-grid", "scorecard", "save-modal", "mode-strip", "ai-breakdown"):
            self.assertIn(f'id="{element_id}"', self.single_table_template)
        self.assertIn("css/pages/single-game-table.css", self.single_table_template)
        self.assertIn("js/pages/single-game.js", self.single_table_template)

    def test_vs_ai_table_scorecard_prioritizes_all_score_rows(self):
        self.assertIn(".scorecard-mode-compare .compare-board", self.single_table_layout_css)
        self.assertIn(":has(#scorecard.scorecard-mode-compare) .score-help", self.single_table_layout_css)
        self.assertIn(".scorecard-mode-compare .score-duel-overview", self.single_table_layout_css)
        self.assertIn(".score-duel-overview {\n        display: none;", self.single_table_layout_css)
        self.assertIn("grid-template-columns: minmax(100px, 1.12fr)", self.single_table_layout_css)
        self.assertIn("grid-template-rows: auto repeat(6, minmax(0, 1fr)) auto auto", self.single_table_layout_css)
        self.assertIn("isTableLayout ? '나' : `나 (${username})`", self.single)
        self.assertIn("+0 (", self.score_utils)
        self.assertIn("renderCompareStatRow('상단 합계'", self.score_utils)
        self.assertIn("renderCompareStatRow('보너스'", self.score_utils)
        self.assertIn("function renderSoloTableBoard", self.score_utils)
        self.assertIn("상단 합계", self.score_utils)
        self.assertIn("renderSoloTableBoard(myCard, { interactive: true })", self.single)
        self.assertIn("#scorecard.table-solo-scorecard .solo-table-board", self.single_table_layout_css)
        self.assertNotIn("renderCompactSingleCard(myCard", self.single)
        self.assertNotIn("Upper Section</span>", self.score_utils)
        self.assertNotIn("Lower Section</span>", self.score_utils)
        self.assertNotIn("Endgame V", self.single)
        self.assertNotIn("exact V(next_state)", self.single)
        self.assertIn("예상 최종 점수", self.ai_panel)
        self.assertNotIn("? '기대 최종점수'", self.ai_panel)
        self.assertIn("지금 기록 vs 재굴림", self.ai_panel)
        self.assertIn("AI 판단 기준", self.ai_panel)
        self.assertIn("positionScoreTooltip(el, tip", self.score_utils)
        self.assertIn("function getScorePreviewOnlyHandlers", self.score_utils)
        self.assertIn('class="compare-cat-cell tip-trigger"', self.score_utils)
        self.assertNotIn("const scoreMetaAttrs = clickable", self.score_utils)
        self.assertIn("help.hidden = true;", self.score_utils)
        self.assertIn(".score-help[hidden]", self.base_css)

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
        self.assertIn("이대로 진행하면 예상되는 최종 점수", self.winprob)
        self.assertIn("현재 주사위와 남은 굴림까지 반영", self.winprob)
        self.assertNotIn("점수판 EV", self.winprob)
        self.assertIn("한 족보의 완성과 상단 보너스 흐름을 우선 고려", self.multi)
        self.assertIn("여러 하단 족보의 성공 가능성을 함께 보존", self.multi)
        self.assertIn("남은 점수판 가치까지 반영한 기대점수 기준", self.multi)
        self.assertNotIn("최적 정책보다 게임당 기대점수", self.multi)

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

    def test_ai_panel_renders_a_human_readable_target_probability(self):
        self.assertIn('function renderProbabilityContext(context)', self.ai_panel)
        self.assertIn('report.probability_context', self.ai_panel)
        self.assertIn('ai-probability-basis', self.ai_panel)

    def test_all_keep_recommendation_is_treated_as_a_score_hint_not_five_keep_badges(self):
        self.assertIn("if (!options.enabled || !aiRec || aiRec.stage === 'score') return;", self.yacht_game)
        self.assertIn("if (aiRec.stage === 'score') return true;", self.yacht_game)

    def test_ai_panel_compares_reroll_with_record_now(self):
        self.assertIn('function renderActionComparison(comparison)', self.ai_panel)
        self.assertIn('renderActionComparison(aiRec.action_comparison)', self.ai_panel)

    def test_ai_score_hint_uses_actual_zero_score_for_sacrifice_badge(self):
        self.assertIn("calcScore(dice, categoryIndex)", self.yacht_game)
        self.assertIn("if (targetScore !== null) return targetScore <= 0;", self.yacht_game)
        self.assertNotIn(".includes('0점')", self.yacht_game)
        self.assertNotIn("targetRow.type === 'sacrifice' ||", self.yacht_game)

    def test_single_mode_strip_does_not_render_stale_coach_summary_copy(self):
        self.assertIn('class="mode-config-grid"', self.single)
        self.assertNotIn('id="mode-strip-toggle"', self.single)
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
        self.assertNotIn('최적 정책보다 게임당 기대점수 10.4점 낮음', self.single)

    def test_single_settings_strip_is_always_visible(self):
        self.assertIn('.mode-config-grid {\n            display:flex;', self.single)
        self.assertNotIn('.mode-strip.expanded .mode-config-grid', self.single)
        self.assertNotIn('MODE_STRIP_EXPANDED_KEY', self.single)
        self.assertNotIn('toggleModeStrip', self.single)
        self.assertNotIn('function isCompactModeViewport()', self.single)
        self.assertNotIn("window.addEventListener('resize', updateModeStripUI)", self.single)

    def test_single_score_help_sits_at_the_top_of_the_scorecard(self):
        self.assertIn('class="single-insight-grid"', self.single)
        self.assertIn('.single-insight-grid {\n            display: block;', self.single)
        self.assertIn('id="score-desc-area" class="ai-breakdown score-help"', self.single)
        insight_index = self.single.index('class="single-insight-grid"')
        help_index = self.single.index('id="score-desc-area"')
        scorecard_area_index = self.single.index('<div class="scorecard-area">')
        scorecard_index = self.single.index('id="scorecard"')
        self.assertLess(insight_index, scorecard_area_index)
        self.assertLess(scorecard_area_index, help_index)
        self.assertLess(scorecard_area_index, scorecard_index)
        self.assertLess(help_index, scorecard_index)

    def test_game_status_bar_does_not_wrap_dice_or_ai_panels(self):
        for page in (self.single_template, self.multi_template):
            info_start = page.index('<div class="info-bar">')
            info_end = page.index('                </div>\n                <div class="dice-grid"', info_start)
            dice_grid = page.index('<div class="dice-grid"', info_start)
            ai_panel = page.index('id="ai-breakdown"', info_start)
            self.assertLess(info_end, dice_grid)
            self.assertLess(info_end, ai_panel)

    def test_roll_control_follows_the_dice_grid_on_both_game_pages(self):
        for page in (self.single_template, self.multi_template):
            dice_grid = page.index('<div class="dice-grid"')
            roll_action = page.index('class="dice-action-row"')
            roll_button = page.index('id="roll-btn"', roll_action)
            self.assertLess(dice_grid, roll_action)
            self.assertLess(roll_action, roll_button)

    def test_scorecard_marks_ready_pending_and_locked_rows(self):
        self.assertIn("'filled score-locked'", self.score_utils)
        self.assertIn("'clickable score-ready'", self.score_utils)
        self.assertIn("'score-pending'", self.score_utils)
        self.assertIn('.compare-value-cell.score-ready', self.base_css)
        self.assertIn('.compare-value-cell.score-locked', self.base_css)

    def test_single_desktop_scorecard_uses_full_height_without_a_fixed_offset(self):
        self.assertIn('height: 100%;', self.single)
        self.assertIn('margin-top: 0;', self.single)
        self.assertNotIn('margin-top: 164px;', self.single)

    def test_single_solo_layout_stacks_below_desktop_breakpoint(self):
        responsive_rule = (
            'body.solo-play-mode .game-wrapper { grid-template-columns: minmax(0, 1fr); }'
        )
        self.assertIn(responsive_rule, self.single)

    def test_single_timer_restores_its_countdown_after_an_expiry_notice(self):
        self.assertIn('function restoreTimerCountdown()', self.single)
        self.assertIn("timerBar.innerHTML = '⏳<span id=\"timer-count\">30</span>초 남았습니다';", self.single)
        self.assertIn('restoreTimerCountdown();', self.single)


if __name__ == "__main__":
    unittest.main()
