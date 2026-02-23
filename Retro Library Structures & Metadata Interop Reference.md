# Retro Library Structures & Metadata Interop Reference

*Last updated: 2026-02-23*

**Goal:** A practical, converter-friendly reference that documents how major modern retro emulation OSes/frontends/ecosystems store **ROMs**, **metadata**, and **media assets** (box art, marquees, videos, manuals, bezels, etc.), so a developer agent can **translate libraries between systems** or build new libraries from scratch.

---

## Contents

1. [Normalized model used in this doc]

2. [Asset types and file-format cheat sheet]

3. [Families of ecosystems]

4. [System-by-system specifications]
   4.1 [EmulationStation “classic” (RetroPie-style)]
   4.2 [Batocera]
   4.3 [KNULLI]
   4.4 [AmberELEC]
   4.5 [JELOS / ROCKNIX]
   4.6 [ArkOS]
   4.7 [OnionOS (Miyoo Mini family)]
   4.8 [muOS (MustardOS)]
   4.9 [ES-DE (EmulationStation Desktop Edition)]
   4.10 [EmuDeck (SteamOS ecosystem)]
   4.11 [RetroDECK]
   4.12 [RetroBat]
   4.13 [LaunchBox / Big Box]
   4.14 [Attract-Mode]
   4.15 [Pegasus Frontend]
   4.16 [RetroArch (playlists, thumbnails, overlays)]

5. [Conversion cookbook]

6. [Mapping tables]

7. [Format‑specific patterns (XML, SQL, DAT)]

8. [Validation checklist]

---

## Normalized model used in this doc

To convert between systems, it helps to normalize everything into a single internal schema. Use the following model:

### 1\) System (platform)

Represents a platform/collection like snes, psx, arcade, etc.

* **system\_id**: canonical ID you choose (e.g., snes, psx, mame)

* **display\_name**

* **rom\_root**: where ROMs live for this system

* **asset\_roots**: where each asset type lives (if system supports splitting)

* **metadata\_source**: how metadata is stored (XML, SQLite, plaintext, etc.)

### 2\) Game (content entry)

* **rom\_path**: absolute or relative to rom\_root

* **title**

* **sort\_title** (optional)

* **regions / languages** (optional)

* **release\_date**

* **genres, developer, publisher**

* **rating / favorite / playcount / lastplayed** (optional)

* **assets**: list of asset references

### 3\) Asset (media file)

Each asset has: \- **asset\_type** (normalized type list below) \- **file\_path** \- **format** (png/jpg/mp4/pdf…) \- **match\_key** (how it is associated to the ROM: “same basename”, “explicit path in XML”, etc.)

**Converter principle:** Treat ROM filenames and *stable IDs* (CRC/MD5/ScreenScraper IDs) as your ground truth, and treat UI-specific media (miximages, wheels, themes) as derived artifacts.

---

## Asset types and file-format cheat sheet

### Normalized asset types

Use these in your internal representation and map to each system:

* box\_front, box\_back, box\_spine

* disc

* screenshot\_gameplay, screenshot\_title, screenshot\_menu

* marquee / wheel / logo (system dependent naming)

* fanart / background

* miximage (composite image, often “box+shot+logo”)

* video (usually gameplay preview)

* manual

* bezel (bezel image) and overlay\_cfg (RetroArch overlay config)

### Common file formats

* Images: .png, .jpg/.jpeg (PNG preferred for transparency and marquees)

* Videos: .mp4 (most common), sometimes .mkv

* Manuals: .pdf (sometimes .cbz/.cbr in some setups)

* Overlays: .cfg \+ .png

---

## Families of ecosystems

Most “retro OS” stacks fall into a few library-layout families:

1. **EmulationStation (ES) gamelist family**  
   Uses gamelist.xml plus per-system media folders. Examples: Batocera, RetroPie, AmberELEC, JELOS/ROCKNIX, ArkOS, KNULLI.

2. **ES-DE family (desktop/Steam Deck)**  
   ES-DE stores gamelists centrally and stores media in a typed folder tree (covers/screenshot/etc.).

3. **Windows launcher family**  
   LaunchBox, RetroBat, Playnite (not detailed), etc. RetroBat is ES-family; LaunchBox is its own.

4. **Arcade-cabinet frontends**  
   Attract-Mode is the major one here.

5. **RetroArch-first**  
   Uses playlists (.lpl) \+ thumbnails folder structure and optional overlays.

---

# System-by-system specifications

## EmulationStation “classic” (RetroPie-style)

