"""Create Chrome-friendly JPEG copies of HEIC/HEIF photos under images/."""
from pathlib import Path

from PIL import Image, ImageOps
from pillow_heif import is_supported, register_heif_opener


IMAGE_ROOT = Path("images")
MAX_SIZE = (2400, 2400)


def main():
    register_heif_opener()
    converted = 0

    if not IMAGE_ROOT.exists():
        print("No images folder; nothing to convert.")
        return

    for source in sorted(IMAGE_ROOT.rglob("*")):
        if not source.is_file():
            continue

        try:
            # Inspect the file contents, not the filename: iPhones or upload
            # tools can leave HEIC photos with .png/.jpg/.jpeg extensions.
            if not is_supported(str(source)):
                continue
            destination = source.with_suffix(".jpg")
            # Do not overwrite a source file if an unusual HEIF file is named .jpg.
            if destination.resolve() == source.resolve():
                continue

            with Image.open(source) as original:
                image = ImageOps.exif_transpose(original).convert("RGB")
                image.thumbnail(MAX_SIZE, Image.Resampling.LANCZOS)
                image.save(destination, "JPEG", quality=86, optimize=True, progressive=True)
            print(f"Converted {source} -> {destination}")
            converted += 1
        except Exception as exc:
            print(f"Could not convert {source}: {exc}")

    print(f"HEIC/HEIF conversion complete: {converted} file(s).")


if __name__ == "__main__":
    main()
