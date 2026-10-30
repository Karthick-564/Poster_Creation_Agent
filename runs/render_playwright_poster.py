import os
from pathlib import Path
from playwright.sync_api import sync_playwright

def render_poster():
    html_path = Path("runs/nova_ctf_poster.html").resolve()
    out_dir = Path("runs/exports")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_png = out_dir / "nova_ctf_2026_final_2x.png"
    artifact_png = Path("C:/Users/iQube/.gemini/antigravity/brain/98f40bc9-b037-4830-8e36-54702f37f83a/nova_ctf_2026_final_2x.png")

    file_url = html_path.as_uri()
    print(f"Loading HTML: {file_url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 1024 x 1536 viewport with device_scale_factor=2 produces 2048 x 3072
        page = browser.new_page(
            viewport={"width": 1024, "height": 1536},
            device_scale_factor=2
        )
        page.goto(file_url, wait_until="networkidle")
        # Ensure fonts are loaded
        page.evaluate("document.fonts.ready")

        canvas_el = page.locator(".poster-canvas")
        canvas_el.screenshot(path=str(out_png))
        canvas_el.screenshot(path=str(artifact_png))
        browser.close()

    print(f"Rendered 2x poster successfully:")
    print(f"Local export: {out_png}")
    print(f"Artifact path: {artifact_png}")

if __name__ == "__main__":
    render_poster()

