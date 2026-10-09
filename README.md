# Rise Above - a sky-high VR adventure

End-of-year project. A three-level virtual-reality game built in Unity 6 for **Meta Quest** (and playable on a
normal PC without a headset). It's a fun, tense game about heights: no railings, real falls, three lives,
tasks, puzzles, wind, a companion and stars to collect. Fear of heights is the *theme* - the game simulates what
vertigo feels like from inside your head - but the goal is a game that's fun to play and to watch.

## How it plays

| Feature | What it means in the game |
|---|---|
| Three levels, rising | 6-13 m cafe balcony & roof -> 25-31 m construction site -> 150 m skyscraper. Levels unlock in order. |
| No railings | On **Normal** and **Hard** every edge is open - one wrong step and you really fall (a second of rushing air, then the screen goes dark). |
| 3 lives | Each fall costs a heart and returns you to the last checkpoint. Lose all three = game over, try again. |
| Hazards | Wind gusts that shove you (crouch to hold on), crumbling tiles, cracking glass, a loose see-saw board, startled pigeons, a helicopter's downdraft. |
| Tasks & puzzles | Water flowers over the edge, rescue a parrot and a cat, weigh down a loose board, plant a flag on a crane, ring a rooftop bell. |
| Score & stars | Points for tasks, courage stars, lives left and speed (x1.5 on Hard). Best score per level. 3 stars: finish, no falls, all courage stars. |
| Difficulty | **Easy** (railings, safety glass, fog hides the drop), **Normal** (no railings), **Hard** (narrower paths, stronger wind, clear air). |
| Pause menu | **Esc** / **X** / Menu button: Resume, Calm Meadow, Restart level, Main menu. |
| Pip | A little glowing bird who flies in to explain things (and to help in a panic), then flies off - no HUD clutter. |
| Optional anxiety log | Off by default. Turn it on in the main menu to rate anxiety 0-10 before/after each level (for demos/research). |

## Feeling the fear - the player's point of view

The **Fear System** simulates acrophobia from inside the player's head:

- Fear is measured realistically: rays sample the drop *around and below the head* (standing on a 30 cm beam at 150 m
  is very different from standing behind a railing at 6 m) and *where the player is looking* - glass floors don't count as ground.
- **Looking down into the drop** makes it surge: tunnel vision closes in, colour drains, chromatic shimmer, a vertigo
  "dolly-zoom" (desktop), a pounding heartbeat you hear and feel in the controllers, and a live **BPM** readout (70 -> 170).
- Hold your gaze at maximum fear and a **panic wave** hits: the edges pulse red, a ringing tone, Pip flies *above your head*
  and the HUD shouts **LOOK UP**. Looking at the sky calms you down; freezing without looking up for too long = slip.
- **Coping tools**: look up, crouch, breathe with the guide, the Calm Meadow. Finishing a task or reaching a checkpoint gives relief.
- The look-down tasks become a push-and-pull: stare at the target while your heart races, look up to recover, look down again.
  Task progress freezes while you are panicking - exactly the approach / cope / approach loop used in exposure therapy.
- The level summary and CSV log record **peak heart rate** and **panic waves beaten** (`peak_bpm`, `panics_beaten`, `panic_start`, `panic_recovered_seconds`, `panic_froze`).

## Graphics

**Real assets (CC0, Poly Haven)** - 4 photographic HDR skies (sunset, noon, golden hour, park) that also light the
scenes, and 10 real PBR texture sets (asphalt, concrete, paving, grass, dirt, wood planks, metal plate, rusty grating,
gravel, tiles) with normal and roughness maps. Downloaded only from polyhaven.com, every file verified against Poly
Haven's published MD5 checksum. See `Assets/AcrophobiaVR/ThirdParty/PolyHaven/LICENSE_PolyHaven_CC0.txt`.

**Baked lighting** - lightmaps with bounced light and ambient occlusion, light probes for moving objects, baked
reflection probes (cheap enough to keep on Quest). Re-bake with **Rise Above > Bake Lighting (All Scenes)** after
rebuilding scenes (about 1.5 minutes for all four).

**Before that (still used for building facades)**:

