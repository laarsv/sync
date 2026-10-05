# Sync — Design system

Stand 2026-10-05. sync folgt der **VRWB-CI v3**. Maßgeblich ist `Suite/DESIGN.md`
(Projekt vrwb_suite, Tokens in `frontend/src/theme-v3.css`): Farben, Typografie,
Dichte, Dialoge, Zugänglichkeit. Dieses Dokument wiederholt das nicht. Es enthält
die Zuordnung der CI zum Code von sync, die ausdrücklichen Abweichungen und den
Marken-Teil (§1b).

Neue Oberfläche nutzt die Tokens unten, keine neuen Hex-Werte. Schrift mindestens
12 px (`text-xs`), Foreground auf Royal-Fläche ist immer Weiß (`paper`).

## 1. Tokens in Tailwind (`frontend/tailwind.config.js`)

| Tailwind | CI-Token | Wert |
|---|---|---|
| `royal`, `royal-soft` | `--royal`, `--soft` | `#2947c9`, `#aeb9ee` |
| `ink` (+ Alpha, z. B. `ink/10`) | `--ink` + Stufen | `#161a24` |
| `paper` | `--paper` | `#ffffff` |
| `canvas`, `surface-2`, `surface-3` | `--canvas`, `--surface-2/-3` | `#f3f5fa`, `#f7f8fc`, `#eef1f8` (noch ungenutzt) |
| `pos`, `neg`, `warn` | `--pos`, `--neg`, `--warn` | `#177245`, `#c0392b`, `#9a5900` |
| `pos-tint`, `neg-tint`, `warn-tint`, `neg-line` | `--pos-tint` … | Tönungen und Linie aus der CI |
| `shadow-1`, `shadow-2` | `--shadow-1/-2` | Karten bzw. Dialoge |

Grün, Rot und Gelb nur als Signal (OK, Fehler, Warnung), nie als Dekoration.
Standard-Tailwind-Farben (`red-600`, `green-100` …) nicht verwenden.

## 1b. Wortmarke, Produkt-Lockup & Bildmarke — VRWB CI v1.0 (verbindlich)

Quelle (Source of Truth): claude.ai-Design-Projekt **„VRWB Markenidentität"**
(`VRWB Corporate Identity.dc.html`, per DesignSync erreichbar; das Design-Projekt
gewinnt). Konvention:

- **Wortmarke** `vrwb` = gesetzter Text, **immer klein**, Roboto **900**, Laufweite
  **−4,5 %** (`tracking-wordmark`). Cursor `_` in Royal = einziges grafisches Element.
- **Produkt-Lockup „Standalone"** (`components/Wordmark.jsx`, nie inline nachbauen):
  **`vrwb_sync`** — der Unterstrich wird zum Trenner in Royal, der Toolname hängt direkt
  dran in **Roboto Mono 500 Royal**, ~0,83× Größe, Laufweite −1 % (`tracking-toolname`).
  Toolname immer klein, ein Wort. Einsatz: Login-Hero, Footer (→ vrwb.de), Browser-Titel.
  Auf Ink: `vrwb` weiß, `_sync` in **Royal Soft** (`<Wordmark onInk />`).
- **Produkt-Lockup „Mit Signatur" — bevorzugte Marke, im App-Header** (`components/Logo.jsx`):
  handschriftliche Signatur (Royal, `public/logo-clean.svg` als CSS-Maske) links, dünne
  Haarlinie (`bg-ink/15`) als Trenner, rechts das Standalone-Lockup `vrwb_sync`. Signatur
  = „der Mensch", `vrwb_` = „die Maschine".
- **Blink** (`.wordmark-cursor-blink`, 1,2 s `steps`) nur für den Cursor der puren
  Dachmarken-Wortmarke im Hero (Login-Fußzeile `vrwb_`) — nie im Standalone-Lockup
  (dort ist `_` Trenner, kein Cursor) und nie in der App-Nav.
