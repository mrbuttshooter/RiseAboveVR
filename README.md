# Rise Above - a sky-high VR adventure

End-of-year project. A three-level virtual-reality platformer built in Unity 6 for **Meta Quest** (and playable on a
normal PC without a headset). It's a game of heights and hardship: run, jump, ride and balance across rooftops, cranes
and skyscrapers against the clock - no railings, real falls, limited lives. Heights are the theme; the goal is a game
that's hard, fun to play and fun to watch.

## How it plays

| Feature | What it means in the game |
|---|---|
| Three levels, rising | Rooftop Chase (11-16 m) -> Crane Rush (6-28 m) -> Skyline Gauntlet (139-150 m). Levels unlock in order. |
| Race the clock | Every level has a hard time limit. Finish fast for **gold / silver / bronze**; run out of time and it's game over. |
| Lives & checkpoints | Each fall or knock-off costs a heart and sends you back to the last checkpoint. No hearts left = game over. |
| Jump | **A** (VR) / **Space** (desktop). Gaps, vaults, moving platforms and a final leap for a helicopter ladder. |
| Hazards | Wind gusts, collapsing planks, shattering skylights and glass bridges, swinging platforms, a sweeping crane boom, falling debris, startled pigeons. |
| Rides | A swinging board on chains, a crane-carried steel beam, a swinging hook pallet, a turning tower-crane jib, a zipline, a window-washer cradle. |
| Score | Time left, lives left, courage stars and tasks, x0.6 on Easy and x1.6 on Hard. Best time and best score per level. |
| Difficulty | **Easy** (5 lives, 50% more time, slower hazards, gentler wind), **Normal** (3 lives), **Hard** (2 lives, less time, faster hazards, stronger wind). |
| Pause menu | **Esc** / **X** / Menu button: Resume, Restart level, Main menu. |
| Pip | A little glowing bird who announces the race, cheers at checkpoints, taunts you when you fall and yells when time is short. |

## The levels

**Park hub (main menu)** - level portals, difficulty picker, medals with best times and scores, trophy wall, help board.

**Level 1 - Rooftop Chase** (chase Kiwi the parrot across the rooftops)
- Jump from the cafe roof to the next building and run over a courtyard of glass skylights that shatter under you
- Ride a board swinging on chains over the street and jump off at the far end of the swing
- Edge along an 85 cm ledge while gusts and pigeons try to knock you off
- Drop down, cross a light well on collapsing planks, vault two walls and jump to the fire escape
- Climb to the top roof and catch Kiwi at the end of a diving plank

**Level 2 - Crane Rush** (beat the storm to the helipad)
- Scaffold ladder, then a plank walkway that collapses under you while steel debris rains down (watch for the orange circles)
- Ride a crane-carried beam up to the slab while a boom sweeps the floor - jump it or be knocked off
- Walk an 18 m beam in the wind, ride a swinging hook pallet to the scaffold tower and climb to the top
- Hop onto the turning tower-crane jib and drop off onto the roof with the helipad

**Level 3 - Skyline Gauntlet** (150 m up)
- A 22 cm steel tightrope between towers in side wind
- A zipline from Tower M down to Tower B - one go per life
- A tilting window-washer cradle lowers you 8 m down the face of the tower
- Sprint over a glass bridge whose panes crack and shatter a moment after you step on them
- Finale: run and jump off the roof for the rope ladder of a hovering helicopter - walking off falls short.
  Catch it and it lifts you away over the city while the fireworks go off.

**Courage stars** float at the riskiest spots (each worth points). **Medals** come from your finish time.

## Controls

| | VR (Quest / PC VR) | Desktop (no headset) |
|---|---|---|
| Move | Left stick | WASD (Shift = sprint) |
| Turn | Right stick | Mouse |
| Jump | A | Space |
| Climb ladders | Grab the rungs (grip) and pull | Look at the ladder, hold W / Space |
| Grab zipline / items | Grip | Left click |
| Press UI | Trigger | Click |
| Crouch (wind) | Really crouch | C |
| Pause menu | X or Menu (left controller) | Esc |
| Free cursor | - | Tab |

Desktop mode switches on automatically when no headset is detected (or start the build with `-desktop`), so the whole
game can be played and presented on a normal laptop. Desktop walking speed equals the VR stick speed, so every jump
that works on a keyboard also works in a headset.

## Graphics

**Real assets (CC0, Poly Haven)** - photographic HDR skies that also light the scenes, real PBR texture sets
(asphalt, concrete, paving, grass, dirt, wood planks, metal plate, rusty grating, gravel, tiles) and photo-scanned props
(air-conditioning units, utility boxes, crates, barrels). Downloaded only from polyhaven.com, every file verified
against Poly Haven's published checksum. See `Assets/AcrophobiaVR/ThirdParty/PolyHaven/LICENSE_PolyHaven_CC0.txt`.
Every course piece uses the same real materials as the rest of the world (wood, concrete, painted steel, grating).

