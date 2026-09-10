# Shanghai Commute Drive

[简体中文](README.md) · [Documentation](docs/INDEX.md)

A browser city-exploration and driving project built with TypeScript, Three.js, Vite and Blender. Automatic touring, manual driving, vehicles, streamed scenery, collision, journey activities, local progress and a photo album are implemented in the current codebase.

**This is a private development and migration repository, not a public open-source release.** The original visual assets remain in use. No blanket MIT license is granted for this project. Dependencies, models, photographs and map data retain their individual terms.

## Restore and run

Git stores source code, scripts, tests, lockfiles, documentation and provenance records. Large runtime and authoring assets are private Release attachments. A Git clone alone does not restore those assets.

Use Node.js 20.19+ or compatible 22.12+/24, Python 3.9+, Git, and GitHub CLI authenticated to an authorized account.

```sh
git clone https://github.com/rttang/shanghai-commute-drive.git
cd shanghai-commute-drive
gh release download backup-2026-09-10 --repo rttang/shanghai-commute-drive --pattern '*.zip' --dir .tooling/restore-downloads
python3 scripts/restore_private_assets.py --parts .tooling/restore-downloads --group runtime
npm ci
npm run dev
```

Open `http://127.0.0.1:8080/`. Use `npm ci --no-bin-links` on ExFAT where required. Restore with `--group all` before model authoring. On native Windows use `py -3` instead of `python3` where appropriate; WSL2 can run the existing Bash/Python authoring workflow after installing Linux dependencies.

## Commands and controls

- `npm run build`: type checking, model-placement verification, static build and resource hash verification.
- `npm run test:portable`: regressions excluding private historical freeze/archive checks.
- `npm test`: original suite, including historical asset-preservation requirements that may need the original archive.
- `npm run build:release` / `npm run preview:release`: optimized runtime build and local preview on port 8081.
- `npm run streets:master`: offline modeling workflow; it is not a normal startup command.
- W/arrow-up accelerates; S/arrow-down brakes or reverses; A/D steers; Space applies the handbrake; P/Esc pauses; R resets; C changes the camera.

The app UI currently uses Simplified Chinese. Progress and photos are browser-local, not synchronized across computers. Dynamics are game calibrations; the city representation is simplified and is not navigation, survey data or vehicle certification.

## Documentation and source credits

See [Architecture](docs/ARCHITECTURE.md), [Technical design](docs/TECHNICAL_DESIGN.md), [Resource recovery](docs/RESOURCE_RECOVERY.md), [Asset sources](docs/ASSET_SOURCES.md), [Third-party notices](THIRD_PARTY_NOTICES.md), and the [upload/recovery report](docs/private-backup/REPORT.md).

Asset licenses and unresolved provenance qualifications remain recorded even though the repository is private. Any future public redistribution requires a separate review of the exact files, embedded materials and intended use.