### Type

Frontend \+ config convention used by RetroPie and many ES-based distributions.

### ROM root

Common RetroPie convention is per-system folders under a single ROM root (e.g., \~/RetroPie/roms/\<system\>).

### Media \+ metadata locations (default RetroPie behavior)

* **Gamelists:** \~/.emulationstation/gamelists/\<system\>/gamelist.xml

* **Downloaded images:** \~/.emulationstation/downloaded\_images/\<system\>/...  
  RetroPie documentation describes the scraped metadata/images living under the EmulationStation home directory. 

Some setups also support a gamelist.xml directly inside the ROM folder, depending on how ES is configured; treat this as a “variant mode” rather than the canonical RetroPie default. 

### Typical media types

Depends on theme support, but commonly: \- image (box art or screenshot) \- video \- marquee

### Naming & path rules

* Media file names are usually **ROM basename \+ extension** chosen by the scraper.

* gamelist.xml usually stores **paths** to images/videos (often relative such as ./downloaded\_images/... or absolute).

### Key config files

* \~/.emulationstation/es\_systems.cfg defines systems, ROM paths, extensions, launch commands. 

* \~/.emulationstation/es\_settings.cfg stores UI settings (booleans/strings).

### Converter notes

* Treat es\_systems.cfg as the source of truth for **which folder maps to which system**.

* If your input library has media folders next to ROMs, you can rewrite \<image\>/\<video\> paths accordingly.

* Watch out for **subfolders**: ES will index ROM subdirectories under \<path\>; relative paths inside gamelist.xml must remain resolvable.

---

## Batocera

### Type

Linux retro OS \+ EmulationStation-based frontend.

### ROM root (core idea)

Batocera’s default structure is a system folder under /userdata/roms/\<PLATFORM\> with a gamelist.xml and a few standard media folders. A scraper/frontends reference notes Batocera’s default media locations as /userdata/roms/\<PLATFORM\>/images, /userdata/roms/\<PLATFORM\>/videos, and /userdata/roms/\<PLATFORM\>/manuals with gamelist.xml in the platform folder. 

### Media folders (typical)

Inside each system folder: \- images/ \- videos/ \- manuals/ (if used)

### Media naming convention (important)

A Batocera (batocera-emulationstation) issue shows a common pattern where gamelist.xml points to files like: \- ./images/\<rom\>-image.png \- ./images/\<rom\>-thumb.png \- ./images/\<rom\>-marquee.png \- ./videos/\<rom\>-video.mp4 \- ./images/\<rom\>-bezel.png 

This “suffix style” is **very converter-friendly** because you can deterministically derive asset filenames from the ROM basename.

### Metadata file

* \<system\_folder\>/gamelist.xml (one per system)

### System definitions

Batocera has an es\_systems.cfg in /usr/share/emulationstation, with supported customization paths (older approach vs newer customization methods). 

### Converter notes

* If you’re converting from ES-DE → Batocera: create /userdata/roms/\<system\>/images, /videos, /manuals and write gamelist.xml with **relative paths** like ./images/....

* If you’re converting from Batocera → ES-DE: you can parse the suffixes to infer asset types (\-image, \-thumb, \-marquee, \-bezel, \-video).

---

## KNULLI

### Type

Handheld-focused OS (commonly described as Batocera-derived).

### ROM root (typical SD-card structure)

A community notes repository describes a share partition containing: \- share/bios/ \- share/roms/ with per-emulator/system folders. 

### Media \+ metadata

KNULLI is EmulationStation-based, so it generally uses per-system gamelist.xml plus per-system media folders (very similar to Batocera). A KNULLI issue describes scraped artwork entries in gamelist.xml pointing to files in an images folder. 

### Converter notes

* In practice, treat KNULLI as “Batocera-style EmulationStation library” unless your target device’s KNULLI build documents a different per-system subfolder naming.

---

## AmberELEC

### Type

Handheld OS using EmulationStation.

### Metadata \+ media (high-level)

AmberELEC documentation covers importing or managing “gamelists and media” for EmulationStation. 

### Converter notes

* AmberELEC tends to be ES-family compatible: if you can produce gamelist.xml \+ per-system media folders (or the expected ES home media folders), it usually works.

* Because AmberELEC can change defaults across releases/builds, a robust converter should support:

* **media-in-ROM-tree** mode (Batocera-like)

* **media-in-ES-home** mode (RetroPie-like)

---

## JELOS / ROCKNIX

### Type