Procedurally generated PBR textures (brick / office / glass facades with lit windows, concrete, asphalt, paving, wood,
brushed metal, grating, gravel - all with normal maps) tiled at real-world scale, URP post-processing per level mood
(ACES tonemapping, bloom, colour grading, white balance, vignette, SSAO on PC), soft shadows, reflection probes, detailed
props (cars with wheels and lights, layered trees, street lamps, benches, people, rooftop machinery). On Quest the heavy
post-processing and probes switch off automatically (`PlatformGraphics`).

## Extra features

- **Courage Elevator (free practice)** - a glass lift in the park (to your right at the start). Press UP / DOWN / STOP and
  ride to any height up to 120 m, at your own pace. Pip comments at 10, 25, 50 and 100 m; your best height is saved.
  This is self-paced graded exposure: the player decides how high to go.
- **Brave Photos** - press **B** on the right controller (or **F** on the keyboard) to take a photo from where you stand.
  Photos taken high up (or while your heart is racing) count as *brave photos*. Saved to `<persistentDataPath>/Photos`.
- **Achievements** - 12 badges (First Look Down, Glass Walker, Rode the Wave, Steady Feet, Star Collector, Rise Above,
  Sky High, Brave Soul, Cat Rescuer, Calm Breather, Photographer, Cloud Walker) with golden pop-ups.
- **My Progress** (button on the main menu) - your last sessions (anxiety before/after, peak BPM, panic waves beaten,
  slips), the achievements grid, totals, and **Export report** which writes `RiseAbove_Report.html` with tables and
  bar charts - ready to put in the project report.
- **Fear muffles hearing** - at high fear the world sounds dull and distant while your heartbeat stays clear.

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
"Performance" URP quality level, post-processing and reflection probes switched off on device (`PlatformGraphics`,
`QuestPerformance`). Re-apply any time with **Rise Above > Configure for Meta Quest**.

## Sound & feel

All audio is synthesised in code (no audio files) and placed in 3D space:

- **World sounds**: a busker playing guitar, splashing fountains, cafe chatter, passing cars (engine + Doppler), lift and crane
  motors that run only while moving, bird flocks chirping below you - attached automatically to the right objects (`SceneAudioDresser`).
- **Footsteps** that match the surface (concrete, wood, metal grating, glass, grass) and **creaking planks / beams / rope bridge**
  that groan louder the more you wobble - high up, even a steady plank occasionally creaks.
- **Positional one-shots**: glass cracks and shatters under your feet, the lift clunks, Pip chirps from where Pip flies, the cat meows
  from the cat, fireworks boom from the sky.
- **Wind** grows with height and surges with gusts; the **heartbeat** follows your BPM; the **breathing guide** breathes with you.
- **Haptics** (controller rumble): heartbeat at high fear, grabbing items, pressing buttons, glass cracking/shattering, wind gusts,
  wobbling on a beam, lift jolts, slips, courage stars, pouring water.
- **Master volume** control on the main menu (saved between sessions).

## The levels

**Park hub (main menu)** - level portals, difficulty picker, best times and scores, trophy wall, help board.

**Level 1 - The Sunset Cafe (6 m balcony -> 13 m roof)**
- Water three flowers on a shelf hanging over the street (grab the can by its handle, tilt to pour)
- Look down and find the street musician, the fountain and a dog on a walk (hold your gaze)
- Walk the glass skywalk - the glass cracks while you stand on it, so keep moving
- Rescue Kiwi the parrot from a 40 cm window ledge: step over a crumbled gap while pigeons burst out at you
- Climb the fire-escape ladder to the roof terrace at 13 m - no parapet, and gusts push you towards the street
- Ring the bell on the roof to finish

**Level 2 - Construction site (25-31 m)**
- Ride an open lift with no rails that *stalls halfway*
- The hammer sits at the end of a **loose board** sticking out over the edge: walk out on it and it see-saws and
  tips you off - weigh down the inner end with the cement bag first
- Gusts sweep the open roof, collect the other tools near the edges
- Cross a wobbling plank bridge (balance meter), climb a ladder hand-over-hand
- Walk the crane catwalk in the wind and plant the topping-out flag
- Ride a steel beam hanging from the crane across to the next roof

**Level 3 - Skyscraper (150 m)**
- No parapets - just a kerb and 150 m of air
- Cross a steel beam between towers while wind gusts hit - crouch to resist
- Run over loose tiles that crumble a moment after you step on them
- Cross a swaying rope bridge with a snapped hand rope and broken planks - and a **helicopter** thunders past
  mid-crossing; crouch or its downdraft knocks you off