- **Bildmarke/Favicon**: Anfangsbuchstabe + Cursor (`s_`) weiß/royal-soft auf Royal,
  abgerundetes Quadrat mit Radius ≈ 23 % der Kante (`frontend/public/favicon.svg`).
  Wortmarke und Bildmarke nie nebeneinander doppeln.
- Nie „Sync"/„SYNC"/„VRWB" als Marke setzen, nicht sperren/stauchen, keine
  Schatten/Verläufe/Outlines.
- Roboto Mono self-hosted via `@fontsource/roboto-mono` (500), Tailwind `font-mono`.

## 2. Bausteine (`frontend/src/index.css`, `components/ui/`)

- `.btn` mit `.btn-primary`, `.btn-outline`, `.btn-danger`, `.btn-ghost`, `.btn-sm`.
  **Dichte-Norm v2:** `.btn`, `.input` und der `Select`-Trigger sind mobil 44 px,
  ab `sm:` 38 px hoch (`min-h-[44px] sm:min-h-[38px]`, analog `--control-height`);
  `.btn-sm` ist 32 px.
- `.card`, `.input`, `.field-label`, `.eyebrow`.
- `Select` (eigene Komponente, kein natives `<select>`), `Modal` (Formulare),
  `ConfirmDialog` (Bestätigungen, `useConfirm()`), `Pill`, `Toggle`, `Icons`
  (inline SVG, `stroke-2`, `currentColor`, kein Icon-Paket).
- Keine nativen `alert`/`confirm`/`prompt`. Bestätigungen laufen über `useConfirm()`:
  natives `<dialog>` mit `showModal()`, `aria-modal`, Titel als `aria-label`, Esc
  bricht ab, Fokus startet auf „Abbrechen“ und kehrt zum Auslöser zurück,
  destruktive Aktionen mit `btn-danger`.
- Kartenlayout mobil, nichts scrollt horizontal.

## 3. Abweichungen von der VRWB-CI

- **Hintergrund weiß statt `--canvas`:** sync hat keine Shell mit Arbeitsfläche.
  Das Token `canvas` ist angelegt, aber nicht in Gebrauch.
- **Tokens als Tailwind-Farben statt CSS-Variablen.** Ink-Stufen sind Tailwind-Alpha
  (`ink/60`), nicht `--ink-60`.
- **Nebentexte in `text-ink/50`** (Platzhalter, „Letzter Lauf“) liegen unter der
  CI-Grenze für Text (Alpha .62). Offen.
- **Fokusring** ist `ring-royal/40` (Tailwind-Ring), nicht `outline` mit `--focus-ring` (Royal/70).
- **Karten** nutzen `shadow-sm` statt `shadow-1`.
- **Überschriften:** Roboto 900 mit `tracking-tight` (−.01 em) statt −.035 em;
  `.eyebrow` in `text-xs`, 700, Großbuchstaben mit `tracking-wider` (.05 em) statt .08 em.
- **Schrift:** Buttons `text-sm` auf allen Breiten (CI: mobil 1 rem), Eingaben `text-base`.
- **Hinweise** (Erfolg, Fehler) sind Bänder mit 4-px-Balken links in `pos`/`neg`;
  Erfolg ist grün (`pos-tint`), die CI nutzt dafür Royal-Tint.
- **`Modal.jsx`, `IntroModal.jsx` und der Menü-Drawer in `Layout.jsx`** sind `div`-Overlays
  (`role="dialog"`, `aria-modal`; Esc bei Modal und Intro, nicht beim Drawer) mit Ink/60
  und Blur, ohne `showModal()`, ohne Fokusführung und Fokusrückgabe, `Modal.jsx` ohne
  `aria-label`. Umstellung auf natives `<dialog>` offen; nur `ConfirmDialog` folgt der CI.
- **Google-Kalenderfarben** (`EVENT_COLORS` in `PairsPage.jsx`) sind Googles Palette
  für `colorId`, keine CI-Farben.
- **Dark Mode:** keiner, wie in der CI.