Handheld OS lineage: JELOS → ROCKNIX (ROCKNIX is actively documented).

### ROM root (ROCKNIX)

ROCKNIX documentation states games are nested into a directory on the games card called roms, and games found in this path are available. 

### Metadata \+ media

Most builds are EmulationStation-family and use gamelist.xml per system plus a media folder structure; exact defaults can vary by build.

### Converter notes

* Assume **ES-family** and make your output configurable:

* roms/\<system\>/gamelist.xml \+ images/, videos/, manuals/ (Batocera-style), or

* .emulationstation/gamelists/\<system\> \+ .emulationstation/downloaded\_\* (RetroPie-style).

---

## ArkOS

### Type

Handheld OS using EmulationStation.

### Common layout seen in the field

ArkOS variants often use a top-level games card directory such as EASYROMS/\<system\>/... and may store scraper output into per-system downloaded\_images and downloaded\_videos directories adjacent to ROMs. 

### Converter notes

* When targeting ArkOS, be prepared to:

* place media under EASYROMS/\<system\>/downloaded\_images and .../downloaded\_videos (one common pattern), and/or

* embed relative paths in gamelist.xml accordingly.

---

## OnionOS (Miyoo Mini family)

### Type

Handheld OS with its own ROM \+ metadata conventions (not ES).

### ROM root

Roms/ at the root of the SD card, with subfolders per system.

### Media storage (box art)

OnionOS documentation indicates scraped images are stored inside each system folder under Imgs/ and use the same basename as the ROM. 

Example: \- ROM: Roms/SNES/Super Mario World.zip \- Image: Roms/SNES/Imgs/Super Mario World.png

### Metadata file

OnionOS uses a system-local XML file: \- Roms/\<system\>/miyoogamelist.xml 

### Converter notes

* OnionOS is excellent for deterministic conversion:

* Image association is by **same filename** in Imgs/.

* Metadata is in miyoogamelist.xml (separate from EmulationStation gamelist schema).

---

## muOS (MustardOS)

### Type

Handheld OS with a simple artwork convention.

### Artwork location \+ naming

Official muOS documentation says artwork must be placed under: \- MUOS/info/catalogue/\<system\>/box/ for box art \- MUOS/info/catalogue/\<system\>/preview/ for preview images/screenshots and filenames must match the content filename. 

### Converter notes

* This is a “pure filename match” system: no XML is required for basic artwork.

* For conversion from ES-family, you can:

* choose which ES image asset becomes box/ (often box\_front / image),

* map screenshot\_gameplay or miximage to preview/.

---

## ES-DE (EmulationStation Desktop Edition)

### Type

Cross-platform frontend; widely used on desktop \+ Steam Deck setups.

### Key difference vs classic EmulationStation

ES-DE stores **gamelists centrally** and stores media in a typed folder tree under a single “downloaded media” root.

### Gamelist storage

ES-DE user guide notes gamelists are stored as: \- \~/ES-DE/gamelists/\<system\>/gamelist.xml and *not* necessarily next to ROMs. 

### Media storage

ES-DE user guide lists supported media directories under a “downloaded media” root, including: covers, screenshots, titlescreens, marquees, 3dboxes, backcovers, fanart, manuals, videos, miximages, etc. 

### Naming & association

ES-DE generally associates media by **matching filenames** within the appropriate media-type folder (and may not rely on \<image\> tags inside gamelist.xml in the same way classic ES does). 

### Converter notes

* ES-DE is a great “hub format” because each asset type has a dedicated folder.

* Recommended converter approach: 1\) Normalize to internal schema  
  2\) Emit ES-DE media into downloaded\_media/\<system\>/\<type\>/rom\_basename.(png/mp4/pdf)  
  3\) Emit gamelist.xml containing text metadata (titles/descriptions/release info).

---

## EmuDeck (SteamOS ecosystem)

### Type

A Steam Deck/SteamOS installer \+ ecosystem that includes ES-DE and many emulators.

### ROM root

EmuDeck FAQ documents ROM location under the chosen install root, typically: \- /home/deck/Emulation/roms (internal SSD)  
or the SD-card equivalent under /run/media/.../Emulation/roms. 

### ES-DE configuration \+ scraped media location (EmuDeck defaults)

EmuDeck’s ES-DE page documents: \- **Config Location:** $HOME/ES-DE \- **Scraped Media Location:** Emulation/tools/downloaded\_media 

### Converter notes

* Treat EmuDeck as ES-DE \+ a specific folder root convention:

