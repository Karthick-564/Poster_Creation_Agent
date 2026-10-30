import os
import shutil
import asyncio
from playwright.async_api import async_playwright

WORKSPACE = r"c:\Users\iQube\project"
ARTIFACTS_DIR = r"C:\Users\iQube\.gemini\antigravity\brain\98f40bc9-b037-4830-8e36-54702f37f83a"
EXPORTS_DIR = os.path.join(WORKSPACE, "runs", "exports")
os.makedirs(EXPORTS_DIR, exist_ok=True)

VARIANTS = [
    {
        "html": os.path.join(WORKSPACE, "runs", "aurora_poster_variant_path2.html"),
        "export_png": os.path.join(EXPORTS_DIR, "aurora_poster_path2_2x.png"),
        "artifact_png": os.path.join(ARTIFACTS_DIR, "aurora_poster_path2_2x.png"),
    },
    {
        "html": os.path.join(WORKSPACE, "runs", "aurora_poster_variant_path3.html"),
        "export_png": os.path.join(EXPORTS_DIR, "aurora_poster_path3_2x.png"),
        "artifact_png": os.path.join(ARTIFACTS_DIR, "aurora_poster_path3_2x.png"),
    }
]

async def render():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for v in VARIANTS:
            page = await browser.new_page(
                viewport={"width": 1080, "height": 1350},
                device_scale_factor=2
            )
            file_url = f"file:///{v['html'].replace(os.sep, '/')}"
            print(f"Loading {file_url}...")
            await page.goto(file_url, wait_until="networkidle")
            await page.wait_for_timeout(1000)
            
            poster = await page.query_selector(".poster-canvas")
            await poster.screenshot(path=v["export_png"])
            print(f"Saved: {v['export_png']}")
            
            shutil.copyfile(v["export_png"], v["artifact_png"])
            print(f"Copied to artifact: {v['artifact_png']}")
            await page.close()
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(render())

