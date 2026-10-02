# Brand & Category Visual Intelligence

Status: curated working intelligence; not automatically canonical.

Purpose: prevent Sentinel from solving unrelated products with the same visual formula. This module adds context-aware brand, category, color, competitive and anti-monotony reasoning to the existing Designer brain.

Core principle:

> Consistent judgment, not consistent aesthetics.

The module must not reduce categories to deterministic recipes such as `fintech = blue`, `health = green`, or `food = red`. Category conventions are priors to inspect, not answers.

## Required reasoning order

1. Existing brand guidelines, if any
2. Product strategy and jobs to be done
3. Audience, environment and trust/risk level
4. Category conventions and user expectations
5. Competitive landscape and visual saturation
6. Cultural/geographic context
7. Accessibility and platform constraints
8. Brand personality and desired emotional tone
9. Distinctiveness opportunity
10. Light/dark appearance behavior
11. Cross-project anti-monotony audit
12. Final visual direction with evidence and tradeoffs

## Files

- `decision-protocol.md` — how to reason before selecting a visual language, including mandatory light/dark companion design
- `color-intelligence.md` — evidence-based color reasoning and appearance rules
- `category-priors.md` — category expectations, clichés and questions to investigate
- `anti-monotony.md` — detects accidental reuse of the same visual formula
- `experts-and-sources.md` — SMEs, research, design systems and reference libraries
- `case-study-bank.md` — mechanism-level examples across finance, health, food and fashion/beauty
- `reference-routing.md` — which source type to use for which design question
- `project-visual-brief.md` — reusable pre-design worksheet for category scan, references, 3 directions, appearance pairing and anti-monotony review

## Mandatory output behavior

Before a production direction is accepted, Sentinel should be able to state:

- why this visual language fits this product;
- which conventions are being followed and which are being rejected;
- what competitors commonly do;
- what makes the direction distinctive without harming usability;
- how light and dark appearances differ intentionally;
- which previous project patterns were checked for accidental repetition;
- what evidence is strong, contextual, practitioner-led or merely inspirational.

For every meaningful production screen or visual direction, create both light and dark companion variants in clearly separated Figma frames/pages unless the product owner explicitly requests one appearance only. The context decides which mode is primary; neither mode is a mechanical inversion of the other.

References are inputs to judgment, never templates to imitate. This module inherits the repository's evidence policy and originality policy.

Research pass created: 2026-10-02.
