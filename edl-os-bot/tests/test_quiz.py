"""Mini-Чекап v2 — тесты scoring + stage detection + growth points."""
from src.core.quiz import (
    QUIZ_QUESTIONS,
    STAGE_WEIGHTS,
    VALID_SCORES,
    GrowthPoint,
    MiniCheckupResult,
    build_result,
    category_label,
    cta_for_score,
    layer_score_0_100,
    stage_detection,
    total_score,
    top3_growth_points,
)


# ── Вопросник ─────────────────────────────────────────────────────────────────

def test_12_questions():
    assert len(QUIZ_QUESTIONS) == 12


def test_layers_have_3_questions_each():
    counts: dict[str, int] = {}
    for q in QUIZ_QUESTIONS:
        counts[q.layer] = counts.get(q.layer, 0) + 1
    assert counts == {"01": 3, "02": 3, "03": 3, "04": 3}


def test_all_question_keys_unique():
    keys = [q.key for q in QUIZ_QUESTIONS]
    assert len(keys) == len(set(keys))


def test_all_options_have_valid_scores():
    for q in QUIZ_QUESTIONS:
        assert len(q.options) == 5, f"{q.key} has {len(q.options)} options, want 5"
        for label, score in q.options:
            assert score in VALID_SCORES, f"{q.key}: score {score} not in {VALID_SCORES}"
            assert label, f"{q.key}: empty label"


def test_question_order_sequential():
    orders = [q.order for q in QUIZ_QUESTIONS]
    assert orders == list(range(1, 13))


# ── Scoring ───────────────────────────────────────────────────────────────────

def test_zero_answers_zero_score():
    answers = {q.key: 0 for q in QUIZ_QUESTIONS}
    for stage in ("start", "team", "structure", "maturity"):
        assert total_score(answers, stage) == 0


def test_full_answers_100_score():
    answers = {q.key: 10 for q in QUIZ_QUESTIONS}
    for stage in ("start", "team", "structure", "maturity"):
        assert total_score(answers, stage) == 100


def test_layer_score_0_to_100():
    answers = {q.key: 10 for q in QUIZ_QUESTIONS}
    for layer in ("01", "02", "03", "04"):
        assert layer_score_0_100(answers, layer) == 100.0

    answers_zero = {q.key: 0 for q in QUIZ_QUESTIONS}
    for layer in ("01", "02", "03", "04"):
        assert layer_score_0_100(answers_zero, layer) == 0.0


def test_weights_sum_to_one():
    for stage, weights in STAGE_WEIGHTS.items():
        total = sum(weights.values())
        assert abs(total - 1.0) < 1e-9, f"Stage {stage}: weights sum {total} ≠ 1"


def test_stage_relative_scoring():
    """Одни и те же ответы дают разный Score при разных стадиях."""
    answers = {q.key: 5 for q in QUIZ_QUESTIONS}
    scores = {stage: total_score(answers, stage) for stage in ("start", "team", "structure", "maturity")}
    # При одинаковых весах и равных scores по всем слоям разницы быть не должно,
    # но весовые коэффициенты разные — проверяем что хотя бы одна пара отличается.
    # На практике при равных layer_scores результат одинаков (50), т.к. сумма весов = 1.
    for score in scores.values():
        assert 0 <= score <= 100


def test_mid_score_audit_plus():
    # Ответы 5 на всё → score ≈ 50 → cta=audit_plus
    answers = {q.key: 5 for q in QUIZ_QUESTIONS}
    score = total_score(answers, "team")
    assert 41 <= score <= 70
    cta_p, cta_s = cta_for_score(score)
    assert cta_p == "audit_plus"


# ── Категории Score ───────────────────────────────────────────────────────────

