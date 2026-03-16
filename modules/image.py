"""Image OSINT — EXIF extraction, reverse image search, face detection, geolocation."""

import asyncio
import hashlib
import io
from pathlib import Path
from typing import Any

import aiohttp

from ghost.core.config import Config


class ImageModule:
    """Image intelligence gathering."""

    def __init__(self, config: Config):
        self.config = config
        self.timeout = aiohttp.ClientTimeout(total=config.request_timeout)

    async def run(self, target: str, input_type: str = "image") -> dict[str, Any]:
        """Analyze an image file or URL."""
        image_data = await self._load_image(target)
        if not image_data:
            return {"error": f"Could not load image from {target}"}

        results = await asyncio.gather(
            self._extract_exif(target, image_data),
            self._reverse_image_search(target, image_data),
            self._detect_faces(image_data),
            self._extract_geolocation(target, image_data),
            return_exceptions=True,
        )

        keys = ["exif", "reverse_search", "faces", "geolocation"]
        data = {"source": target}
        for key, result in zip(keys, results):
            data[key] = result if not isinstance(result, Exception) else {"error": str(result)}

        # Image hash for tracking
        data["hashes"] = {
            "md5": hashlib.md5(image_data).hexdigest(),
            "sha256": hashlib.sha256(image_data).hexdigest(),
        }

        return data

    async def _load_image(self, target: str) -> bytes | None:
        """Load image from file path or URL."""
        if target.startswith(("http://", "https://")):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.get(target) as resp:
                        if resp.status == 200:
                            return await resp.read()
            except Exception:
                return None
        else:
            path = Path(target)
            if path.exists() and path.is_file():
                return path.read_bytes()
        return None

    async def _extract_exif(self, target: str, image_data: bytes) -> dict:
        """Extract EXIF metadata from image."""
        try:
            import exifread
            tags = exifread.process_file(io.BytesIO(image_data), details=False)

            exif = {}
            important_tags = {
                "Image Make": "camera_make",
                "Image Model": "camera_model",
                "Image DateTime": "datetime",
                "EXIF DateTimeOriginal": "datetime_original",
                "EXIF ExposureTime": "exposure",
                "EXIF FNumber": "f_number",
                "EXIF ISOSpeedRatings": "iso",
                "EXIF FocalLength": "focal_length",
                "EXIF LensModel": "lens",
                "Image Software": "software",
                "Image ImageWidth": "width",
                "Image ImageLength": "height",
                "GPS GPSLatitudeRef": "gps_lat_ref",
                "GPS GPSLatitude": "gps_lat",
                "GPS GPSLongitudeRef": "gps_lon_ref",
                "GPS GPSLongitude": "gps_lon",
                "GPS GPSAltitude": "gps_altitude",
            }

            for tag, name in important_tags.items():
                if tag in tags:
                    exif[name] = str(tags[tag])

            # All tags for completeness
            exif["all_tags"] = {str(k): str(v) for k, v in tags.items() if k != "JPEGThumbnail"}

            return exif
        except ImportError:
            # Fallback to Pillow
            try:
                from PIL import Image
                from PIL.ExifTags import TAGS
                img = Image.open(io.BytesIO(image_data))
                exif_data = img._getexif()
                if exif_data:
                    return {TAGS.get(k, k): str(v) for k, v in exif_data.items() if isinstance(v, (str, int, float))}
                return {"note": "No EXIF data found"}
            except Exception as e:
                return {"error": str(e)}

    async def _reverse_image_search(self, target: str, image_data: bytes) -> dict:
        """Perform reverse image search."""
        results = {"engines": []}

        # Google Custom Search (if API key available)
        if self.config.has_api_key("google_api_key") and self.config.has_api_key("google_cx"):
            if target.startswith("http"):
                try:
                    async with aiohttp.ClientSession(timeout=self.timeout) as session:
                        url = (
                            f"https://www.googleapis.com/customsearch/v1"
                            f"?key={self.config.google_api_key}"
                            f"&cx={self.config.google_cx}"
                            f"&searchType=image"
                            f"&q=image:{target}"
                        )
                        async with session.get(url) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                items = data.get("items", [])
                                results["engines"].append({
                                    "engine": "Google",
                                    "matches": [
                                        {"title": i["title"], "url": i["link"]}
                                        for i in items[:10]
                                    ],
                                })
                except Exception as e:
                    results["engines"].append({"engine": "Google", "error": str(e)})

        # Provide search URLs for manual checking
        if target.startswith("http"):
            results["manual_search_urls"] = {
                "google": f"https://lens.google.com/uploadbyurl?url={target}",
                "yandex": f"https://yandex.com/images/search?rpt=imageview&url={target}",
                "tineye": f"https://tineye.com/search?url={target}",
                "bing": f"https://www.bing.com/images/search?view=detailv2&iss=SBI&q=imgurl:{target}",
            }

        return results

    async def _detect_faces(self, image_data: bytes) -> dict:
        """Detect faces in the image."""
        try:
            import face_recognition
            import numpy as np
            from PIL import Image

            img = Image.open(io.BytesIO(image_data))
            img_array = np.array(img)

            face_locations = face_recognition.face_locations(img_array)
            face_encodings = face_recognition.face_encodings(img_array, face_locations)

            faces = []
            for i, (location, encoding) in enumerate(zip(face_locations, face_encodings)):
                top, right, bottom, left = location
                faces.append({
                    "id": i,
                    "bounding_box": {"top": top, "right": right, "bottom": bottom, "left": left},
                    "encoding_hash": hashlib.md5(encoding.tobytes()).hexdigest(),
                })

            return {"face_count": len(faces), "faces": faces}
        except ImportError:
            return {"note": "face_recognition not installed", "face_count": None}
        except Exception as e:
            return {"error": str(e)}

    async def _extract_geolocation(self, target: str, image_data: bytes) -> dict:
        """Extract GPS coordinates from EXIF and resolve to address."""
        try:
            import exifread
            tags = exifread.process_file(io.BytesIO(image_data))

            lat = tags.get("GPS GPSLatitude")
            lat_ref = tags.get("GPS GPSLatitudeRef")
            lon = tags.get("GPS GPSLongitude")
            lon_ref = tags.get("GPS GPSLongitudeRef")

            if not all([lat, lat_ref, lon, lon_ref]):
                return {"found": False, "note": "No GPS data in image"}

            lat_decimal = self._dms_to_decimal(lat.values, str(lat_ref))
            lon_decimal = self._dms_to_decimal(lon.values, str(lon_ref))

            result = {
                "found": True,
                "latitude": lat_decimal,
                "longitude": lon_decimal,
            }

            # Reverse geocode
            try:
                from geopy.geocoders import Nominatim
                geolocator = Nominatim(user_agent="ghost-osint")
                location = geolocator.reverse(f"{lat_decimal}, {lon_decimal}")
                if location:
                    result["address"] = location.address
                    result["raw"] = location.raw.get("address", {})
            except Exception:
                pass

            return result
        except Exception as e:
            return {"found": False, "error": str(e)}

    @staticmethod
    def _dms_to_decimal(dms, ref: str) -> float:
        """Convert degrees/minutes/seconds to decimal."""
        d = float(dms[0].num) / float(dms[0].den)
        m = float(dms[1].num) / float(dms[1].den)
        s = float(dms[2].num) / float(dms[2].den)
        decimal = d + m / 60 + s / 3600
        if ref in ("S", "W"):
            decimal = -decimal
        return decimal
