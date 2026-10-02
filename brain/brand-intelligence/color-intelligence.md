# Color Intelligence

Status: contextual guidance. This is not a universal color-to-emotion lookup table.

## Core evidence position

Color can influence brand perception and behavior, but context, culture, task, saturation, value, existing associations and competitive use matter. Research does not support treating one hue as a universal emotional command.

### Strong cautions

- Labrecque & Milne found color can influence brand-personality judgments and purchase intent, including effects of hue, saturation and value; use this as evidence that color matters, not as permission to hard-code category recipes.
- Elliot & Maier's review concludes color can affect affect, cognition and behavior but explicitly warns that boundary conditions and real-world generalizability remain important. Avoid simplistic claims.
- Apple HIG states color can communicate status, feedback and brand, and requires custom colors to work in light, dark and increased-contrast contexts.
- IBM, Adobe Spectrum, Atlassian and USWDS all use role-based/semantic color systems rather than treating raw hues as the design system.

## Semantic roles before hex values

Define roles such as:
- canvas;
- surface;
- raised surface;
- primary text;
- secondary text;
- interactive/brand action;
- focus;
- selection;
- success/stable;
- warning/watch;
- danger/risk;
- informational;
- learning/memory;
- data-series categorical;
- data-series sequential/diverging.

Only then assign actual color values per appearance.

## Brand color vs UI color

A brand color does not need to flood the interface. Brand expression can live in typography, imagery, motion, illustration, data emphasis, selected states and signature moments.

Apple's branding guidance specifically recommends judicious accent-color use so brand color does not overwhelm controls or dilute its impact.

## Light and dark are separate perceptual systems

Do not create dark mode by mechanically inverting light mode, or light mode by bleaching a dark design.

Re-tune:
- luminance hierarchy;
- perceived saturation;
- contrast;
- borders;
- shadow/elevation;
- glow;
- semantic states;
- data visualization;
- photography and artwork;
- illustration;
- focus and disabled states.

Apple, Atlassian, Adobe Spectrum and IBM all provide theme-specific values/behavior rather than assuming one palette works unchanged everywhere.

## Cultural context

Do not assume Western semantic mappings are universal. Apple explicitly notes that color meanings vary by country and gives financial-chart examples where positive movement may be represented differently by locale.

For regionally important products, record intended markets and test critical semantic color conventions locally.

## Accessibility

- Never rely on color alone for meaning.
- Reinforce state with labels, icons, shapes, patterns or line treatment.
- Verify text and non-text contrast against applicable WCAG requirements.
- Data visualizations require deliberate categorical/sequential/diverging palette choices and non-color reinforcement where needed.

## Competitive distinctiveness

Color is also a memory/distinctiveness asset. Ehrenberg-Bass work on distinctive brand assets treats color as potentially useful only when it gains both prevalence and uniqueness for a brand.

Therefore ask:
- Is this hue strongly owned by competitors?
- Will using the category-default hue increase familiarity but reduce distinctiveness?
- Can distinctiveness come from value, saturation, pairing, material, typography or motion rather than a novel hue?

## Avoid the category-color trap

Bad reasoning:
- fintech → blue;
- health → green;
- food → red/orange;
- luxury → black;
- AI → purple gradient.

Better reasoning:
- identify category expectations;
- inspect competitor saturation;
- define desired brand personality;
- identify trust/risk constraints;
- select a color architecture that is ownable and accessible;
- validate it across real screens, imagery and both appearances.

## Source anchors

- Labrecque, Lauren I. & Milne, George R. (2012), Journal of the Academy of Marketing Science: https://doi.org/10.1007/s11747-010-0245-y
- Elliot, Andrew J. & Maier, Markus A. (2014), Annual Review of Psychology: https://doi.org/10.1146/annurev-psych-010213-115035
- Song et al. (2022), Psychology & Marketing, logo colorfulness and perceived product variety: https://doi.org/10.1002/mar.21674
- Apple HIG Color: https://developer.apple.com/design/human-interface-guidelines/color
- Apple HIG Branding: https://developer.apple.com/design/human-interface-guidelines/branding
- Apple HIG Dark Mode: https://developer.apple.com/design/human-interface-guidelines/dark-mode
- IBM Design Language Color: https://www.ibm.com/design/language/color/
- IBM Data Visualization: https://www.ibm.com/design/language/data-visualization/design/basics/
- Adobe Spectrum Color: https://spectrum.adobe.com/foundations/color/color
- Atlassian Design Color: https://atlassian.design/foundations/color
- USWDS Color: https://designsystem.digital.gov/design-tokens/color/overview/

Research reviewed 2026-10-02. Links are reference locators; do not redistribute third-party visual assets.
