"""
gif2.py — Convert a GIF into an ASCII-art GIF.

Each frame of the source GIF is downsampled, mapped to a set of ASCII
characters based on pixel brightness, and re-rendered as text on a new
image. All rendered frames are then reassembled into an output GIF with
the same per-frame durations as the original.

Optionally supports background removal: pixels close in color to the
frame's top-left pixel are treated as background and rendered as fully
transparent instead of a character, producing a GIF with a transparent
backdrop.
"""

import sys
import argparse
from PIL import Image, ImageDraw, ImageFont, ImageSequence

# Character ramp used to represent brightness, ordered from lightest
# (space, i.e. "empty" / background-like) to darkest (most "ink").
DEFAULT_CHARS = " .:-=/\\#%@"


# Candidate monospace font paths to try, in order, across platforms.
# A monospace font is required so that each character occupies the same
# cell width/height when the ASCII grid is rendered back to an image.
FONT_CANDIDATES = [
    "DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "C:\\Windows\\Fonts\\consola.ttf",
    "C:\\Windows\\Fonts\\cour.ttf",
    "/System/Library/Fonts/Menlo.ttc",
]


def load_font(size: int) -> ImageFont.FreeTypeFont:
    """
    Try each candidate font path until one loads successfully.

    Falls back to PIL's built-in bitmap font (load_default) if none of
    the candidate TrueType fonts are available on the system. Note that
    the default font ignores `size` and is generally small/low quality,
    so results will look worse than with a proper monospace TTF.
    """
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue

    return ImageFont.load_default()


def color_distance(c1, c2):
    """
    Euclidean distance between two RGB colors (as (r, g, b) tuples).
    Used to decide whether a pixel is "close enough" to the detected
    background color to be treated as background.
    """
    return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5


def frame_to_ascii_rows(frame: Image.Image, width: int, chars: str, invert: bool,
                         bg_color=None, bg_tolerance: int = 30):
    """
    Convert a single image frame into a grid of ASCII characters.

    Steps:
      1. Resize the frame down to `width` columns. The height is scaled
         to keep the visual aspect ratio correct, compensated by
         `aspect_correction` since terminal/monospace character cells
         are taller than they are wide (~0.55 width/height ratio).
      2. Convert to grayscale to get a brightness value per cell.
      3. Also keep the RGB values per cell, so that (if requested) we
         can detect which cells are "background" by color proximity.
      4. Map each grayscale value to a character in `chars`, from
         lightest to darkest (or reversed if `invert` is set).

    Returns:
        rows:    list of strings, one string per output row of ASCII
                 characters (each string has `width` characters).
        bg_rows: list of lists of booleans, same shape as `rows`,
                 marking which cells were classified as background.
    """
    # Compensates for monospace characters typically being taller than
    # wide, so the final ASCII image doesn't look vertically stretched.
    aspect_correction = 0.55
    w, h = frame.size
    new_h = max(1, int((width / w) * h * aspect_correction))

    # Downscale once, then derive both a color (RGB) and brightness
    # (grayscale) version of the same small image.
    rgb_small = frame.convert("RGB").resize((width, new_h))
    gray_small = rgb_small.convert("L")
    rgb_pixels = list(rgb_small.getdata())
    gray_pixels = list(gray_small.getdata())

    # Index of the last character in the ramp; used to scale a 0-255
    # brightness value down to a valid index into `chars`.
    scale = len(chars) - 1
    ascii_pixels = []
    is_bg = []
    for rgb, gray in zip(rgb_pixels, gray_pixels):
        # A pixel counts as "background" only when background removal
        # is enabled (bg_color is not None) and its color is within
        # `bg_tolerance` of the reference background color.
        background = bg_color is not None and color_distance(rgb, bg_color) <= bg_tolerance
        is_bg.append(background)
        if invert:
            # Inverted mapping: brighter pixels -> darker/denser chars.
            ascii_pixels.append(chars[scale - int(gray / 255 * scale)])
        else:
            # Normal mapping: brighter pixels -> lighter/sparser chars.
            ascii_pixels.append(chars[int(gray / 255 * scale)])

    # Reshape the flat pixel-per-cell lists back into rows of `width`
    # characters/booleans each.
    rows = []
    bg_rows = []
    for row in range(new_h):
        rows.append("".join(ascii_pixels[row * width:(row + 1) * width]))
        bg_rows.append(is_bg[row * width:(row + 1) * width])
    return rows, bg_rows


