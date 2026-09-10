# Three.js Kart Racing Demo

A fun Mario Kart-inspired racing game demo built with Three.js and Cannon-es!

Drive around the circular track, collect coins, hit the boost pads, and set a high score!

## Controls

| Action | Keys |
|--------|------|
| Accelerate | W or ↑ |
| Reverse | S or ↓ |
| Steer Left | A or ← |
| Steer Right | D or → |
| Jump | Space |
| Turbo Boost | B |
| Change Color | C |
| Reset Position | R |
| Pause Game | P or Escape |

## Features

- **Circular Race Track** - A proper ring-shaped track with curbs and road markings
- **Mario Kart-Style Kart** - Custom 3D kart with spoiler, headlights, and proper wheel positioning
- **Boost Pads** - 4 glowing boost pads around the track for speed bursts
- **Coin Collection** - 40+ coins scattered on and around the track
- **Particle Effects** - Dust trails while driving, sparkles when collecting coins, speed lines during boosts
- **Checkered Grass** - Nintendo-style alternating grass pattern
- **Physics-Based Driving** - Realistic physics with Cannon-es
- **Score System** - Track coins, time remaining, and best scores
- **Toon Shading** - Vibrant Nintendo-style graphics
- **Game Settings (lil-gui)** - Adjust difficulty, time limits, and more
- **Sound Effects** - Generated programmatically using Web Audio API (no external sound files)

## Gameplay

1. Press **Enter** or click **Start Game** to begin
2. Drive around the circular track collecting coins
3. Hit the **blue boost pads** for a speed boost
4. Collect all coins before time runs out for bonus points
5. Your best score is saved locally

## Setup

Download [Node.js](https://nodejs.org/en/download/).
Run the following commands:

```bash
# Install dependencies (only the first time)
npm install

# Run the local server at localhost:8080
npm run dev

# Build for production in the dist/ directory
npm run build
```

## Tech Stack

- **Three.js** - 3D graphics and rendering
- **Cannon-es** - Physics simulation
- **lil-gui** - Settings panel
- **Webpack** - Module bundling
- **Web Audio API** - Sound effects (oscillator-based)

## Credits

The project was built using templates from [Bruno Simon's](https://github.com/brunosimon)
[Three.js Journey](https://threejs-journey.com/) class.

The project uses [Cannon-es](https://pmndrs.github.io/cannon-es/docs/index.html)
and [Three.js](https://threejs.org/) libraries.

## Support the Project

If you enjoy Coin Racer and would like to support development of future games:

https://www.paypal.com/paypalme/doctorNoo