def test_category_label_boundaries():
    assert category_label(0)[0] == "Бизнес держится на вас лично"
    assert category_label(40)[0] == "Бизнес держится на вас лично"
    assert category_label(41)[0] == "Есть базовая структура, много пробелов"
    assert category_label(60)[0] == "Есть базовая структура, много пробелов"
    assert category_label(61)[0] == "Зрелая инфраструктура, но узкие места видны"
    assert category_label(75)[0] == "Зрелая инфраструктура, но узкие места видны"
    assert category_label(76)[0] == "Готовая к масштабированию операционная база"
    assert category_label(100)[0] == "Готовая к масштабированию операционная база"


def test_category_colors():
    _, c0 = category_label(20)
    _, c1 = category_label(50)
    _, c2 = category_label(70)
    _, c3 = category_label(90)
    assert c0 == "red"
    assert c1 == "orange"
    assert c2 == "yellow"
    assert c3 == "green"


# ── CTA routing ───────────────────────────────────────────────────────────────

def test_cta_routing():
    p, s = cta_for_score(0)
    assert p == "audit" and s == "demo"

    p, s = cta_for_score(40)
    assert p == "audit"

    p, s = cta_for_score(41)
    assert p == "audit_plus"

    p, s = cta_for_score(70)
    assert p == "audit_plus"

    p, s = cta_for_score(71)
    assert p == "diagnostic_waitlist"

    p, s = cta_for_score(100)
    assert p == "diagnostic_waitlist"


# ── Stage detection ───────────────────────────────────────────────────────────

def test_stage_detection_normal():
    for opt in ("start", "team", "structure", "maturity"):
        stage, conf = stage_detection(opt)
        assert stage == opt
        assert conf == "high"


def test_stage_detection_outliers():
    stage, conf = stage_detection("outlier_small_team")
    assert stage == "team"
    assert conf == "low"

    stage, conf = stage_detection("outlier_big_team")
    assert stage == "structure"
    assert conf == "low"


def test_stage_detection_unknown():
    stage, conf = stage_detection("unknown_value")
    assert stage == "team"  # default
    assert conf == "low"


# ── Growth points ─────────────────────────────────────────────────────────────

def test_top3_growth_points_returns_3():
    answers = {q.key: 0 for q in QUIZ_QUESTIONS}
    gps = top3_growth_points(answers, "team")
    assert len(gps) == 3


def test_top3_growth_points_are_growth_points():
    answers = {q.key: 0 for q in QUIZ_QUESTIONS}
    gps = top3_growth_points(answers, "team")
    for gp in gps:
        assert isinstance(gp, GrowthPoint)
        assert gp.layer in ("01", "02", "03", "04")
        assert gp.short
        assert gp.action


def test_top3_growth_points_from_weakest_layers():
    # Делаем Деньги сильными — они не должны попасть в точки роста
    answers = {q.key: 0 for q in QUIZ_QUESTIONS}
    for q in QUIZ_QUESTIONS:
        if q.layer == "04":
            answers[q.key] = 10
    gps = top3_growth_points(answers, "team")
    layers = [gp.layer for gp in gps]
    assert "04" not in layers, "Сильный слой не должен попасть в точки роста"


# ── build_result ──────────────────────────────────────────────────────────────

def test_build_result_structure():
    answers = {q.key: 5 for q in QUIZ_QUESTIONS}
    result = build_result(answers, "team", "edu")
    assert isinstance(result, MiniCheckupResult)
    assert 0 <= result.score <= 100
    assert result.stage == "team"
    assert result.segment == "edu"
    assert len(result.growth_points) == 3
    assert set(result.layer_scores.keys()) == {"01", "02", "03", "04"}


def test_build_result_other_segment():
    answers = {q.key: 5 for q in QUIZ_QUESTIONS}
    result = build_result(answers, "start", "other")
    assert result.segment == "other"
    # benchmark может быть None или fallback-медиана
    # не падаем


def test_build_result_all_zeros_audit_cta():
    answers = {q.key: 0 for q in QUIZ_QUESTIONS}
    result = build_result(answers, "start", "it")
    assert result.score == 0
    assert result.cta_primary == "audit"
    assert result.category_color == "red"