* If building a converter for “Steam Deck libraries”, emit ES-DE format media and place it in the EmuDeck expected scraped media folder (or let users configure).

* If you want cross-device sync, keep ROMs under Emulation/roms and media under the scraped-media directory specified in EmuDeck settings.

---

## RetroDECK(s)

### Type

A Flatpak-distributed “all-in-one” stack that uses ES-DE conventions.

### Folder notes

RetroDECK documentation describes a .downloaded\_media location for scraped data and points out how the Flatpak config structure maps to RetroArch and ES-DE config paths. 

### Converter notes

* Use ES-DE rules for metadata \+ media, but be ready for the Flatpak-specific base directories.

---

## RetroBat

### Type

Windows-based stack (RetroArch \+ ES frontend), with a portable folder tree.

### ROM root \+ gamelist

RetroBat’s wiki describes a standard roms/ folder structure and that RetroBat parses gamelist.xml in ROM directories. 

### Config file

RetroBat uses retrobat.ini for many global settings, including paths and various front-end options. 

### Converter notes

* Treat RetroBat as “Batocera-ish ES-family on Windows”:

* system folders under roms/

* gamelist.xml commonly within each system folder

* media folders next to ROMs or as configured

---

## LaunchBox / Big Box

### Type

Windows launcher \+ “Big Box” 10-foot UI.

### Metadata storage

LaunchBox historically stored platform metadata as XML under LaunchBox\\Data\\Platforms\\\<platform\>.xml (plus emulators in Emulators.xml). A forum thread references this structure. 

Newer LaunchBox versions have moved from “local XML” to a SQLite database engine according to LaunchBox release notes. 

**Practical implication for converters:** support at least one of:  
1\) XML ingestion/export (still common in existing installs and exports), or  
2\) SQLite ingestion if the user is on newer versions and wants direct DB access.

### Media folders

LaunchBox uses an Images folder with per-platform subfolders and per-image-type subfolders (e.g., “Box \- Front”, “Clear Logo”, “Background”, “Screenshot”). An official help article references these media types and cleanup from LaunchBox \> Images. 

### Converter notes

* LaunchBox media is organized by **platform \+ media category** rather than “system folder next to ROMs”.

* File association is typically by game title (or database IDs), so converters should implement:

* slugging rules

* “best-effort fuzzy matching” between ROM basename and LaunchBox entry title

* or use LaunchBox XML’s ApplicationPath as a stable key when available (see sample schema reference). 

---

## Attract-Mode

### Type

Arcade-cabinet oriented frontend with flexible layouts.

### Core files

* Main config: attract.cfg and/or per-emulator configs. 

* Romlists live under a romlists/ directory. 

### Romlist file format (important)

A commonly referenced romlist format begins with a header line like: \#Name;Title;Emulator;CloneOf;Year;Manufacturer;Category;Players;Rotation;Control;Status;DisplayCount;... followed by ;\-separated rows. 

### Artwork configuration and lookup behavior

Attract-Mode supports many artwork types (snap, wheel, marquee, flyer, etc.) and searches for artwork in configured directories, trying a sequence of “name-based” matches (display name, romname, clone, etc.). 

### Converter notes

* Implement Attract-Mode as:

* **romlist generator** (text with columns)

* **artwork copier** (place files in the configured artwork folders; filenames typically match romname)

* If the user has a custom layout, they may have custom artwork labels; keep this configurable.

---

## Pegasus Frontend

### Type

Cross-platform frontend using a text-based metadata system.

### Media discovery rules

Pegasus documentation defines how it locates assets: you can place media under a game’s directory and use recognized filenames like boxFront, boxBack, poster, logo, screenshot, video, manual, etc. 

### Metadata format

Pegasus uses metadata files (commonly metadata.pegasus.txt) with a simple syntax, and supports setting files: plus fields like title, developer, etc.

### Converter notes

* Pegasus is friendly for converters because:

* the metadata language is straightforward

* asset naming is standardized (and strongly typed)

* Best practice: generate metadata.pegasus.txt per collection and copy assets into the expected locations.

---

## RetroArch (playlists, thumbnails, overlays)

### Playlists

RetroArch uses .lpl playlist files containing entries referencing ROM paths and core info.

### Thumbnails folder structure

Libretro documentation describes thumbnail storage: \- thumbnails/\<system\>/\<Named\_Boxarts|Named\_Snaps|Named\_Titles\>/... 

### Converter notes

* RetroArch is “metadata-light” by default; you can use ES/ES-DE/LaunchBox as your metadata authority and only generate playlists \+ thumbnails as a derived output.

