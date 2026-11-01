"""Acceptance runner for the 3 poster briefs."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from poster_agent.pipeline import PosterPipeline


def run_all_acceptance():
    assets_dir = Path("runs/synthetic_acceptance_assets")
    results = {}

    # 1. NOVA CTF 2026
    print("\n" + "=" * 60)
    print("RUNNING 1/3: NOVA CTF 2026")
    print("=" * 60)
    nova_brief = Path("briefs/brief_nova_ctf.txt").read_text(encoding="utf-8")
    nova_pipeline = PosterPipeline(run_id="acceptance_nova_ctf")
    nova_pdf, nova_png, nova_md, nova_json = nova_pipeline.run(
        raw_brief=nova_brief,
        bg_image_path=assets_dir / "nova_bg.png",
        hero_image_path=assets_dir / "nova_hero.png",
        title_3d_path=assets_dir / "nova_title_3d.png",
        theme_name="cyber_ctf",
        use_gemini=False,
    )
    results["nova_ctf"] = {
        "pdf": str(nova_pdf),
        "png": str(nova_png),
        "md": str(nova_md),
        "json": str(nova_json),
    }

    # 2. AURORA 2027
    print("\n" + "=" * 60)
    print("RUNNING 2/3: AURORA 2027")
    print("=" * 60)
    aurora_brief = Path("briefs/brief_aurora.txt").read_text(encoding="utf-8")
    aurora_pipeline = PosterPipeline(run_id="acceptance_aurora")
    aurora_pdf, aurora_png, aurora_md, aurora_json = aurora_pipeline.run(
        raw_brief=aurora_brief,
        bg_image_path=assets_dir / "aurora_bg.png",
        hero_image_path=assets_dir / "aurora_hero.png",
        theme_name="aurora",
        title_treatment="css_gradient_glow",
        use_gemini=False,
    )
    results["aurora"] = {
        "pdf": str(aurora_pdf),
        "png": str(aurora_png),
        "md": str(aurora_md),
        "json": str(aurora_json),
    }

    # 3. GREEN LOOP 2027
    print("\n" + "=" * 60)
    print("RUNNING 3/3: GREEN LOOP 2027")
    print("=" * 60)
    green_brief = Path("briefs/brief_green_loop.txt").read_text(encoding="utf-8")
    green_pipeline = PosterPipeline(run_id="acceptance_green_loop")
    green_pdf, green_png, green_md, green_json = green_pipeline.run(
        raw_brief=green_brief,
        bg_image_path=assets_dir / "green_loop_bg.png",
        hero_image_path=assets_dir / "green_loop_hero.png",
        theme_name="green_loop",
        title_treatment="flat",
        use_gemini=False,
    )
    results["green_loop"] = {
        "pdf": str(green_pdf),
        "png": str(green_png),
        "md": str(green_md),
        "json": str(green_json),
    }

    print("\n" + "=" * 60)
    print("ALL 3 ACCEPTANCE POSTERS COMPLETED")
    print("=" * 60)
    return results


if __name__ == "__main__":
    res = run_all_acceptance()
    print(json.dumps(res, indent=2))
