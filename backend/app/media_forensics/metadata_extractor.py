import os
import hashlib
from typing import Dict, Any, Tuple, Optional
from PIL import Image
import exifread
import imagehash
from app.config import settings

class MediaMetadataExtractor:
    """Extracts camera, timestamp, GPS, and technical properties from media files."""

    @staticmethod
    def _convert_to_degrees(value) -> float:
        d = float(value.values[0].num) / float(value.values[0].den)
        m = float(value.values[1].num) / float(value.values[1].den)
        s = float(value.values[2].num) / float(value.values[2].den)
        return d + (m / 60.0) + (s / 3600.0)

    def extract(self, file_path: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "has_exif": False,
            "camera_make": None,
            "camera_model": None,
            "software": None,
            "datetime_original": None,
            "gps_coordinates": None,
            "dimensions": None,
            "format": None,
            "raw_tags": {}
        }

        actual_path = file_path
        if not os.path.exists(actual_path):
            candidate = settings.ephemeral_data_dir / file_path
            if candidate.exists():
                actual_path = str(candidate)

        if not os.path.exists(actual_path):
            return result

        try:
            with Image.open(actual_path) as img:
                result["dimensions"] = f"{img.width}x{img.height}"
                result["format"] = img.format

            with open(actual_path, "rb") as f:
                tags = exifread.process_file(f, details=False)

            if tags:
                result["has_exif"] = True
                if "Image Make" in tags:
                    result["camera_make"] = str(tags["Image Make"])
                if "Image Model" in tags:
                    result["camera_model"] = str(tags["Image Model"])
                if "Image Software" in tags:
                    result["software"] = str(tags["Image Software"])
                if "EXIF DateTimeOriginal" in tags:
                    result["datetime_original"] = str(tags["EXIF DateTimeOriginal"])

                # GPS Coordinates
                if "GPS GPSLatitude" in tags and "GPS GPSLongitude" in tags:
                    lat = self._convert_to_degrees(tags["GPS GPSLatitude"])
                    lat_ref = str(tags.get("GPS GPSLatitudeRef", "N"))
                    if lat_ref == "S":
                        lat = -lat

                    lon = self._convert_to_degrees(tags["GPS GPSLongitude"])
                    lon_ref = str(tags.get("GPS GPSLongitudeRef", "E"))
                    if lon_ref == "W":
                        lon = -lon

                    result["gps_coordinates"] = (round(lat, 6), round(lon, 6))

                for k, v in tags.items():
                    if not k.startswith("JPEGThumbnail"):
                        result["raw_tags"][k] = str(v)

        except Exception as e:
            result["error"] = str(e)

        return result

class MediaHashCalculator:
    """Calculates cryptographic and perceptual hashes for exact and near-duplicate matching."""

    @staticmethod
    def calculate(file_path: str) -> Dict[str, str]:
        hashes = {
            "md5": "",
            "sha256": "",
            "dhash": "",
            "phash": "",
            "ahash": ""
        }
        if not os.path.exists(file_path):
            return hashes

        # Crypto hashes
        with open(file_path, "rb") as f:
            data = f.read()
            hashes["md5"] = hashlib.md5(data).hexdigest()
            hashes["sha256"] = hashlib.sha256(data).hexdigest()

        # Perceptual hashes
        try:
            with Image.open(file_path) as img:
                hashes["dhash"] = str(imagehash.dhash(img))
                hashes["phash"] = str(imagehash.phash(img))
                hashes["ahash"] = str(imagehash.average_hash(img))
        except Exception:
            pass

        return hashes

metadata_extractor = MediaMetadataExtractor()
hash_calculator = MediaHashCalculator()

