"""End-to-End Pipeline Execution with Gemini Planner & Gemini Multimodal Vision Critic."""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from poster_agent.pipeline import PosterPipeline

NOVA_BRIEF = """- Event: NOVA CTF 2026
- Tagline: Capture the flag. Break it. Fix it.
- Date: 15-16 NOVEMBER 2026
- Time: 9:00 AM ONWARDS
- Venue: Main Computer Lab, Block C
- Team Size: Teams of 2-4
- Prize: ₹50,000 Total Prize Pool
- CTA: Register free at nova-ctf.example
- Events: Web | Crypto | Forensics | Reversing
- Organizer: Presented by NOVA Security Club
"""

BG_PATH = "ComfyUI/output/ideogram_circuit_bg_00001_.png"
HERO_PATH = "ComfyUI/output/qwen_shield_test_00001_.png"
FLAG_PATH = "ComfyUI/output/qwen_flag_test_00001_.png"


def main():
    print("=" * 80)
    print("STARTING GEMINI-POWERED 8-STAGE POSTER PIPELINE")
    print("=" * 80)
    print("Planner : Gemini 3.1 Flash (Stage 2 - Method 3 Depth-Blended Planning)")
    print("Critic  : Gemini Multimodal Vision (Stage 6 & Stage 7 Patcher Loop)")
    print("=" * 80)

    run_id = "nova_ctf_method3_master"
    pipeline = PosterPipeline(run_id=run_id, output_base="runs/pipeline_runs")

    pdf_path, png_path, md_path, json_path = pipeline.run(
        raw_brief=NOVA_BRIEF,
        context_text="Department of Computer Science & Engineering annual national cybersecurity competition.",
        bg_image_path=BG_PATH,
        hero_image_path=HERO_PATH,
        title_3d_path="",
        accent_image_path=FLAG_PATH,
        theme_name="cyber_ctf",
        format_name="A2",
        use_gemini=True,
    )

    print("\n" + "=" * 80)
    print("GEMINI PIPELINE COMPLETED SUCCESSFULLY!")
    print("=" * 80)
    print(f"Master Print PDF : {pdf_path}")
    print(f"300 DPI Bleed PNG: {png_path}")
    print(f"Audit Markdown   : {md_path}")
    print(f"Audit JSON Trace : {json_path}")

    print("\nEXECUTIVE AUDIT SUMMARY:\n" + "-" * 40)
    summary_text = md_path.read_text(encoding="utf-8")
    print(summary_text.encode("ascii", errors="replace").decode("ascii"))


if __name__ == "__main__":
    main()