* If you need bezels/overlays, output overlay.cfg plus PNG and point cores/config to them (often via per-game core overrides).

---

# Conversion cookbook

## Step 0 — Decide your “hub format”

Two strong choices: \- **ES-DE as hub** (typed media folders, central gamelists) \- **Normalized internal schema \+ emit multiple targets**

## Step 1 — Detect the input ecosystem

* Look for signature files:

* ES-family: gamelist.xml

* OnionOS: miyoogamelist.xml \+ Imgs/

* muOS: MUOS/info/catalogue/\<system\>/

* LaunchBox: LaunchBox/Data/\* and LaunchBox/Images/\*

* Attract-Mode: attract.cfg, romlists/\*.txt

## Step 2 — Build the internal model

* Enumerate systems

* Enumerate ROMs

* Parse metadata source into normalized Game fields

* Resolve assets:

* explicit file paths (XML entries)

* derived by conventions (suffixes or same-basename matching)

* fallback scans if missing

## Step 3 — Emit output ecosystem

* Create system directories

* Copy/convert assets into correct directories and names

* Write metadata/config files

* Validate (see checklist)

## Step 4 — Handle multi-disc \+ special cases

* ES-DE provides guidance for multi-disc via directories-as-files or .m3u approaches (device ecosystem dependent). 

---

# Mapping tables

## 1\) “ES-family” asset tag → normalized asset type

Actual supported tags vary across forks/themes, but these are widely used in ES-family stacks.

* \<image\> → box\_front or screenshot\_gameplay (depends on scraper setting)

* \<thumbnail\> → screenshot\_gameplay (small)

* \<marquee\> → marquee

* \<video\> → video

* \<bezel\> → bezel (Batocera shows this tag in the wild) 

## 2\) Batocera suffix → normalized asset type

From Batocera example paths:

\- \*-image.png → box\_front (or main image) 

\- \*-thumb.png → screenshot\_gameplay (thumb) 

\- \*-marquee.png → marquee 

\- \*-video.mp4 → video 

\- \*-bezel.png → bezel

## 3\) ES-DE media folder → normalized asset type

From ES-DE media directory list:

 \- covers/ → box\_front

 \- backcovers/ → box\_back 

\- 3dboxes/ → box\_front (3D) 

\- screenshots/ → screenshot\_gameplay 

\- titlescreens/ → screenshot\_title 

\- marquees/ → marquee 

\- fanart/ → fanart

 \- videos/ → video 

\- manuals/ → manual 

\- miximages/ → miximage

## 4\) RetroArch thumbnails

From libretro docs:

\- Named\_Boxarts → box\_front 

\- Named\_Snaps → screenshot\_gameplay 

\- Named\_Titles → screenshot\_title

## 5\) muOS catalogue

From muOS docs: 

\- .../box/ → box\_front 

\- .../preview/ → screenshot\_gameplay (or miximage)

---

# Format‑specific patterns (XML, SQL, DAT)

Modern retro‑emulation ecosystems share a common set of data containers for storing game metadata.  
The three most important file types are XML gamelists (used by EmulationStation‑family stacks and legacy LaunchBox), SQLite databases (used by newer LaunchBox builds and some plugins), and **DAT** files (used by ROM managers like ClrMamePro and for arcade sets).  
Understanding the structure of these files and how to read or produce them is essential for converter agents.

## XML patterns

### EmulationStation gamelist schema

