# DESIGN.md — EDL site design system

> Stitch-format спецификация. Источник правды для всех визуальных решений. Каждый CSS-токен из `styles.css` — отражение этого документа.

---

## 1. Colors (OKLCH)

### Tinted neutrals — основа

Никогда не используем чистый `#000` или чистый `#fff`. Всегда tinted, со слабым оттенком в сторону бренда (cool blue).

```css
--neutral-100: oklch(0.98 0.005 250);  /* fog white — основной фон */
--neutral-200: oklch(0.95 0.008 250);  /* tinted surface — секции */
--neutral-300: oklch(0.88 0.012 250);  /* subtle borders */
--neutral-400: oklch(0.65 0.015 250);  /* tertiary text */
--neutral-500: oklch(0.45 0.018 250);  /* secondary text */
--neutral-700: oklch(0.25 0.022 250);  /* body text on light */
--neutral-800: oklch(0.18 0.025 250);  /* deep ink */
--neutral-900: oklch(0.13 0.03 255);   /* brand navy — почти чёрный с холодом */
--neutral-950: oklch(0.08 0.025 255);  /* abyss — самый глубокий */
```

### Brand

```css
--accent-lime: oklch(0.92 0.22 122);          /* electric lime, наш сигнатур */
--accent-lime-hover: oklch(0.86 0.21 122);
--accent-lime-active: oklch(0.78 0.20 122);
--accent-lime-glow: oklch(0.92 0.22 122 / 0.15); /* для тонких свечений */
```

### Semantic

```css
--text-on-light: var(--neutral-800);
--text-secondary-light: var(--neutral-500);
--text-tertiary-light: var(--neutral-400);
--text-on-dark: oklch(0.96 0.005 250);
--text-secondary-dark: oklch(0.72 0.012 250);

--bg-canvas: var(--neutral-100);
--bg-section: var(--neutral-200);
--bg-deep: var(--neutral-900);

--border-subtle: oklch(0.88 0.012 250 / 0.6);
--border-on-dark: oklch(0.96 0.005 250 / 0.08);
--border-strong: var(--neutral-800);
```

### Rules

- Accent lime — **только** на CTA-кнопках, ключевых цифрах в счётчиках, hover-fill индикаторах. Не на body-тексте, не на фонах больших площадей.
- Никаких градиентов в стиле «фиолетовый-в-розовый». Допустим только subtle radial-glow от `--accent-lime-glow`.
- Никаких теней с чистым `#000` — только tinted shadows: `oklch(0.13 0.03 255 / 0.08)`.

---

## 2. Typography

### Type families

```css
--ff-display: 'Plus Jakarta Sans', system-ui, sans-serif;
--ff-body: 'Geist', system-ui, sans-serif;
--ff-mono: 'Geist Mono', ui-monospace, monospace;
```

**Plus Jakarta Sans** — display, заголовки, акценты. Geometric, premium-vibe.  
**Geist** — body, всё остальное. Современный neutral sans.  
**Geist Mono** — eyebrow-метки, цифры, технические подписи.

### Type scale (modular, ratio 1.333 — perfect fourth)

```css
/* Static scale (for product UI / inline text) */
--fs-12: 0.75rem;     /* 12px — caption, eyebrow */
--fs-14: 0.875rem;    /* 14px — small */
--fs-16: 1rem;        /* 16px — body small */
--fs-18: 1.125rem;    /* 18px — body */
--fs-20: 1.25rem;     /* 20px — lead body */
--fs-24: 1.5rem;      /* 24px — h4 */
--fs-32: 2rem;        /* 32px — h3 */
--fs-44: 2.75rem;     /* 44px — h2 */
--fs-60: 3.75rem;     /* 60px — h1 */
--fs-84: 5.25rem;     /* 84px — display */
--fs-120: 7.5rem;     /* 120px — hero display */

/* Fluid scale (for marketing display) */
--fs-h1-fluid: clamp(3rem, 8vw, 7.5rem);     /* 48-120px */
--fs-h2-fluid: clamp(2.25rem, 5vw, 4.5rem);  /* 36-72px */
--fs-h3-fluid: clamp(1.625rem, 3vw, 2.5rem); /* 26-40px */
--fs-display-fluid: clamp(4rem, 12vw, 9rem); /* 64-144px */
```

### Tracking & line-height

```css
--lh-tight: 0.95;
--lh-snug: 1.05;
--lh-normal: 1.4;
--lh-relaxed: 1.6;

--tracking-tightest: -0.04em;  /* для display 84px+ */
--tracking-tight: -0.025em;    /* для h1, h2 */
--tracking-snug: -0.015em;     /* для h3, h4 */
--tracking-normal: 0;
--tracking-wide: 0.06em;       /* для eyebrow uppercase */
--tracking-widest: 0.12em;     /* для tiny mono labels */
```

### Hierarchy rules

- Только **2 веса** на странице: 500 (medium) и 700 (bold). Никаких light/extralight, никаких black.
- Display-заголовки (h1, hero) всегда tracking-tight или tightest. Tight letter-spacing — признак premium.
- Body всегда line-height 1.5–1.6. Заголовки — 0.95–1.05.
- Eyebrow-метки (numbered: «01 · ПОДХОД») — Geist Mono, uppercase, tracking-widest.
- Italic — НЕ для целых блоков. Только для смыслового выделения внутри текста.

---

## 3. Elevation & shadows

Pure black shadows запрещены. Все тени — tinted brand-color, layered.

