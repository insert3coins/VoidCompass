try:
    from PIL import Image
except ImportError:
    print("Pillow is not installed. Please run: pip install Pillow")
    exit()


SOURCE_IMAGE = "icon-source.png"
OUTPUT_ICON = "icon.ico"
ICON_SIZES = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]


def create_icon():
    img = Image.open(SOURCE_IMAGE).convert("RGBA")
    img = img.resize((256, 256), Image.Resampling.LANCZOS)
    img.save(OUTPUT_ICON, format="ICO", sizes=ICON_SIZES)
    print(f"{OUTPUT_ICON} created successfully from {SOURCE_IMAGE}.")


if __name__ == "__main__":
    create_icon()
