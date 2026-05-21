/**
 * mini-checkup-engine.js — Mini-Чекап v2 scoring engine (JS-порт Python core/quiz.py).
 * Единственный источник правды для расчёта Score на клиенте.
 * Идентичен Python-алгоритму — тестируется фикстурами quiz_scoring_cases.json.
 */
(function (root, factory) {
  'use strict';
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = factory();
  } else {
    root.MiniCheckupEngine = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // ── Загрузка канона ───────────────────────────────────────────────────────
  let _canon = null;

  function setCanon(canon) {
    _canon = canon;
  }

  function _assertCanon() {
    if (!_canon) throw new Error('Canon not loaded. Call MiniCheckupEngine.setCanon(data) first.');
  }

  // ── Определение стадии из P2 ─────────────────────────────────────────────
  function stageDetection(p2Option) {
    _assertCanon();
    const stage = _canon.stage_from_p2[p2Option] || 'team';
    const confidence = _canon.stage_confidence[p2Option] || 'low';
    return { stage, confidence };
  }

  // ── Score по слою (0..100) ────────────────────────────────────────────────
  function layerScore0to100(answers, layer) {
    _assertCanon();
    const qs = _canon.questions.filter(q => q.layer === layer);
    if (!qs.length) return 0;
    const raw = qs.reduce((sum, q) => sum + (answers[q.key] || 0), 0);
    return raw * 100 / (10 * qs.length);
  }

  // ── Взвешенный суммарный Score ────────────────────────────────────────────
  function totalScore(answers, stage) {
    _assertCanon();
    const weights = _canon.stage_weights[stage] || _canon.stage_weights['team'];
    let total = 0;
    for (const layer of ['01', '02', '03', '04']) {
      total += layerScore0to100(answers, layer) * (weights[layer] || 0);
    }
    return Math.round(total);
  }

  // ── Категория по Score ────────────────────────────────────────────────────
  function categoryLabel(score) {
    _assertCanon();
    for (const t of _canon.category_thresholds) {
      if (score <= t.max) return { label: t.label, color: t.color };
    }
    const last = _canon.category_thresholds[_canon.category_thresholds.length - 1];
    return { label: last.label, color: last.color };
  }

  // ── CTA по Score ──────────────────────────────────────────────────────────
  function ctaForScore(score) {
    if (score <= 40) return { primary: 'audit', secondary: 'demo' };
    if (score <= 70) return { primary: 'audit_plus', secondary: 'audit' };
    return { primary: 'diagnostic_waitlist', secondary: 'audit_plus' };
  }

  // ── Бенчмарк ─────────────────────────────────────────────────────────────
  function benchmarkFor(segment, stage, userScore) {
    _assertCanon();
    const segData = _canon.benchmark[segment];
    if (segData && segData[stage] != null) {
      const mean = segData[stage];
      return { mean, delta: userScore - mean };
    }
    const fallback = _canon.benchmark_all_stages[stage];
    if (fallback != null) {
      return { mean: fallback, delta: userScore - fallback, isFallback: true };
    }
    return { mean: null, delta: null };
  }

  // ── Советы по росту ───────────────────────────────────────────────────────
  function hintFor(questionKey, answerScore) {
    _assertCanon();
    const hints = _canon.growth_hints[questionKey];
    if (!hints) return { short: 'Есть пространство для роста', action: 'Поставьте конкретный следующий шаг с датой.' };
    return answerScore <= 3 ? hints.low : hints.mid;
  }

  // ── Топ-3 точки роста ─────────────────────────────────────────────────────
  function top3GrowthPoints(answers, stage) {
    _assertCanon();
    const layers = ['01', '02', '03', '04'];
    const layerScores = layers.map(l => ({ layer: l, score: layerScore0to100(answers, l) }));
    layerScores.sort((a, b) => a.score - b.score);
    const weakest3 = layerScores.slice(0, 3);

    return weakest3.map(({ layer }) => {
      const qs = _canon.questions.filter(q => q.layer === layer);
      const worst = qs.reduce((min, q) =>
        (answers[q.key] || 0) < (answers[min.key] || 0) ? q : min, qs[0]);
      const ansScore = answers[worst.key] || 0;
      const hint = hintFor(worst.key, ansScore);
      return {
        layer,
        layerLabel: _canon.layer_labels[layer],
        questionKey: worst.key,
        short: hint.short,
        action: hint.action,
      };
    });
  }

  // ── Полный результат ──────────────────────────────────────────────────────
  function buildResult(answers, p2Option, segment) {
    _assertCanon();
    const { stage, confidence } = stageDetection(p2Option);
    const score = totalScore(answers, stage);
    const { label: category, color: categoryColor } = categoryLabel(score);
    const { mean: benchmarkMean, delta: benchmarkDelta, isFallback } = benchmarkFor(segment, stage, score);
    const layerScores = {};
    for (const l of ['01', '02', '03', '04']) {
      layerScores[l] = Math.round(layerScore0to100(answers, l));
    }
    const growthPoints = top3GrowthPoints(answers, stage);
    const { primary: ctaPrimary, secondary: ctaSecondary } = ctaForScore(score);

    return {
      score,
      category,
      categoryColor,
      stage,
      stageLabel: _canon.stage_labels[stage],
      stageDesc: _canon.stage_desc[stage],
      stageConfidence: confidence,
      segment,
      segmentLabel: _canon.segment_labels[segment] || 'вашего сегмента',
      segmentDisplay: _canon.segment_display[segment] || segment,
      layerScores,
      benchmarkMean,
      benchmarkDelta,
      benchmarkFallback: isFallback || false,
      growthPoints,
      ctaPrimary,
      ctaSecondary,
    };
  }

  return {
    setCanon,
    stageDetection,
    layerScore0to100,
    totalScore,
    categoryLabel,
    ctaForScore,
    benchmarkFor,
    hintFor,
    top3GrowthPoints,
    buildResult,
  };
}));
