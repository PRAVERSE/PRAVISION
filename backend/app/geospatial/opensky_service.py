import time
import httpx
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("pravision.geospatial.opensky")

OPENSKY_STATES_URL = "https://opensky-network.org/api/states/all"
CACHE_TTL_SECONDS = 15  # Minimum cache TTL to respect OpenSky rate limits
REQUEST_TIMEOUT_SECONDS = 8.0

class OpenSkyService:
    """
    Dedicated OpenSky Flight Telemetry Connector.
    Proxies, normalizes, caches, and attributes global flight data through FastAPI,
    bypassing browser CORS restrictions and shielding upstream servers from rate spikes.
    """

    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._cache_timestamp: float = 0.0
        self._last_successful_update: Optional[str] = None
        self._consecutive_failures: int = 0
        self._last_error: Optional[str] = None

    def validate_bounding_box(
        self,
        lamin: float,
        lomin: float,
        lamax: float,
        lomax: float
    ) -> Tuple[float, float, float, float]:
        """Validates geospatial coordinate bounds."""
        if not (-90.0 <= lamin <= 90.0 and -90.0 <= lamax <= 90.0):
            raise ValueError(f"Latitude must be between -90.0 and 90.0 (received lamin={lamin}, lamax={lamax}).")
        if not (-180.0 <= lomin <= 180.0 and -180.0 <= lomax <= 180.0):
            raise ValueError(f"Longitude must be between -180.0 and 180.0 (received lomin={lomin}, lomax={lomax}).")
        if lamin > lamax:
            raise ValueError("lamin cannot be greater than lamax.")
        if lomin > lomax:
            raise ValueError("lomin cannot be greater than lomax.")
        return lamin, lomin, lamax, lomax

    async def get_flights(
        self,
        lamin: float = 20.0,
        lomin: float = -125.0,
        lamax: float = 50.0,
        lomax: float = -65.0,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Retrieves real-time aircraft telemetry within a geospatial bounding box.
        Applies in-memory TTL caching and graceful stale-data fallback.
        """
        self.validate_bounding_box(lamin, lomin, lamax, lomax)
        cache_key = f"{round(lamin, 1)}_{round(lomin, 1)}_{round(lamax, 1)}_{round(lomax, 1)}"
        now = time.time()

        # Check Cache
        cached = self._cache.get(cache_key)
        if not force_refresh and cached and (now - self._cache_timestamp) < CACHE_TTL_SECONDS:
            return {
                **cached,
                "cached": True,
                "cache_age_seconds": round(now - self._cache_timestamp, 1)
            }

        params = {
            "lamin": lamin,
            "lomin": lomin,
            "lamax": lamax,
            "lomax": lomax
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                res = await client.get(
                    OPENSKY_STATES_URL,
                    params=params,
                    headers={"User-Agent": "PRAVISION-OSINT-Intelligence-Platform/2.5"}
                )

            if res.status_code == 200:
                raw_data = res.json()
                states = raw_data.get("states") or []
                normalized_aircraft = self._normalize_states(states)

                result = {
                    "status": "operational",
                    "source": "OpenSky Network",
                    "attribution": "Flight telemetry provided by The OpenSky Network (https://opensky-network.org)",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "is_stale": False,
                    "bounding_box": {"lamin": lamin, "lomin": lomin, "lamax": lamax, "lomax": lomax},
                    "total_aircraft": len(normalized_aircraft),
                    "aircraft": normalized_aircraft,
                    "cached": False
                }

                self._cache[cache_key] = result
                self._cache_timestamp = now
                self._last_successful_update = result["timestamp"]
                self._consecutive_failures = 0
                self._last_error = None
                return result

            elif res.status_code == 429:
                self._last_error = "OpenSky rate limit reached (HTTP 429)."
                logger.warning(self._last_error)
            else:
                self._last_error = f"OpenSky upstream responded with HTTP {res.status_code}."
                logger.warning(self._last_error)

        except Exception as e:
            self._last_error = f"Upstream communication error: {str(e)}"
            logger.warning(self._last_error)

        self._consecutive_failures += 1

        # Fallback to stale cached data if available
        if cached:
            logger.info("Serving stale cached flight telemetry due to upstream unavailability.")
            return {
                **cached,
                "is_stale": True,
                "stale_reason": self._last_error,
                "last_successful_update": self._last_successful_update,
                "cached": True
            }

        # No cache available: return truthful degraded status
        return {
            "status": "degraded",
            "source": "OpenSky Network",
            "attribution": "The OpenSky Network (https://opensky-network.org)",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "is_stale": True,
            "error": self._last_error or "Flight telemetry temporarily unavailable.",
            "total_aircraft": 0,
            "aircraft": []
        }

    def _normalize_states(self, states: List[List[Any]]) -> List[Dict[str, Any]]:
        """Transforms raw OpenSky state vectors into standardized, typed aircraft telemetry."""
        aircraft_list = []
        for s in states:
            if not isinstance(s, list) or len(s) < 11:
                continue
            lon = s[5]
            lat = s[6]
            if lon is None or lat is None:
                continue

            callsign = s[1].strip() if s[1] else "UNKNOWN"
            aircraft_list.append({
                "icao24": s[0],
                "callsign": callsign,
                "origin_country": s[2],
                "longitude": float(lon),
                "latitude": float(lat),
                "baro_altitude_meters": float(s[7]) if s[7] is not None else None,
                "on_ground": bool(s[8]),
                "velocity_mps": float(s[9]) if s[9] is not None else None,
                "heading_degrees": float(s[10]) if s[10] is not None else 0.0,
                "vertical_rate_mps": float(s[11]) if len(s) > 11 and s[11] is not None else None,
                "geo_altitude_meters": float(s[13]) if len(s) > 13 and s[13] is not None else None,
                "squawk": str(s[14]) if len(s) > 14 and s[14] is not None else None,
                "last_contact": s[4]
            })
        return aircraft_list

    def get_health(self) -> Dict[str, Any]:
        """Reports telemetry connector health and cache statistics."""
        return {
            "service": "OpenSky Telemetry Gateway",
            "status": "healthy" if self._consecutive_failures == 0 else "degraded",
            "last_successful_update": self._last_successful_update,
            "consecutive_failures": self._consecutive_failures,
            "last_error": self._last_error,
            "cache_entries": len(self._cache),
            "cache_ttl_seconds": CACHE_TTL_SECONDS
        }

    def get_coverage(self) -> Dict[str, Any]:
        return {
            "provider": "OpenSky Network",
            "coverage_type": "Global ADS-B / Mode S",
            "supported_parameters": ["lamin", "lomin", "lamax", "lomax"],
            "max_poll_rate": "1 request / 10-15s (Anonymous Tier)",
            "license": "Open Data / Attribution Required",
            "attribution_url": "https://opensky-network.org"
        }

opensky_service = OpenSkyService()