```css
/* Shadow tokens — color comes from --neutral-900 with varying alpha */
--shadow-1: 0 1px 2px oklch(0.13 0.03 255 / 0.04),
            0 1px 3px oklch(0.13 0.03 255 / 0.06);
--shadow-2: 0 2px 4px oklch(0.13 0.03 255 / 0.05),
            0 4px 12px oklch(0.13 0.03 255 / 0.08);
--shadow-3: 0 4px 8px oklch(0.13 0.03 255 / 0.06),
            0 16px 32px oklch(0.13 0.03 255 / 0.10);
--shadow-4: 0 8px 16px oklch(0.13 0.03 255 / 0.08),
            0 32px 64px oklch(0.13 0.03 255 / 0.14);

/* Special: glow shadow for accent elements */
--shadow-accent: 0 0 0 1px var(--accent-lime-glow),
                 0 4px 12px oklch(0.92 0.22 122 / 0.12);
```

### Layering rules

- 3 z-уровня в hero: фон → текст → визуал. Каждый со своей elevation.
- Карточки funnel: shadow-2 в покое, shadow-3 в hover.
- Floating CTA на mobile: shadow-3.
- Modal: shadow-4 + backdrop blur.

---

## 4. Components

### Buttons

```css
/* Primary CTA — lime fill, dark text, hover slide-fill */
.btn-primary {
  background: var(--accent-lime);
  color: var(--neutral-900);
  padding: 14px 28px;
  border-radius: 4px;  /* острые углы — признак премиум, никаких rounded-full */
  font-family: var(--ff-display);
  font-weight: 600;
  letter-spacing: -0.015em;
  position: relative;
  overflow: hidden;
}

/* Hover effect — lime sliding from left */
.btn-primary::before {
  content: '';
  position: absolute;
  inset: 0;
  background: var(--accent-lime-hover);
  transform: translateX(-100%);
  transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.btn-primary:hover::before { transform: translateX(0); }
```

**Никаких:**
- Cards-внутри-cards (одна карточка = один компонент)
- Border-radius > 8px (только 0, 4, 8)
- Иконок над заголовками карточек
- Drop-shadow на тексте

### Cards

Минимум визуального decoration. Структура держит композицию, не декор.

- Border 1px tinted, не background-flat
- Hover: border-color меняется на --neutral-700, +shadow-2
- Padding минимум 32px на десктопе, 24px на мобайле
- Внутри: только заголовок + 1 описание + 1 действие. Никаких 5 элементов в одной карточке.

### Forms

В v1 нет форм (всё через Calendly modal). Если появятся — отдельная итерация.

---

## 5. Motion

### Easing tokens

```css
/* Spring-style — ОСНОВНОЕ на сайте */
--ease-out-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
--ease-out-smooth: cubic-bezier(0.16, 1, 0.3, 1);
--ease-in-out-power: cubic-bezier(0.65, 0, 0.35, 1);

/* Никогда */
/* --ease-bounce — запрещён, выглядит дёшево */
/* --ease-elastic — запрещён */
```

### Durations

```css
--dur-fast: 150ms;     /* hover, focus */
--dur-medium: 300ms;   /* card hover, button fill */
--dur-slow: 600ms;     /* section reveals */
--dur-cinematic: 1200ms; /* hero entry */
```

### Motion patterns

| Эффект | Где | Реализация |
|---|---|---|
| **Reveal-on-scroll** | Каждая секция | IntersectionObserver + `transform: translateY(40px)` → 0, opacity 0 → 1, stagger 60ms между детьми |
| **Hero text reveal** | Hero h1 | Word-by-word через split + animate-in с stagger 80ms, easing spring |
| **Parallax title** | Заголовки секций | `translateY` from -10% to +10% по scroll progress, через CSS Scroll-driven Animations |
| **Count-up numbers** | Stats блок | requestAnimationFrame counter с easeOutQuart |
| **Magnetic CTA** | Primary buttons | mousemove → translateX/Y proportional to cursor distance, max 8px, ease 200ms |
| **Hover-fill button** | Все CTA | ::before slide-in left-to-right, 400ms spring |
| **Sticky section title** | Длинные секции (FAQ) | `position: sticky` + opacity transition |
| **Custom cursor** | Desktop only | Кастомный cursor circle, scale 2x при hover на CTA |
| **Architecture diagram** | Method block | SVG paths draw-in при scroll-into-view |

### Reduced motion

Все scroll-driven animations отключаются через:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

Magnetic cursor и parallax — отключаются JS-проверкой `matchMedia`.

---

## 6. Do's and Don'ts

### ✅ Do

- Использовать OKLCH для всех цветов
- Tinted neutrals везде (никогда чистый чёрный/серый)
- Spring-easing на всех transitions
- Layered shadows (минимум 2 уровня)
- 8px baseline grid для всех spacing
- Композиция асимметричная (ratio 60/40, 70/30)
- Plus Jakarta Sans для display, Geist для body
- Negative letter-spacing на крупных заголовках (-0.025em минимум)
- Реальные цифры, не округлённые
- Eyebrow-нумерация с Mono шрифтом

### ❌ Don't

- Inter в любых местах (заменён на Plus Jakarta + Geist)
- Pure black `#000` или pure gray `#888`
- Bounce/elastic easing
- Cards-в-cards гнездования
- Big rounded icons выше заголовков
- Stock фото или AI-illustrations
- Drop shadows с `rgba(0,0,0,X)` — только tinted
- Тяжёлые библиотеки (Framer Motion, GSAP) — vanilla JS только
- Линейная композиция «hero + grid + grid + CTA»
- Стрелочки-эмодзи как декор
- Glassmorphism / neumorphism / brutalism mix

---

**Версия:** 1.0 · 27 апреля 2026  
**Изменения:** при пересмотре — обновить версию и записать в `BRAND_GUIDELINES.md` раздел 7
