# Environment Reconnaissance

Date: 2026-08-14

Workspace:

```text
/data/PROYECTOS/kdenlive-mcp
```

This phase only inspects the local environment and creates small reproducible
test artifacts. It does not implement the MCP server or the editing engine.

## Host Tools

Detected binaries on the host:

```text
/usr/bin/python3
/usr/bin/ffmpeg
/usr/bin/ffprobe
/usr/bin/flatpak
```

Not found on the host `PATH`:

```text
python
melt
kdenlive
```

Versions:

```text
Python: 3.13.5
FFmpeg: 7.1.4-0+deb13u1
ffprobe: 7.1.4-0+deb13u1
```

The requested target is Python 3.11+. The installed Python 3.13.5 satisfies
that requirement, but the future package should declare supported versions
explicitly and run tests on the selected interpreter.

## Kdenlive Flatpak

Flatpak application:

```text
ID: org.kde.kdenlive
Version: 26.04.3
Branch: stable
Origin: flathub
Runtime: org.kde.Platform/x86_64/6.10
SDK: org.kde.Sdk/x86_64/6.10
Installation: system
```

Flatpak location:

```text
/var/lib/flatpak/app/org.kde.kdenlive/x86_64/stable/b19b3c18e9ca99ddda26b2af4354826775904b384f9f7e2cf66b73b9f8127c91
```

Flatpak permissions:

```text
shared=network;ipc;
sockets=wayland;pulseaudio;fallback-x11;
devices=all;
filesystems=xdg-run/pipewire-0;xdg-config/kdeglobals:ro;host;
```

Important consequence: this Kdenlive Flatpak currently has broad `host`
filesystem access. The MCP server must not inherit that trust model. It should
still enforce its own allowlists for media, project, and output directories.

## Tools Inside The Kdenlive Flatpak

Detected inside the Flatpak:

```text
/app/bin/kdenlive
/app/bin/melt
/app/bin/ffmpeg
/app/bin/ffprobe
```

Versions inside the Flatpak:

```text
Kdenlive: 26.04.3
MLT melt: 7.40.0
FFmpeg: 8.1.1
ffprobe: 8.1.1
```

This is a significant compatibility finding: the host FFmpeg/ffprobe version is
7.1.4, while the Kdenlive Flatpak uses 8.1.1. Future validation and render tests
should compare behavior against the Flatpak toolchain, especially for metadata,
codec support, GPU encoding, and MLT project loading.

## MLT Profiles

The Flatpak `melt` exposes vertical profiles relevant to Reels, Shorts, and
TikTok workflows.

`vertical_hd_30`:

```text
description: Vertical HD 30 fps
frame_rate_num: 30
frame_rate_den: 1
width: 1080
height: 1920
progressive: 1
sample_aspect_num: 1
sample_aspect_den: 1
display_aspect_num: 9
display_aspect_den: 16
colorspace: 709
```

`vertical_hd_60`:

```text
description: Vertical HD 60 fps
frame_rate_num: 60
frame_rate_den: 1
width: 1080
height: 1920
progressive: 1
sample_aspect_num: 1
sample_aspect_den: 1
display_aspect_num: 9
display_aspect_den: 16
colorspace: 709
```

Available MLT consumers include:

```text
xml
avformat
null
sdl2
sdl2_audio
multi
```

This confirms a terminal path exists for XML generation/inspection and render
validation through MLT, but Kdenlive-specific project XML still needs to be
studied from real `.kdenlive` files.

## Reproducible Recon Artifacts

Created:

```text
examples/recon/sample1.mp4
examples/recon/sample_vertical.mp4
examples/recon/sample_mlt.xml
```

Commands:

```bash
mkdir -p examples/recon docs

ffmpeg -y \
  -f lavfi -i testsrc2=size=640x360:rate=30 \
  -f lavfi -i sine=frequency=440:sample_rate=48000 \
  -t 3 \
  -c:v libx264 -pix_fmt yuv420p \
  -c:a aac \
  examples/recon/sample1.mp4

ffmpeg -y \
  -f lavfi -i testsrc2=size=360x640:rate=30 \
  -f lavfi -i sine=frequency=880:sample_rate=48000 \
  -t 3 \
  -c:v libx264 -pix_fmt yuv420p \
  -c:a aac \
  examples/recon/sample_vertical.mp4

flatpak run --command=melt org.kde.kdenlive \
  -profile vertical_hd_30 \
  examples/recon/sample1.mp4 \
  examples/recon/sample_vertical.mp4 \
  -consumer xml:examples/recon/sample_mlt.xml all=1

xmllint --noout examples/recon/sample_mlt.xml

flatpak run --command=melt org.kde.kdenlive \
  examples/recon/sample_mlt.xml \
  -consumer null
```

Validation results:

```text
xmllint accepted examples/recon/sample_mlt.xml.
Flatpak melt loaded and played examples/recon/sample_mlt.xml to consumer null.
Original synthetic media files were not modified after XML generation.
```

## Commands Used For Detection