- Walk a plank to rescue Mittens the cat, then launch the fireworks finale

**Stars** per level: finish (1) + no falls (1) + all Courage Stars (1). Courage Stars float at the scariest spots.
**Score**: 500 per task, 250 per courage star, 400 per life left, plus a time bonus (x1.5 on Hard, x0.6 on Easy).

## Controls

| | VR (Quest / PC VR) | Desktop (no headset) |
|---|---|---|
| Move | Left stick | WASD (Shift = careful steps) |
| Turn / teleport | Right stick | Mouse |
| Grab / climb | Grip | Left click (Space to climb) |
| Press UI | Trigger | Click |
| Pour watering can | Tilt it | Hold right mouse |
| Crouch (wind) | Really crouch | C |
| Pause menu (Resume / Calm Meadow / Restart / Main menu) | X or Menu (left controller) | Esc |
| Heart rate | Look at your left wrist (watch, also shows lives) | Appears when it races; H = always show |
| Free cursor | - | Tab (hold right mouse to look while free) |

Desktop mode switches on automatically when no headset is detected (or start the build with `-desktop`),
so the whole game can be played and presented on a normal laptop.

## Ready-made builds

| Build | Where | How to run |
|---|---|---|
| Windows (PC, desktop mode or PC VR) | `E:\Unity_project\Builds\Windows\RiseAboveVR.exe` | Double-click. With no headset it starts in desktop mode. With Quest Link / SteamVR running it starts in VR. Add `-desktop` to force desktop mode. |
| Meta Quest (standalone) | `E:\Unity_project\Builds\Quest\RiseAboveVR.apk` | Enable Developer Mode on the Quest, connect by USB, then `adb install -r RiseAboveVR.apk` (or drag it into SideQuest). Find it under *Unknown Sources*. |

Screenshots from the play-test are in the `Screenshots/` folder (good for the report/presentation).

## Running it in Unity

1. Open the folder `RiseAboveVR` with **Unity 6000.3.25f1** (Unity 6 LTS).
2. Menu **Rise Above > Build All Scenes** (already done once - re-run after changing level code).
3. Open `Assets/AcrophobiaVR/Scenes/MainMenu.unity` and press **Play**.

**Meta Quest (standalone):** File > Build Profiles > Android > Switch Platform, connect the Quest (developer mode on), Build And Run.
**PC VR (Quest Link / SteamVR):** Build Profiles > Windows, enable OpenXR in Project Settings > XR Plug-in Management, Build.

## Data for the report

Every session appends to `acrophobia_log.csv` in `Application.persistentDataPath`
(menu **Rise Above > Open Session Log Folder**). Columns: `session,timestamp,level,event,value`.
Events include `anxiety_before`, `anxiety_after`, `level_complete_seconds`, `slip`, `calm_meadow_enter`,
`calm_meadow_exit_seconds`, `checkpoint`, `courage_star`, `objective_complete`, `exposure_mode`, `lift_stall`.
Open it in Excel to chart anxiety before vs after each level across sessions.

## Code map

```
Assets/AcrophobiaVR/
  Scripts/Core       GameManager (levels, unlocks, scene fades), PlayerRig, ExposureSettings, ProgressStore, SessionLogger
  Scripts/Gameplay   LevelController, objectives (look-down, collect, water, deliver, reach, press), hazards
                     (BalanceBeam, CrackingGlass, CrumblingTile, MovingPlatform, Ladder), SafeRoom, Companion, CourageStar
  Scripts/UI         Runtime-built world-space UI: HUD, rating panel, breathing guide, dialogs, menu, trophy graph
  Scripts/Ambient    Procedural audio (all sounds synthesised - no audio files), particles, birds, traffic, fireworks
  Scripts/Desktop    Keyboard + mouse fallback rig
  Editor/            LevelBuilder - generates all 4 scenes from code (Rise Above menu)
```

Everything is built from Unity primitives and synthesised sound - there are no third-party assets.

## Safety note

This is a student project, not a medical device. Anyone with severe acrophobia, epilepsy, motion sickness or
heart conditions should use it only with appropriate support. Play standing in a clear space, or seated.