The canonical metadata container for ES‑family systems is a gamelist.xml file located either within the system’s ROM folder or in a central gamelists/\<system\>/ directory.  
Each gamelist has a \<gameList\> root node containing one \<game\> element per entry. A \<game\> block uses a \<path\> tag to point to the ROM and can include tags such as \<name\>, \<desc\>, \<image\>, \<thumbnail\>, \<video\>, \<rating\>, \<releasedate\>, \<developer\>, \<publisher\>, \<genre\>, \<players\>, \<playcount\> and \<lastplayed\>[\[1\]](https://github.com/AmberELEC/emulationstation/blob/main/GAMELISTS.md#:~:text=).  
ES documents path semantics: asset paths can be absolute, start with ./ to denote a path relative to the ROM directory, or start with \~/ to reference the user’s home directory[\[2\]](https://github.com/AmberELEC/emulationstation/blob/main/GAMELISTS.md#:~:text=The%20gamelist,description%2C%20release%20date%2C%20and%20rating). Paths that omit these prefixes may fail to resolve; for example, ES‑DE requires \<path\> values beginning with ./ to link games correctly[\[2\]](https://github.com/AmberELEC/emulationstation/blob/main/GAMELISTS.md#:~:text=The%20gamelist,description%2C%20release%20date%2C%20and%20rating). The metadata fields are encoded as strings, floats, integers or ISO‑formatted datetimes, and image/video paths are treated as either absolute or relative with the same rules[\[3\]](https://github.com/AmberELEC/emulationstation/blob/main/GAMELISTS.md#:~:text=There%20are%20a%20few%20types,of%20metadata).

When writing a gamelist, preserve the \<gameList\> root, ensure each \<game\> has a \<path\> that matches the ROM’s location, and provide only the tags your target frontend recognises. Converters should remove unused media tags if targeting an ES‑DE environment (because ES‑DE ignores explicit \<image\>/\<video\> tags and instead matches files by filename) and should ensure \<releasedate\> values follow the YYYYMMDDT000000 format. To parse a gamelist programmatically, use a standard XML parser (e.g., Python’s xml.etree.ElementTree), iterate through \<game\> nodes, and read/write tags accordingly.

### LaunchBox XML

Legacy LaunchBox installations store platform metadata in LaunchBox/Data/Platforms/\<platform\>.xml. These files use a \<LaunchBox\> root with many \<Game\> child entries. A typical \<Game\> element contains fields like \<ID\>, \<Title\>, \<ReleaseDate\>, \<Rating\>, \<Genre\>, \<Platform\>, \<Developer\>, \<Publisher\>, \<ApplicationPath\>, \<ConfigurationPath\>, \<ManualPath\>, \<StarRating\> and others[\[4\]](https://gist.github.com/Xananax/7dccce48db254ef7acd0#:~:text=%3C%3Fxml%20version%3D,DOS%5CBaryon%20%5B1995%5D%3C%2FRootFolder%3E%20%3CWikipediaURL%20%2F%3E%20%3C%2FGame)[\[5\]](https://gist.github.com/Xananax/7dccce48db254ef7acd0#:~:text=%3CID%3E9eb28688,DOS%5CBlood%20%5B1997%5D%3C%2FRootFolder%3E%20%3CWikipediaURL%20%2F%3E%20%3C%2FGame). The \<ApplicationPath\> or \<ID\> can be used as a stable key when matching ROMs to metadata.  
LaunchBox’s XML format is verbose and includes many optional tags such as \<UseDosBox\>, \<ScummVMFolder\>, \<SortTitle\>, \<Notes\> and \<StarRating\>[\[4\]](https://gist.github.com/Xananax/7dccce48db254ef7acd0#:~:text=%3C%3Fxml%20version%3D,DOS%5CBaryon%20%5B1995%5D%3C%2FRootFolder%3E%20%3CWikipediaURL%20%2F%3E%20%3C%2FGame). When generating LaunchBox XML, populate the fields relevant to your library and omit unnecessary ones. To ingest existing LaunchBox XML, parse the \<Game\> elements and map them into your canonical model; pay particular attention to the \<ApplicationPath\> to locate ROMs on disk.

### Reading and writing XML

Because these gamelists are standard XML documents, they can be read and written with off‑the‑shelf libraries. In Python, for example, xml.etree.ElementTree.parse('gamelist.xml') loads the file; you can then iterate through root.findall('game') to read each entry and use ElementTree.write('output.xml', encoding='utf‑8') to create a new file. When writing, always include the XML declaration (\<?xml version="1.0"?\>) and ensure the file is saved in UTF‑8. When converting between frontends, pay careful attention to path semantics and remove or add \<image\>, \<thumbnail\>, \<video\> tags according to the target’s expectations.

## SQL patterns (SQLite)

Modern frontends increasingly use SQLite, a self‑contained relational database, to store metadata. SQLite files are portable across platforms and can be queried with standard SQL. Notable examples include:

* **MAME data plugin** – MAME’s internal data plugin builds a history.db file in its data directory that stores information extracted from support files. The documentation notes that this database uses the SQLite3 format[\[6\]](https://docs.mamedev.org/plugins/data.html#:~:text=Note%20that%20you%20can%20only,dat%20files%20simultaneously). A developer can open this database using the sqlite3 command‑line tool or any SQLite library to query tables such as history or bios.

* **LaunchBox (post‑2025 versions)** – According to LaunchBox’s release notes, version 13.19 replaced the legacy XML‑based local game database with a high‑performance SQLite database[\[7\]](https://www.launchbox-app.com/about/changelog#:~:text=,performance%20gains%20in%20upcoming%20releases). The change reduces memory usage and speeds up startup, signalling that new LaunchBox installations will expect a .db file rather than XML. While LaunchBox’s schema is proprietary, it typically includes tables for Games, Platforms, Genres, Developers, Publishers and relationship tables. Converters should extract data via SQL queries such as SELECT Title, PlatformID, ApplicationPath FROM Games and join to look up platform names.

### Reading SQLite databases

To inspect a SQLite database, use sqlite3 \<databasefile\> and issue commands like .tables to list tables, .schema \<table\> to view structure, and SELECT statements to extract rows. In Python, you can connect via sqlite3.connect('library.db') and use cursors to execute queries. When building a converter, identify the primary keys and relationships (e.g., PlatformID in a Games table) and map them to your canonical model. Because SQLite allows arbitrary schema changes, use introspection rather than hard‑coding column names wherever possible.

### Writing SQLite databases

When emitting a SQLite library, first create the necessary tables with CREATE TABLE statements matching the target frontend’s expected schema. Insert rows using INSERT INTO statements or high‑level libraries like SQLAlchemy. Ensure you wrap multiple inserts within transactions (BEGIN; … COMMIT;) to improve performance. If you are generating a LaunchBox database, consult the official schema or export an existing database as a template, then populate tables accordingly. Always close the database connection to flush data to disk.

## DAT file patterns (ROM set definitions)

DAT files are metadata lists used by ROM management utilities (e.g., ClrMamePro, RomCenter, MAME) to describe the contents of game sets. They are typically XML documents conforming to the Logiqx DTD and have a \<datafile\> root element[\[8\]](https://pleasuredome.miraheze.org/wiki/DAT_File#:~:text=Emulators%20usually%20require%20files%20with,to%20find%20and%20use%20them). Inside \<datafile\> you will find a \<header\> describing the dat (name, description, version, author) and a series of \<machine\> (or sometimes \<game\>) elements that correspond to individual game sets. Each \<machine\> has a name attribute and contains one or more \<rom\> child elements. A \<rom\> entry records attributes such as name (ROM filename), size (bytes), crc and sha1 hashes, and sometimes status or region[\[8\]](https://pleasuredome.miraheze.org/wiki/DAT_File#:~:text=Emulators%20usually%20require%20files%20with,to%20find%20and%20use%20them). DAT files therefore provide a definitive listing of which files belong to each game and how to verify their integrity.

### Reading DAT files

Because DAT files are XML, you can parse them with the same tools used for gamelists. Iterate through each \<machine\> element to obtain the name of the set and read its \<rom\> children to get file names and checksums. This allows you to verify that a collection of ROMs matches the expected CRC/SHA1 values. Some ROM managers like **datutil** can convert between dat formats or extract lists of files from a dat. When converting to another frontend, you can use the dat as your source of truth for ROM basenames and verify that your ROM files are unmodified.

### Producing DAT files

There are two common ways to generate a dat:

* **Using ClrMamePro’s Dir2Dat** – The Dir2Dat feature scans a folder of ROMs and produces a dat describing its contents. The ClrMamePro interface allows you to set options such as Description, Single File Sets, Add Date, Match tagdata, and toggles for whether to keep archives and CHDs as files[\[9\]](https://pleasuredome.miraheze.org/wiki/How_to_create_a_dat-file_with_clrmamepro#:~:text=This%20is%20a%20collection%20of,file%20%20with%20%2022). Once configured, pressing **Create** scans the source folder and outputs a DAT file with \<machine\> entries and \<rom\> hashes for each file[\[9\]](https://pleasuredome.miraheze.org/wiki/How_to_create_a_dat-file_with_clrmamepro#:~:text=This%20is%20a%20collection%20of,file%20%20with%20%2022). This is useful when you have a curated ROM folder and need to produce a dat for distribution or verification.

* **Using emulator tools** – Many emulators can emit XML lists of supported games. For example, MAME supports the \-listxml command, which outputs an XML file containing \<machine\> entries for all supported arcade games. Converting this output into a dat is as simple as saving the XML and, if necessary, wrapping it in a \<datafile\> root element with a \<header\>.

When creating your own dat, compute the CRC and SHA1 of each ROM file (using tools like crc32 or sha1sum), populate the \<rom\> attributes accordingly, and group related files under a \<machine\> whose name matches the expected set name. Including accurate checksums ensures that ROM managers can validate your set and that conversions built from the dat will match the intended ROMs.

# Validation checklist

Before declaring “conversion done”, verify:

1. **System detection**

2. Every ROM belongs to exactly one target system (or intentionally multiple collections).

3. **Path correctness**

4. All metadata references resolve on the target device (relative vs absolute).

5. Case sensitivity is correct on Linux-based targets.

6. **Filename normalization**

7. Decide whether to preserve input filenames or normalize (beware: changing ROM names can break save states and playlists).

8. **Media completeness**

9. If target UI expects a specific asset type (e.g., marquee), provide it or choose fallbacks.

10. Avoid mixing JPG assets into places requiring transparency.

11. **Performance**

12. Avoid excessively large PNGs/videos for handhelds.

13. Ensure no duplicate large assets are copied unnecessarily.

---

## Appendix: Practical “conversion presets” (recommended defaults)

### A) “Universal ES-family output” preset

For each system: \- roms/\<system\>/ \- ROM files \- gamelist.xml \- images/, videos/, manuals/ \- Use relative paths in gamelist.xml with ./images/... and ./videos/....

### B) “ES-DE hub” preset

* ROMs anywhere (user-configurable)

* downloaded\_media/\<system\>/\<type\>/\<rom\_basename\>.\<ext\>

* gamelists/\<system\>/gamelist.xml (text metadata only)

### C) “muOS minimal” preset

* Copy box art to MUOS/info/catalogue/\<system\>/box/ as same basename PNG

* Copy preview images to .../preview/ as same basename PNG

---

*End of document.*

---

[\[1\]](https://github.com/AmberELEC/emulationstation/blob/main/GAMELISTS.md#:~:text=) [\[2\]](https://github.com/AmberELEC/emulationstation/blob/main/GAMELISTS.md#:~:text=The%20gamelist,description%2C%20release%20date%2C%20and%20rating) [\[3\]](https://github.com/AmberELEC/emulationstation/blob/main/GAMELISTS.md#:~:text=There%20are%20a%20few%20types,of%20metadata) emulationstation/GAMELISTS.md at main · AmberELEC/emulationstation · GitHub

[https://github.com/AmberELEC/emulationstation/blob/main/GAMELISTS.md](https://github.com/AmberELEC/emulationstation/blob/main/GAMELISTS.md)

[\[4\]](https://gist.github.com/Xananax/7dccce48db254ef7acd0#:~:text=%3C%3Fxml%20version%3D,DOS%5CBaryon%20%5B1995%5D%3C%2FRootFolder%3E%20%3CWikipediaURL%20%2F%3E%20%3C%2FGame) [\[5\]](https://gist.github.com/Xananax/7dccce48db254ef7acd0#:~:text=%3CID%3E9eb28688,DOS%5CBlood%20%5B1997%5D%3C%2FRootFolder%3E%20%3CWikipediaURL%20%2F%3E%20%3C%2FGame) launchbox.xml · GitHub

[https://gist.github.com/Xananax/7dccce48db254ef7acd0](https://gist.github.com/Xananax/7dccce48db254ef7acd0)

[\[6\]](https://docs.mamedev.org/plugins/data.html#:~:text=Note%20that%20you%20can%20only,dat%20files%20simultaneously) Data Plugin — MAME Documentation 0.285 documentation

[https://docs.mamedev.org/plugins/data.html](https://docs.mamedev.org/plugins/data.html)

[\[7\]](https://www.launchbox-app.com/about/changelog#:~:text=,performance%20gains%20in%20upcoming%20releases) LaunchBox for Windows Latest Changes

[https://www.launchbox-app.com/about/changelog](https://www.launchbox-app.com/about/changelog)

[\[8\]](https://pleasuredome.miraheze.org/wiki/DAT_File#:~:text=Emulators%20usually%20require%20files%20with,to%20find%20and%20use%20them) DAT File \- Retro Arcade Guides

[https://pleasuredome.miraheze.org/wiki/DAT\_File](https://pleasuredome.miraheze.org/wiki/DAT_File)

[\[9\]](https://pleasuredome.miraheze.org/wiki/How_to_create_a_dat-file_with_clrmamepro#:~:text=This%20is%20a%20collection%20of,file%20%20with%20%2022) How to create a dat-file with clrmamepro \- Retro Arcade Guides

[https://pleasuredome.miraheze.org/wiki/How\_to\_create\_a\_dat-file\_with\_clrmamepro](https://pleasuredome.miraheze.org/wiki/How_to_create_a_dat-file_with_clrmamepro)