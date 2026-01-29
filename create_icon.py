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

    # 1. Draw the main background circle (Radar Scope)
    # Bounding box: [x0, y0, x1, y1]
    draw.ellipse([10, 10, 246, 246], fill=dark_bg, outline=elite_orange, width=10)

    # 2. Draw Grid Lines (Crosshairs)
    draw.line([128, 20, 128, 236], fill=elite_orange, width=4) # Vertical
    draw.line([20, 128, 236, 128], fill=elite_orange, width=4) # Horizontal

    # 3. Draw Concentric Rings (Radar distance markers)
    draw.ellipse([64, 64, 192, 192], outline=elite_orange, width=3)

    # 4. Draw a "Target" Blip (Cyan dot representing a discovery)
    # Placed in the top-right quadrant
    draw.ellipse([170, 60, 200, 90], fill=elite_cyan, outline="white", width=2)

    # Save as .ico
    # We include multiple sizes so Windows can scale it for the Taskbar, Explorer, etc.
    img.save('icon.ico', format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print("✅ icon.ico created successfully!")

if __name__ == "__main__":
    create_icon()