def render_rows_to_image(rows, bg_rows, font, bg, fg, remove_bg: bool):
    """
    Render a grid of ASCII rows (as produced by frame_to_ascii_rows)
    back into a raster image.

    If `remove_bg` is True, cells marked as background (or containing
    a plain space character) are left untouched on a transparent
    (RGBA) canvas, so the output frame has a transparent backdrop.
    Otherwise, all characters are drawn on a solid-color (RGB) canvas
    using the given background/foreground colors.
    """
    # Use the bounding box of a representative character ("M") to
    # determine the fixed cell width/height for the monospace grid.
    bbox = font.getbbox("M")
    char_w = bbox[2] - bbox[0] or 1
    char_h = (bbox[3] - bbox[1]) or 1
    line_h = int(char_h * 1.15)  # small line-spacing multiplier

    cols = len(rows[0]) if rows else 0
    img_w = max(1, char_w * cols)
    img_h = max(1, line_h * len(rows))

    if remove_bg:
        # Transparent canvas: only draw characters that are NOT
        # background and are not blank spaces, leaving everything
        # else fully transparent.
        canvas = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        for i, (row, bg_row) in enumerate(zip(rows, bg_rows)):
            x = 0
            for ch, is_background in zip(row, bg_row):
                if not is_background and ch != " ":
                    draw.text((x, i * line_h), ch, font=font, fill=fg)
                x += char_w
    else:
        # Solid-color canvas: draw each full row of text directly,
        # which is much faster than drawing character by character.
        canvas = Image.new("RGB", (img_w, img_h), bg)
        draw = ImageDraw.Draw(canvas)
        for i, row in enumerate(rows):
            draw.text((0, i * line_h), row, font=font, fill=fg)
    return canvas


def main():
    parser = argparse.ArgumentParser(description="Convert a GIF into an ASCII-art GIF")
    parser.add_argument("gif_path", help="Path to the input GIF")
    parser.add_argument("output_path", help="Path for the output GIF")
    parser.add_argument("--width", type=int, default=100,
                         help="Width in characters (default: 100)")
    parser.add_argument("--font-size", type=int, default=10,
                         help="Font size in px (default: 10)")
    parser.add_argument("--chars", type=str, default=DEFAULT_CHARS,
                         help="Character set from lightest to darkest (default: " +
                              DEFAULT_CHARS.replace("%", "%%") + ")")
    parser.add_argument("--invert", action="store_true",
                         help="Invert the brightness mapping (light background -> light character)")
    parser.add_argument("--bg", type=str, default="black",
                         help="Background color when NOT removing the background (name or #hex, default: black)")
    parser.add_argument("--fg", type=str, default="white",
                         help="Text/foreground color (name or #hex, default: white)")
    parser.add_argument("--remove-bg", action="store_true",
                         help="Remove the background of the original gif (becomes transparent in the result)")
    parser.add_argument("--bg-tolerance", type=int, default=30,
                         help="Color tolerance used to detect the background to remove (default: 30)")
    args = parser.parse_args()

    font = load_font(args.font_size)

    im = Image.open(args.gif_path)

    # When background removal is requested, sample the top-left pixel
    # of the first frame as the reference background color. This is a
    # simple heuristic — it assumes the corner pixel is representative
    # of the background (works well for flat-color backgrounds).
    bg_color = None
    if args.remove_bg:
        first = im.convert("RGB")
        bg_color = first.getpixel((0, 0))

    out_frames = []
    durations = []
    # Iterate over every frame in the animated GIF, converting each one
    # to ASCII rows and then rendering those rows back into an image.
    for frame in ImageSequence.Iterator(im):
        # Preserve each frame's original display duration (falls back
        # to 100ms if the GIF doesn't specify one).
        duration = frame.info.get("duration", 100)
        rows, bg_rows = frame_to_ascii_rows(
            frame.copy(), args.width, args.chars, args.invert,
            bg_color=bg_color, bg_tolerance=args.bg_tolerance,
        )
        out_frames.append(render_rows_to_image(rows, bg_rows, font, args.bg, args.fg, args.remove_bg))
        durations.append(duration)

    if not out_frames:
        print("No frames were found in the gif.")
        sys.exit(1)

    save_kwargs = dict(
        save_all=True,
        append_images=out_frames[1:],
        duration=durations,
        loop=0,
        optimize=False,
    )
    if args.remove_bg:
        # Disposal method 2 clears each frame to the background before
        # drawing the next one — needed so transparent frames don't
        # leave "ghost" characters from previous frames when played back.
        save_kwargs["disposal"] = 2

    out_frames[0].save(args.output_path, **save_kwargs)
    print(f"Done: {len(out_frames)} frames -> {args.output_path}")


if __name__ == "__main__":
    main()