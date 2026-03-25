# CLAUDE.md

## Project Overview

**trading-videos** — A professional trading video generation application built with [Remotion](https://www.remotion.dev/), React, and TypeScript. Provides three composition templates for creating animated trading analysis and market update videos at 1920x1080 resolution.

## Tech Stack

- **Framework:** Remotion 4.0.414 (programmatic video rendering)
- **Language:** TypeScript 5.5.3 with strict mode
- **UI:** React 18.3.1
- **Validation:** Zod 3.22.3 (runtime schema validation for composition props)
- **Output:** JPEG frames, MP4 video

## Repository Structure

```
src/
├── index.ts            # Entry point — registers Remotion root
├── Root.tsx            # Composition definitions & Zod schemas
├── TradingVideo.tsx    # Main trading analysis video (300 frames, 10s)
├── TradingIntro.tsx    # Cinematic intro sequence (150 frames, 5s)
└── PriceAction.tsx     # Price action chart animation (240 frames, 8s)
remotion.config.ts      # Remotion config (JPEG format, overwrite output)
tsconfig.json           # TypeScript config (ES2018, commonjs, react-jsx)
package.json            # Dependencies and scripts
```

## Commands

```bash
npm start              # Launch Remotion Studio (interactive preview)
npm run build          # Render TradingVideo → out/trading-video.mp4
npm run build:intro    # Render TradingIntro → out/trading-intro.mp4
npm run build:price    # Render PriceAction → out/price-action.mp4
```

There are no test or lint commands configured.

## Architecture

### Compositions

Each video is a standalone React component registered in `Root.tsx` with a Zod schema for props validation:

| Composition | Component | Frames | FPS | Duration | Props Schema |
|---|---|---|---|---|---|
| `TradingVideo` | `TradingVideo.tsx` | 300 | 30 | 10s | `ticker`, `priceChange`, `currentPrice` |
| `TradingIntro` | `TradingIntro.tsx` | 150 | 30 | 5s | `title`, `subtitle` |
| `PriceAction` | `PriceAction.tsx` | 240 | 30 | 8s | `ticker`, `prices` (number array) |

### Animation Patterns

- Frame-driven using `useCurrentFrame()` and `useVideoConfig()`
- `interpolate()` for linear transitions between frame ranges
- `spring()` for physics-based animations with damping/mass
- `<Sequence>` components for timed sub-animations
- SVG-based charts rendered inline (no charting library)

### Design System

- Dark theme backgrounds with gradient overlays
- Accent colors: `#00d4ff` (cyan), `#00ff88` (green/positive), `#ff4757` (red/negative)
- Glow effects via `text-shadow`, `box-shadow`, and SVG filters
- Grid background patterns using SVG

## Code Conventions

- Functional components typed as `React.FC<Props>`
- Props defined with `type Props = { ... }` (TypeScript type aliases)
- Named exports for all components
- Inline CSS styles (no external stylesheets or CSS-in-JS libraries)
- Zod schemas colocated in `Root.tsx` alongside composition registration
- No external state management — props-only data flow

## Adding a New Composition

1. Create a new component file in `src/` following the existing pattern
2. Define a Zod schema in `Root.tsx`
3. Register a `<Composition>` in the `RemotionRoot` component
4. Add a build script in `package.json`: `"build:<name>": "remotion render <CompositionId> out/<filename>.mp4"`
