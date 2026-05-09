# DESIGN: Impeccable Design System

## Scene Sentence
> "A solo momentum trader sitting at a single desktop monitor at 6:45 AM, scanning for pre-market runners in a dark room, needing to extract go/no-go information in under 30 seconds."

## Theme
- **Primary**: Deep Dark
- **Reasoning**: Reduces eye strain during early morning pre-market sessions in dim environments.

## Color Strategy: Restrained
- **Neutral**: Tinted Gray (OKLCH L=10% – 95%, C=0.005)
- **Accent**: Emerald Green (OKLCH L=70%, C=0.15, H=150) — Used strictly for "in play" signals and positive delta.
- **Alert**: Amber/Orange — Used for "Repeat Runners" and high-volatility "Wake Up" alerts.
- **Danger**: Red — Used for "Fading" momentum or risk-off signals.

## Typography
- **Scale**: 1.25x Ratio.
- **Hierarchy**: Tiny (10px) labels for secondary data, Large (20px+) bold for primary price/gap metrics.
- **Font**: Monospace (Inter/Roboto Mono) for all numerical data to ensure column alignment.

## Layout & Rhythm
- **Sparse Containers**: No heavy cards. Use thin `border-gray-800` dividers and background-tint variations to define zones.
- **Data Density**: High. Use compact rows with consistent column widths.
- **Spacing**: Varied rhythm. Large gaps between main sections, tight (4px–8px) spacing within data widgets.

## Motion
- **Pulse**: Subtle emerald pulse on the "Live" session badge when the market is open.
- **Transitions**: 200ms ease-out-expo for all hover states. No layout shifts.

## Constraints (Impeccable Laws)
- No glassmorphism.
- No gradient text.
- No SaaS-cliché hero metrics.
- No nested cards.
- No side-stripe borders as accents.
