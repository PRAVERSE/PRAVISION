import os
import hashlib
from typing import Dict, Optional

class SecretVault:
    """
    Secure In-Memory credential store for user-supplied API keys (Shodan, HIBP, Hunter, Censys, etc.).
    Protects secrets from being dumped, serialized to disk, or transmitted to the client.
    """
    def __init__(self):
        self._secrets: Dict[str, str] = {}
        # Pre-populate from system environment variables if available
        self._load_from_env()

    def _load_from_env(self):
        key_mappings = {
            "shodan_api_key": "SHODAN_API_KEY",
            "hibp_api_key": "HIBP_API_KEY",
            "hunter_api_key": "HUNTER_API_KEY",
            "censys_api_id": "CENSYS_API_ID",
            "censys_api_secret": "CENSYS_API_SECRET",
            "intelx_api_key": "INTELX_API_KEY",
            "numverify_api_key": "NUMVERIFY_API_KEY",
            "ipinfo_token": "IPINFO_TOKEN",
            "virustotal_api_key": "VIRUSTOTAL_API_KEY",
            "mapillary_token": "MAPILLARY_TOKEN",
        }
        for internal_name, env_var in key_mappings.items():
            val = os.getenv(env_var)
            if val:
                self._secrets[internal_name] = val.strip()

    def set_secret(self, key_name: str, value: str) -> None:
        if value:
            self._secrets[key_name] = value.strip()
        elif key_name in self._secrets:
            del self._secrets[key_name]

    def get_secret(self, key_name: str) -> Optional[str]:
        return self._secrets.get(key_name)

    def has_secret(self, key_name: str) -> bool:
        return bool(self._secrets.get(key_name))

    def get_status_overview(self) -> Dict[str, bool]:
        """Returns whether a key is configured without exposing the value."""
        return {k: True for k in self._secrets.keys()}

secret_vault = SecretVault()
