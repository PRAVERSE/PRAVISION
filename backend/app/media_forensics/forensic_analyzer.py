import os
from PIL import Image, ImageChops, ImageEnhance
from pathlib import Path
from app.config import settings

class MediaForensicAnalyzer:
    """
    Performs forensic inspection including Error Level Analysis (ELA) to identify
    potential manipulation, compression inconsistencies, or spliced regions.
    """

    def analyze_ela(self, image_path: str, quality: int = 90, scale: int = 15) -> dict:
        result = {
            "is_analyzed": False,
            "ela_image_filename": None,
            "compression_anomaly_detected": False,
            "forensic_notes": ""
        }

        if not os.path.exists(image_path):
            return result

        try:
            original = Image.open(image_path).convert("RGB")
            temp_resaved = settings.ephemeral_data_dir / "ela_temp.jpg"

            # Resave at specific quality
            original.save(temp_resaved, "JPEG", quality=quality)
            resaved = Image.open(temp_resaved)

            # Compute pixel difference
            ela_diff = ImageChops.difference(original, resaved)

            # Scale difference
            extrema = ela_diff.getextrema()
            max_diff = max([ex[1] for ex in extrema]) if extrema else 0
            scale_factor = 255.0 / max_diff if max_diff != 0 else 1.0

            enhancer = ImageEnhance.Brightness(ela_diff)
            ela_image = enhancer.enhance(scale_factor)

            ela_filename = f"ela_{Path(image_path).stem}.png"
            ela_output_path = settings.ephemeral_data_dir / ela_filename
            ela_image.save(ela_output_path, "PNG")

            # Clean up intermediate
            if temp_resaved.exists():
                temp_resaved.unlink()

            result["is_analyzed"] = True
            result["ela_image_filename"] = ela_filename
            result["compression_anomaly_detected"] = max_diff > 45
            result["forensic_notes"] = (
                f"Peak error difference: {max_diff}/255. "
                f"{'Noticeable high-frequency discrepancies detected; inspect bright highlights in ELA.' if max_diff > 45 else 'Uniform compression characteristics across surface.'}"
            )

        except Exception as e:
            result["error"] = str(e)

        return result

forensic_analyzer = MediaForensicAnalyzer()