```bash
python3 --version
ffmpeg -version
ffprobe -version
which python python3 ffmpeg ffprobe melt flatpak kdenlive
flatpak info org.kde.kdenlive
flatpak info --show-permissions org.kde.kdenlive
flatpak info --show-location org.kde.kdenlive
flatpak info --show-runtime org.kde.kdenlive
flatpak info --show-sdk org.kde.kdenlive
flatpak run --command=which org.kde.kdenlive kdenlive
flatpak run --command=which org.kde.kdenlive melt
flatpak run --command=which org.kde.kdenlive ffmpeg
flatpak run --command=which org.kde.kdenlive ffprobe
flatpak run --command=kdenlive org.kde.kdenlive --version
flatpak run --command=melt org.kde.kdenlive -version
flatpak run --command=ffmpeg org.kde.kdenlive -version
flatpak run --command=ffprobe org.kde.kdenlive -version
flatpak run --command=melt org.kde.kdenlive -query profiles
flatpak run --command=melt org.kde.kdenlive -query profile=vertical_hd_30
flatpak run --command=melt org.kde.kdenlive -query profile=vertical_hd_60
flatpak run --command=melt org.kde.kdenlive -query consumers
```

## Current Limitation

During the initial reconnaissance, no existing `.kdenlive` files were found in:

```text
/home/abrahamc
/data/PROYECTOS
/home/abrahamc/.var/app/org.kde.kdenlive/data/kdenlive/.backup
```

Kdenlive's CLI exposes options to open a project, import clips into the bin, and
render a project, but it does not expose a verified headless command to create
and save a new `.kdenlive` project. The first real reference projects were
therefore created manually through Kdenlive and saved under `examples/recon/`.

## Kdenlive Save Automation Probe

After the initial reconnaissance, Kdenlive was launched with the synthetic clips:

```bash
flatpak run org.kde.kdenlive \
  --no-welcome \
  -i examples/recon/sample1.mp4,examples/recon/sample_vertical.mp4 \
  examples/recon/cli_created.kdenlive
```

Result:

```text
Kdenlive opened and initialized normally.
No examples/recon/cli_created.kdenlive file was created automatically.
No autosave or backup .kdenlive file was found after timeout termination.
The active project title was Untitled [*]/ 640x360 30.00fps.
```

Kdenlive exposed a DBus service:

```text
org.kde.kdenlive.kdbus-_1_340
```

Relevant DBus objects/actions:

```text
/kdenlive/MainWindow_1
/kdenlive/MainWindow_1/actions/file_save
/kdenlive/MainWindow_1/actions/file_save_as
```

Relevant DBus methods:

```text
org.kde.kdenlive.MainWindow.addProjectClip(QString url)
org.kde.kdenlive.MainWindow.addTimelineClip(QString url)
org.kde.kdenlive.MainWindow.updateProjectPath(QString path)
org.kde.KMainWindow.activateAction(QString action)
```

`file_save` was enabled, but invoking it through:

```bash
qdbus6 org.kde.kdenlive.kdbus-_1_340 \
  /kdenlive/MainWindow_1 \
  org.kde.KMainWindow.activateAction file_save
```

blocked waiting for the GUI save dialog. Calling `updateProjectPath(...)` first
did not set `QWidget.windowFilePath` and did not provide a headless save path.

Conclusion: DBus can be useful later for controlled Kdenlive integration probes,
such as adding clips to the bin or timeline, but this installation does not
currently expose a tested headless "save project to path" operation through CLI
or DBus.

## Manual Kdenlive Project Capture

Manually captured through Kdenlive 26.04.3:

```text
examples/recon/manual_empty_vertical.kdenlive
examples/recon/manual_bin_only.kdenlive
examples/recon/manual_two_clips_timeline.kdenlive
examples/recon/manual_trim_marker.kdenlive
```

Validation:

```bash
xmllint --noout examples/recon/manual_*.kdenlive

flatpak run --command=melt org.kde.kdenlive \
  examples/recon/manual_two_clips_timeline.kdenlive \
  -consumer null terminate_on_pause=1
```

All four reference projects are well-formed XML and load through the Flatpak
`melt` binary with exit code 0. Kdenlive also created a cache directory named
after the document id, `examples/recon/1787190383242/`; that directory contains
thumbnails/audio thumbs and is ignored by Git.

## Sandbox Mitigation In Phase 1

The MCP environment tools now distinguish Flatpak metadata access from Flatpak
execution.

Inside the Codex command sandbox, `flatpak run` can fail with:

```text
error: Unable to allocate instance id
```

The server reports this as:

```text
FLATPAK_EXECUTION_UNAVAILABLE_IN_SANDBOX
```

and falls back to read-only metadata where possible:

```text
get_kdenlive_version -> flatpak info org.kde.kdenlive
get_mlt_version -> scan libmlt-7.so.* under flatpak info --show-location
```

This does not make render or GUI operations possible inside the sandbox. It does
make environment discovery deterministic and prevents version tools from failing
when only Flatpak execution is blocked.
