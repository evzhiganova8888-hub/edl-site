"""Quiz scoring + рекомендации."""
from src.core.quiz import QUIZ_QUESTIONS, layer_scores, recommendation, total_score


def test_12_questions():
    assert len(QUIZ_QUESTIONS) == 12


def test_layers_have_3_questions_each():
    layers: dict[str, int] = {}
    for q in QUIZ_QUESTIONS:
        layers[q.layer] = layers.get(q.layer, 0) + 1
    assert layers == {"strategy": 3, "sales": 3, "operations": 3, "finance": 3}


def test_zero_answers_zero_score():
    answers = {q.key: 0 for q in QUIZ_QUESTIONS}
    assert total_score(answers) == 0
    rec = recommendation(0)
    assert rec[0] == "audit"


def test_full_answers_100_score():
    answers = {q.key: 10 for q in QUIZ_QUESTIONS}
    assert total_score(answers) == 100
    rec = recommendation(100)
    assert rec[0] == "sprint"


def test_mid_score_diagnostic():
    # 6 баллов на все 12 = 72/120 = 60 → диагностика
    answers = {q.key: 6 for q in QUIZ_QUESTIONS}
    score = total_score(answers)
    assert 41 <= score <= 70
    assert recommendation(score)[0] == "diagnostic"


def test_layer_scores_sum_30_each_at_max():
    answers = {q.key: 10 for q in QUIZ_QUESTIONS}
    scores = layer_scores(answers)
    assert scores == {"strategy": 30, "sales": 30, "operations": 30, "finance": 30}


def test_options_all_have_valid_scores():
    for q in QUIZ_QUESTIONS:
        for label, score in q.options:
            assert 0 <= score <= 10
            assert label
