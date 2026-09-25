from PIL import Image
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
input_folder = project_root / "assets" / "originals"
output_folder = project_root / "assets" / "webp"

output_folder.mkdir(parents=True, exist_ok=True)

for input_path in input_folder.iterdir():
    if input_path.suffix.lower() == ".png":
        output_path = output_folder / f"{input_path.stem}.webp"

        with Image.open(input_path) as image:
            image.save(output_path, "WEBP", quality=100)

        print(f"Converted {input_path.name} -> {output_path.name}")
