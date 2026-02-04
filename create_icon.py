try:
    from PIL import Image, ImageDraw
except ImportError:
    print("❌ Pillow is not installed. Please run: pip install Pillow")
    exit()

def create_icon():
    # Define size (256x256 is standard for high-res icons)
    size = (256, 256)
    
    # Create a new image with transparent background
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Elite Dangerous Theme Colors
    elite_orange = "#FF7100"
    elite_cyan = "#00d1ff"
    dark_bg = "#111111"
    darker_orange = "#994400"

    # 1. Draw the main background circle
    # Bounding box: [x0, y0, x1, y1]
    draw.ellipse([10, 10, 246, 246], fill=dark_bg, outline=elite_orange, width=8)

    # 2. Draw Cardinal ticks
    # North
    draw.line([128, 10, 128, 40], fill=elite_orange, width=6)
    # South
    draw.line([128, 216, 128, 246], fill=elite_orange, width=6)
    # East
    draw.line([216, 128, 246, 128], fill=elite_orange, width=6)
    # West
    draw.line([10, 128, 40, 128], fill=elite_orange, width=6)

    # 3. Draw the Compass Needle
    # North Point (Cyan - pointing to the void)
    draw.polygon([(128, 45), (155, 128), (101, 128)], fill=elite_cyan)
    # South Point (Dark Orange - grounding)
    draw.polygon([(128, 211), (155, 128), (101, 128)], fill=darker_orange)

    # 4. Central Pivot
    draw.ellipse([118, 118, 138, 138], fill="#ffffff", outline=None)

    # Save as .ico
    # We include multiple sizes so Windows can scale it for the Taskbar, Explorer, etc.
    img.save('icon.ico', format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print("✅ icon.ico created successfully!")

if __name__ == "__main__":
    create_icon()