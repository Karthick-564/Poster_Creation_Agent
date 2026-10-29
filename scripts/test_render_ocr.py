from playwright.sync_api import sync_playwright
from rapidocr_onnxruntime import RapidOCR

w, h = 1200, 1600
text = "APEX TECH SUMMIT 2026"
l_px, t_px, box_w, box_h = 96, 288, 1008, 160
font_px = 54

content = f"""<!DOCTYPE html>
<html>
<body style="margin:0; background:#0B132B;">
  <div id="canvas" style="position:relative; width:{w}px; height:{h}px; background:#0B132B;">
    <div style="position:absolute; left:{l_px}px; top:{t_px}px; width:{box_w}px; height:{box_h}px; font-family:Arial, sans-serif; font-size:{font_px}px; font-weight:800; color:#FFFFFF; text-transform:uppercase; display:flex; align-items:center;">
      <span>{text}</span>
    </div>
  </div>
</body>
</html>"""

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": w, "height": h})
    page.set_content(content)
    page.screenshot(path="temp_test_render/pw_test_54.png")
    browser.close()

engine = RapidOCR()
res, _ = engine("temp_test_render/pw_test_54.png")
print("OCR result:", res)

