import math
from datetime import datetime
from typing import Dict, Any

class SolarPositionCalculator:
    """
    Calculates solar elevation (altitude) and azimuth angle for given coordinates and datetime.
    Used in OSINT for shadow-length and time-of-day forensic analysis.
    """

    @staticmethod
    def calculate(lat: float, lon: float, dt: datetime = None) -> Dict[str, Any]:
        dt = dt or datetime.utcnow()
        # Day of the year
        day_of_year = dt.timetuple().tm_yday
        hour_fraction = dt.hour + (dt.minute / 60.0) + (dt.second / 3600.0)

        # Solar declination angle (approximate Cooper formula)
        declination_rad = math.radians(23.45 * math.sin(math.radians((360.0 / 365.0) * (284 + day_of_year))))
        declination_deg = math.degrees(declination_rad)

        # Equation of time (minutes)
        b = math.radians((360.0 / 365.0) * (day_of_year - 81))
        eot = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)

        # Solar time
        time_offset = (4.0 * lon) + eot
        true_solar_time = (hour_fraction * 60.0 + time_offset) % 1440.0
        solar_hour_angle = math.radians((true_solar_time / 4.0) - 180.0)

        # Solar altitude angle (elevation)
        lat_rad = math.radians(lat)
        sin_altitude = (math.sin(lat_rad) * math.sin(declination_rad) +
                        math.cos(lat_rad) * math.cos(declination_rad) * math.cos(solar_hour_angle))
        altitude_rad = math.asin(max(-1.0, min(1.0, sin_altitude)))
        altitude_deg = math.degrees(altitude_rad)

        # Solar azimuth angle
        cos_azimuth = ((math.sin(declination_rad) - math.sin(lat_rad) * math.sin(altitude_rad)) /
                       (math.cos(lat_rad) * math.cos(altitude_rad)))
        azimuth_deg = math.degrees(math.acos(max(-1.0, min(1.0, cos_azimuth))))
        if math.sin(solar_hour_angle) > 0:
            azimuth_deg = 360.0 - azimuth_deg

        # Shadow direction is opposite to sun azimuth
        shadow_direction_deg = (azimuth_deg + 180.0) % 360.0

        # Shadow multiplier = cotangent(altitude) if altitude > 0
        shadow_length_ratio = (1.0 / math.tan(altitude_rad)) if altitude_rad > 0.05 else None

        return {
            "latitude": lat,
            "longitude": lon,
            "utc_timestamp": dt.isoformat(),
            "solar_elevation_deg": round(altitude_deg, 2),
            "solar_azimuth_deg": round(azimuth_deg, 2),
            "shadow_direction_deg": round(shadow_direction_deg, 2),
            "shadow_length_multiplier": round(shadow_length_ratio, 2) if shadow_length_ratio else "Horizon/Night",
            "is_daylight": altitude_deg > 0
        }

solar_calculator = SolarPositionCalculator()

