import os
from PIL import Image

png_path = r"C:\Users\corey\.gemini\antigravity-ide\brain\afecd31f-c19c-4a67-8cc9-cbcbd6c1fc98\human_robot_handshake_icon_1780516947061.png"
ico_path = r"c:\Users\corey\.gemini\antigravity-ide\scratch\field-aware\triagecore\triage_core\ui\icon.ico"

if os.path.exists(png_path):
    img = Image.open(png_path)
    img.save(ico_path, format="ICO", sizes=[(256, 256)])
    print(f"Successfully converted PNG to {ico_path}")
else:
    print(f"Error: {png_path} does not exist.")
