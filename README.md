# Asciify

A small Python CLI tool that converts an animated GIF into an **ASCII-art GIF**, frame by frame, with optional background removal for a transparent result.

## How it works

1. Each frame of the source GIF is resized down to a fixed number of character columns.
2. Every pixel cell is converted to grayscale and mapped to a character from a brightness ramp (light → dark), producing a grid of ASCII characters.
3. That character grid is rendered back into an image using a monospace font.
4. All rendered frames are reassembled into a new animated GIF, preserving the original per-frame durations.

Optionally, the tool can detect the background color (sampled from the top-left pixel of the first frame) and skip drawing any character whose original pixel color is close enough to it — producing an ASCII GIF with a transparent background instead of a solid one.

## Requirements

- Python 3.7+
- [Pillow](https://python-pillow.org/) (`PIL`)

```bash
pip install Pillow
```

A monospace TrueType font is used for rendering if available (DejaVu Sans Mono, Liberation Mono, Consolas, Menlo, etc., depending on OS). If none are found, Pillow's built-in bitmap font is used as a fallback (lower quality).

## Usage

```bash
python gif2.py <input.gif> <output.gif> [options]
```

### Positional arguments

| Argument      | Description                |
|---------------|-----------------------------|
| `gif_path`    | Path to the input GIF       |
| `output_path` | Path for the output GIF     |

### Options

| Flag              | Default | Description                                                                 |
|--------------------|---------|-------------------------------------------------------------------------------|
| `--width`           | `100`   | Output width in characters                                                    |
| `--font-size`       | `10`    | Font size in pixels                                                           |
| `--chars`           | `" .:-=/\\#%@"` | Character ramp, ordered from lightest to darkest                     |
| `--invert`          | off     | Invert the brightness mapping                                                 |
| `--bg`              | `black` | Background color (name or `#hex`) — used only when `--remove-bg` is **not** set |
| `--fg`              | `white` | Text/foreground color (name or `#hex`)                                        |
| `--remove-bg`       | off     | Remove the background, producing a transparent-background GIF                 |
| `--bg-tolerance`    | `30`    | Color distance tolerance used to detect the background to remove              |

### Examples

Basic conversion:

```bash
python gif2.py input.gif output.gif
```

Wider output, custom colors:

```bash
python gif2.py input.gif output.gif --width 160 --bg "#000000" --fg "#00ff00"
```

Transparent background, more lenient background detection:

```bash
python gif2.py input.gif output.gif --remove-bg --bg-tolerance 50
```

Custom character ramp and inverted brightness mapping:

```bash
python gif2.py input.gif output.gif --chars " .oO0@" --invert
```

## Notes / limitations

- `--remove-bg` uses a simple heuristic: it samples the color of the **top-left pixel of the first frame** as the reference background color. This works well for flat, solid-colored backgrounds but may not work for gradients, noisy backgrounds, or GIFs where the corner pixel isn't representative of the background.
- The aspect-ratio correction factor (`0.55`) assumes typical monospace character proportions; very unusual fonts may need manual tuning of `--width` to look right.
- Larger `--width` and `--font-size` values produce sharper, larger, and slower-to-render output GIFs.

Add your license of choice here.
