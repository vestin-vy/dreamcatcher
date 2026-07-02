# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** DreamCatcher
**Generated:** 2026-06-20 12:32:42
**Category:** Warm Handmade / Boho Brand
**Repalette:** 2026-07-02 — warm handmade boho (cream/terracotta/mint), per rebrand brief; token names unchanged, values only

---

## Global Rules

### Color Palette

| Role | Hex | CSS Variable |
|------|-----|--------------|
| Primary | `#3B2F2A` | `--color-primary` |
| On Primary | `#FFFFFF` | `--color-on-primary` |
| Secondary | `#6B5D54` | `--color-secondary` |
| Accent/CTA | `#B4552D` | `--color-accent` |
| Accent hover | `#94431F` | `--color-accent-hover` |
| Background | `#FAF3E8` | `--color-background` |
| Surface | `#FFFFFF` | `--color-surface` |
| Surface alt | `#F3EADC` | `--color-surface-alt` |
| Foreground | `#2E2622` | `--color-foreground` |
| Muted | `#E8ECF0` | `--color-muted` |
| Muted foreground | `#7A6A5F` | `--color-muted-foreground` |
| Border | `#E4D6C3` | `--color-border` |
| Destructive | `#DC2626` | `--color-destructive` |
| Ring | `#3B2F2A` | `--color-ring` |
| Accent 2 (secondary CTA) | `#2F7D5F` | `--color-accent-2` |
| Accent 2 hover | `#266A50` | `--color-accent-2-hover` |
| Accent 2 bright (decoration/gradients ONLY — never text on white) | `#7FCDB0` | `--color-accent-2-bright` |
| Accent 2 soft (badge bg) | `#E9F6EF` | `--color-accent-2-soft` |
| Accent 2 on soft | `#1E5C45` | `--color-accent-2-on-soft` |

**Gradients:**

```css
--gradient-hero:
  radial-gradient(120% 120% at 82% 8%, rgba(180,85,45,0.14), transparent 55%),
  radial-gradient(120% 120% at 0% 100%, rgba(127,205,176,0.22), transparent 52%),
  linear-gradient(180deg, #FAF3E8 0%, #F3EADC 100%);   /* LIGHT hero */
--gradient-accent: linear-gradient(120deg, var(--color-accent) 0%, var(--color-accent-2-bright) 100%); /* terracotta -> mint */
```

**Color Notes:** Warm handmade boho — cream page, terracotta primary CTA (white text 4.91:1 ✓),
deep mint secondary CTA (white text 4.98:1 ✓, ties the site to the mint IG logo).
Hero is LIGHT: hero text uses foreground/secondary; the mid-page editorial banner stays the
single dark block (base `#2E2622` + terracotta wash). Gold survives only inside legacy SVG
artwork where it still reads; the hero dreamcatcher line art is terracotta on cream.

### Typography

- **Heading Font:** Cormorant
- **Body Font:** Montserrat
- **Mood:** luxury, high-end, fashion, elegant, refined, premium
- **Google Fonts:** [Cormorant + Montserrat](https://fonts.google.com/share?selection.family=Cormorant:wght@400;500;600;700|Montserrat:wght@300;400;500;600;700)

**CSS Import:**
```css
@import url('https://fonts.googleapis.com/css2?family=Cormorant:wght@400;500;600;700&family=Montserrat:wght@300;400;500;600;700&display=swap');
```

### Spacing Variables

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | `4px` / `0.25rem` | Tight gaps |
| `--space-sm` | `8px` / `0.5rem` | Icon gaps, inline spacing |
| `--space-md` | `16px` / `1rem` | Standard padding |
| `--space-lg` | `24px` / `1.5rem` | Section padding |
| `--space-xl` | `32px` / `2rem` | Large gaps |
| `--space-2xl` | `48px` / `3rem` | Section margins |
| `--space-3xl` | `64px` / `4rem` | Hero padding |

### Shadow Depths

| Level | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)` | Subtle lift |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.1)` | Cards, buttons |
| `--shadow-lg` | `0 10px 15px rgba(0,0,0,0.1)` | Modals, dropdowns |
| `--shadow-xl` | `0 20px 25px rgba(0,0,0,0.15)` | Hero images, featured cards |

---

## Component Specs

### Buttons

```css
/* Primary Button */
.btn-primary {
  background: #B4552D;
  color: white;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: all 200ms ease;
  cursor: pointer;
}

.btn-primary:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

/* Secondary Button */
.btn-secondary {
  background: transparent;
  color: #3B2F2A;
  border: 2px solid #3B2F2A;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: all 200ms ease;
  cursor: pointer;
}
```

### Cards

```css
.card {
  background: #FAF3E8;
  border-radius: 12px;
  padding: 24px;
  box-shadow: var(--shadow-md);
  transition: all 200ms ease;
  cursor: pointer;
}

.card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
}
```

### Inputs

```css
.input {
  padding: 12px 16px;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  font-size: 16px;
  transition: border-color 200ms ease;
}

.input:focus {
  border-color: #3B2F2A;
  outline: none;
  box-shadow: 0 0 0 3px #3B2F2A20;
}
```

### Modals

```css
.modal-overlay {
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
}

.modal {
  background: white;
  border-radius: 16px;
  padding: 32px;
  box-shadow: var(--shadow-xl);
  max-width: 500px;
  width: 90%;
}
```

---

## Style Guidelines

**Style:** Liquid Glass

**Keywords:** Flowing glass, morphing, smooth transitions, fluid effects, translucent, animated blur, iridescent, chromatic aberration

**Best For:** Premium SaaS, high-end e-commerce, creative platforms, branding experiences, luxury portfolios

**Key Effects:** Morphing elements (SVG/CSS), fluid animations (400-600ms curves), dynamic blur (backdrop-filter), color transitions

### Page Pattern

**Pattern Name:** Feature-Rich Showcase

- **Conversion Strategy:** Clear feature hierarchy. One key message per card. Strong CTA repetition.
- **CTA Placement:** Hero (sticky) + After features + Bottom
- **Section Order:** 1. Hero (value prop), 2. Feature grid/cards (4-6), 3. Use cases or benefits, 4. Social proof or logos, 5. CTA

---

## Anti-Patterns (Do NOT Use)

- ❌ Cheap visuals
- ❌ Fast animations

### Additional Forbidden Patterns

- ❌ **Emojis as icons** — Use SVG icons (Heroicons, Lucide, Simple Icons)
- ❌ **Missing cursor:pointer** — All clickable elements must have cursor:pointer
- ❌ **Layout-shifting hovers** — Avoid scale transforms that shift layout
- ❌ **Low contrast text** — Maintain 4.5:1 minimum contrast ratio
- ❌ **Instant state changes** — Always use transitions (150-300ms)
- ❌ **Invisible focus states** — Focus states must be visible for a11y

---

## Pre-Delivery Checklist

Before delivering any UI code, verify:

- [ ] No emojis used as icons (use SVG instead)
- [ ] All icons from consistent icon set (Heroicons/Lucide)
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover states with smooth transitions (150-300ms)
- [ ] Light mode: text contrast 4.5:1 minimum
- [ ] Focus states visible for keyboard navigation
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive: 375px, 768px, 1024px, 1440px
- [ ] No content hidden behind fixed navbars
- [ ] No horizontal scroll on mobile
