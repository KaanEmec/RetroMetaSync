Below is a **new standalone document** you can append to your project as a separate reference file (e.g., `retro-library-detection-guideline.md`).  
It is written explicitly for a **development AI agent** whose task is to classify an unknown directory tree into one of the supported retro library ecosystems.

Citations refer to your previously uploaded reference documents.

---

# **Retro Library Structure Detection Guide**

**How to identify which retro emulation ecosystem a given directory belongs to**

**Purpose:**  
Given an arbitrary directory tree, determine which retro emulation system (OS/frontend/ecosystem) it most likely belongs to — without executing code and without relying on external configuration.

This guide defines a **systematic detection methodology** based on structural fingerprints, metadata files, media layouts, and configuration artifacts.

---

# **1\. Detection Philosophy**

Every ecosystem leaves structural fingerprints in at least one of these categories:

1. **Metadata format and location**  
2. **Media folder taxonomy**  
3. **ROM root conventions**  
4. **Configuration file signatures**  
5. **Database or playlist artifacts**

Use a layered approach:

1. Identify **global root clues** (e.g., `LaunchBox/`, `ES-DE/`, `RetroBat/`)  
2. Look for **metadata format signatures** (`gamelist.xml`, `.lpl`, `Platforms.xml`, `.txt romlists`)  
3. Inspect **media directory contracts**  
4. Confirm via **config files unique to the ecosystem**

Never rely on a single file unless it is uniquely identifying (e.g., `retrobat.ini`).

---

# **2\. High-Level Family Classification**

Before detecting exact systems, classify the directory into one of these structural families (see ecosystem families in your reference ):

| Family | Primary Indicator |
| ----- | ----- |
| **EmulationStation (ES) family** | Presence of `gamelist.xml` per system |
| **ES-DE family** | Central `ES-DE/gamelists/` \+ `downloaded_media/` |
| **Windows launcher (LaunchBox)** | `LaunchBox/Data/Platforms/*.xml` or SQLite |
| **RetroArch playlist-driven** | `.lpl` playlists \+ `thumbnails/` |
| **Attract-Mode** | `romlists/*.txt` \+ `attract.cfg` |
| **Pegasus** | `metadata.pegasus.txt` or `media/<game>/boxFront.*` |
| **OnionOS / handheld minimal** | `Roms/<SYS>/Imgs/` \+ `miyoogamelist.xml` |

Proceed to system-level detection only after family classification.

---

# **3\. EmulationStation (Classic) Detection**

## **Structural Indicators**

Look for:

* `gamelist.xml` inside system folders  
* OR under `~/.emulationstation/gamelists/<system>/`  
* Presence of `~/.emulationstation/es_systems.cfg`

## **Typical Patterns**

* ROMs under `roms/<system>/`  
* Media referenced inside `gamelist.xml`  
* Image/video paths may be:  
  * Absolute  
  * `./` relative  
  * `~/` relative

## **Detection Heuristic**

If:

* Multiple `gamelist.xml` files exist inside system directories  
* Media paths are stored directly inside XML entries  
* There is an `.emulationstation` directory

→ Classify as **Classic EmulationStation family (RetroPie-style)**

---

# **4\. Batocera Detection**

Batocera is an EmulationStation fork but has very specific layout conventions.

## **Unique Structural Fingerprints**

* `/userdata/roms/<system>/gamelist.xml`  
* Media folders inside each system:  
  * `images/`  
  * `videos/`  
  * `manuals/`  
* Asset suffix naming:  
  * `<rom>-image.png`  
  * `<rom>-thumb.png`  
  * `<rom>-marquee.png`  
  * `<rom>-video.mp4`  
  * `<rom>-bezel.png`

## **Detection Rule**

If:

* Each system folder contains `gamelist.xml`  
* Media files use `-image`, `-thumb`, `-marquee` suffix pattern  
* ROM root resembles `/userdata/roms/`

→ Classify as **Batocera**

---

# **5\. RetroBat Detection (Windows ES-Family Variant)**

RetroBat resembles Batocera but differs in media organization.

## **Unique Indicators**

* Root folder named `RetroBat`  
* `retrobat.ini` present  
* Media organized as:

roms/\<system\>/images/boxart/  
roms/\<system\>/images/wheel/  
roms/\<system\>/images/video/

Rather than flat suffix naming

* `gamelist.xml` per system

## **Detection Rule**

If:

* `retrobat.ini` exists  
* Media is deeply categorized under `images/boxart`, `images/wheel`, etc.  
* Structure lives under `RetroBat/roms/`

→ Classify as **RetroBat**

---

# **6\. ES-DE Detection (Desktop / Steam Deck)**

ES-DE diverges from classic EmulationStation in one critical way:

Media is NOT resolved via `<image>` tags in `gamelist.xml`.

## **Unique Structural Fingerprints**

* `ES-DE/` directory exists  
* `ES-DE/gamelists/<system>/gamelist.xml`  
* `ES-DE/downloaded_media/<system>/` with subfolders:  
  * `covers`  
  * `screenshots`  
  * `marquees`  
  * `manuals`  
  * `videos`  
  * `3dboxes`  
  * `backcovers`  
  * etc.

## **Media Matching Model**

Media matched by **filename mirroring**, not XML path reference

## **Detection Rule**

If:

* Centralized `downloaded_media/<system>/covers/`  
* Centralized `gamelists/<system>/gamelist.xml`  
* Media filenames exactly match ROM basenames  
* XML lacks explicit media paths or they are ignored

→ Classify as **ES-DE**

---

# **7\. LaunchBox Detection**

LaunchBox is fundamentally different.

## **Unique Structural Fingerprints**

* `LaunchBox/` root folder  
* `LaunchBox/Data/Platforms/<platform>.xml`  
* OR `Metadata.sqlite` database  
* Media stored in:  
  * `LaunchBox/Images/<Platform>/Box - Front/`  
  * `Clear Logo`  
  * `Screenshot - Gameplay`  
  * etc.

## **Distinguishing Behavior**

* Media association via title matching (not path references)  
* XML contains fields like `<ApplicationPath>` and `<DatabaseID>`

## **Detection Rule**

If:

* Metadata under `Data/Platforms/*.xml`  
* Media organized by platform \+ media category  
* No per-system `gamelist.xml`

→ Classify as **LaunchBox**

---

# **8\. Attract-Mode Detection**

Attract-Mode does NOT use XML.

## **Unique Structural Fingerprints**

* `attract.cfg`  
* `romlists/*.txt`  
* `emulators/*.cfg`

## **Romlist Format**

* Semicolon-separated rows  
* Header begins with:  
  `#Name;Title;Emulator;CloneOf;Year;Manufacturer;Category;Players;...`

## **Artwork Configuration**

Defined inside emulator `.cfg` files using labels like:

* flyer  
* snap  
* marquee  
* wheel

## **Detection Rule**

If:

* No `gamelist.xml`  
* `.txt` romlists exist  
* `attract.cfg` present

→ Classify as **Attract-Mode**

---

# **9\. Pegasus Detection**

## **Indicators**

* `metadata.pegasus.txt`  
* OR `media/<gamename>/boxFront.jpg` style directory

Pegasus supports both explicit metadata and folder-discovery modes

## **Detection Rule**

If:

* `metadata.pegasus.txt` exists  
* OR media organized under `media/<game>/boxFront.*`

→ Classify as **Pegasus**

---

# **10\. RetroArch Detection**

RetroArch is playlist-driven.

## **Unique Indicators**

* `.lpl` playlist files  
* `thumbnails/<system>/Named_Boxarts/`  
* `/config/<core>/` override configs

## **Detection Rule**

If:

* `.lpl` files exist  
* No `gamelist.xml`  
* Thumbnails organized by `Named_Boxarts`, `Named_Snaps`, `Named_Titles`

→ Classify as **RetroArch playlist ecosystem**

---

# **11\. OnionOS Detection**

## **Unique Indicators**

* `Roms/<SYS>/Imgs/` folder  
* `miyoogamelist.xml`  
* Short uppercase system folder names:  
  * `FC`  
  * `SFC`  
  * `MD`  
  * `PS`

## **Detection Rule**

If:

* `Imgs/` exists inside each system  
* Metadata file is `miyoogamelist.xml`  
* Case-sensitive system naming

→ Classify as **OnionOS**

---

# **12\. muOS Detection**

## **Unique Indicators**

* `MUOS/info/catalogue/<system>/box/`  
* `MUOS/info/catalogue/<system>/preview/`

No `gamelist.xml` required.

## **Detection Rule**

If artwork lives under `MUOS/info/catalogue/...`

→ Classify as **muOS**

---

# **13\. AmberELEC / JELOS / ROCKNIX Detection**

These are ES-family but with specific SD-card conventions.

## **Indicators**

* `roms/<system>/gamelist.xml`  
* SD-card mounted structure  
* System folder naming variations (e.g., `genesis` vs `megadrive`)

## **Detection Rule**

If:

* ES-style layout  
* Root resembles SD-card style `/roms/`  
* Naming reflects handheld conventions

→ Classify as **Handheld ES-family (AmberELEC/JELOS/ROCKNIX)**

---

# **14\. Decision Tree Summary**

1. If `.lpl` → RetroArch  
2. If `metadata.pegasus.txt` → Pegasus  
3. If `attract.cfg` \+ `romlists/` → Attract-Mode  
4. If `LaunchBox/Data/Platforms/` → LaunchBox  
5. If `ES-DE/downloaded_media/` → ES-DE  
6. If `retrobat.ini` → RetroBat  
7. If `Roms/<SYS>/Imgs/` \+ `miyoogamelist.xml` → OnionOS  
8. If `MUOS/info/catalogue/` → muOS  
9. If `roms/<system>/gamelist.xml` → ES-family  
   * If suffix naming → Batocera  
   * If deep `images/boxart/` → RetroBat  
   * If `.emulationstation/` home tree → RetroPie

---

# **15\. Final Recommendation for AI Agent**

When classifying:

1. Build a **confidence score per ecosystem**  
2. Weight:  
   * Unique config files highest  
   * Metadata format second  
   * Media structure third  
   * Naming conventions last  
3. If two ecosystems share identical structure (e.g., Batocera vs KNULLI):  
   * Default to broader family classification (ES-family)  
   * Do not over-specify unless additional fingerprint is found

---

If you want, I can now:

* Add this as a **fully formatted `.md` file**  
* Add a **confidence scoring model**  
* Add a **structured YAML classification schema**  
* Or produce a **machine-readable decision table for an AI agent**

