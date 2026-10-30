from pathlib import Path
from playwright.sync_api import sync_playwright

def render_variants():
    out_dir = Path("runs/exports")
    out_dir.mkdir(parents=True, exist_ok=True)
    brain_dir = Path("C:/Users/iQube/.gemini/antigravity/brain/98f40bc9-b037-4830-8e36-54702f37f83a")

    variants = [
        ("runs/poster_variant_path1.html", "poster_blend_path1_2x.png"),
        ("runs/poster_variant_path2.html", "poster_blend_path2_2x.png"),
        ("runs/poster_variant_path3.html", "poster_blend_path3_2x.png"),
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for html_rel, png_name in variants:
            html_path = Path(html_rel).resolve()
            out_png = out_dir / png_name
            artifact_png = brain_dir / png_name

            page = browser.new_page(
                viewport={"width": 1024, "height": 1536},
                device_scale_factor=2
            )
            page.goto(html_path.as_uri(), wait_until="networkidle")
            page.evaluate("document.fonts.ready")

            canvas = page.locator(".poster-canvas")
            canvas.screenshot(path=str(out_png))
            canvas.screenshot(path=str(artifact_png))
            page.close()
            print(f"Rendered {png_name} successfully!")

        browser.close()

if __name__ == "__main__":
    render_variants()