**3D models** - the helicopter and other hero models were generated with Gemini and reviewed before import.

**Baked lighting** - lightmaps with bounced light and ambient occlusion, light probes for moving objects, baked
reflection probes. Re-bake with **Rise Above > Bake Lighting (All Scenes)** after rebuilding scenes.

Building facades use procedurally generated PBR textures (brick / office / glass with lit windows); URP
post-processing per level mood (ACES tonemapping, bloom, colour grading, vignette, SSAO on PC). On Quest the heavy
post-processing and probes switch off automatically (`PlatformGraphics`).

## Sound & feel

All audio is synthesised in code (no audio files) and placed in 3D space: city traffic, crane motors, the helicopter's
rotor, wind that grows with height and surges with gusts, footsteps matching the surface, creaking planks, glass that
cracks and shatters under you, countdown and "hurry" beeps in the last 10 seconds. Controller **haptics** for grabs,
landings, gusts, cracking glass, the zipline and slips. Master volume on the main menu.

## Installing on Meta Quest

1. Enable **Developer Mode** for the headset (Meta Horizon phone app > Devices > Developer Mode).
2. Connect the Quest to the PC with a USB-C cable and accept the "Allow USB debugging" prompt inside the headset.
3. Install the APK, either:
   - with **SideQuest** (drag `Builds\Quest\RiseAboveVR.apk` onto it), or
   - with ADB: `adb install -r E:\Unity_project\Builds\Quest\RiseAboveVR.apk`
     (ADB ships with Unity: `E:\UnityEditors\6000.3.25f1\Editor\Data\PlaybackEngines\AndroidPlayer\SDK\platform-tools\adb.exe`).
4. In the headset: **Library > Unknown Sources > Rise Above VR**.
5. Play standing in a cleared guardian area (room-scale) - or seated. Left **X** = pause menu at any time.

Settings used for Quest: IL2CPP + ARM64, Vulkan, ASTC textures, min Android API 32 (Quest 2 / Pro / 3 / 3S),
OpenXR single-pass instanced (multiview), foveated rendering, Meta Quest Support + Touch controller profiles, the
"Performance" URP quality level (`PlatformGraphics`, `QuestPerformance`). Re-apply with **Rise Above > Configure for Meta Quest**.

## Ready-made builds

| Build | Where | How to run |
|---|---|---|
| Windows (PC, desktop mode or PC VR) | `E:\Unity_project\Builds\Windows\RiseAboveVR.exe` | Double-click. With no headset it starts in desktop mode; with Quest Link / SteamVR running it starts in VR. Add `-desktop` to force desktop mode. |
| Meta Quest (standalone) | `E:\Unity_project\Builds\Quest\RiseAboveVR.apk` | See *Installing on Meta Quest* above. |

## Running it in Unity

1. Open the folder `RiseAboveVR` with **Unity 6000.3.25f1** (Unity 6 LTS).
2. Menu **Rise Above > Build All Scenes** (re-run after changing level code), then **Rise Above > Bake Lighting (All Scenes)**.
3. Open `Assets/AcrophobiaVR/Scenes/MainMenu.unity` and press **Play**.

**Course tests** - `CourseTests` (Editor) drives the desktop rig with simulated keys through every section of every
level at VR walking speed and logs whether each jump / ride / crossing works: `CourseTests.Run(CourseTests.Level3())`.

## Data for the report

Every session appends to `acrophobia_log.csv` in `Application.persistentDataPath`
(menu **Rise Above > Open Session Log Folder**). Columns: `session,timestamp,level,event,value` - level finishes and
times, slips, checkpoints, courage stars, objectives.

## Code map

```
Assets/AcrophobiaVR/
  Scripts/Core       GameManager (levels, unlocks, scene fades), PlayerRig, Difficulty, ProgressStore (medals, best
                     times/scores), Achievements, SessionLogger
  Scripts/Gameplay   LevelController (race clock, lives, medals, score), FallGuard, checkpoints, objectives, BalanceBeam,
                     Ladder, GustZone, Companion (Pip), CourageStar
  Scripts/Hazards    Hazard base + PathMover, Pendulum, Sweeper, Carrier (ride moving things), HitBox, CollapsingPlatform,
                     DebrisDropper, Zipline, ChaseObjective, HeliLadderCatch
  Scripts/UI         Runtime-built world-space UI: HUD, dialogs, pause menu, main menu, records wall
  Scripts/Ambient    Procedural audio (all sounds synthesised - no audio files), particles, birds, traffic, fireworks
  Scripts/Desktop    Keyboard + mouse fallback rig (run, sprint, jump)
  Editor/            LevelBuilder + Level*Course - generate every scene from code (Rise Above menu); CourseTests
```

## Safety note

This is a student project. Anyone with epilepsy, motion sickness or heart conditions should take care. Play standing
in a clear space, or seated.
