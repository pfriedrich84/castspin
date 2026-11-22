# SPDX-License-Identifier: Apache-2.0
"""Validated Supervisor options; secrets never enter the public status object."""
from dataclasses import dataclass, field
from ipaddress import IPv4Address
import json
from pathlib import Path
from urllib.parse import urlsplit


class ConfigurationError(ValueError):
    """Only deliberately safe local validation messages may reach Ingress."""


@dataclass(frozen=True)
class Settings:
    enabled: bool = False
    music_assistant_url: str = ""
    music_assistant_token: str = field(default="", repr=False)
    network_address: str = ""
    player_port: int = 18010

    @classmethod
    def load(cls, path: Path):
        if not path.exists():
            return cls()
        if path.stat().st_size > 65536:
            raise ConfigurationError("Options file is too large")
        try:
            raw = json.loads(path.read_text())
            if not isinstance(raw, dict):
                raise ValueError
            value = cls(**raw)
        except (ValueError, TypeError):
            raise ConfigurationError("Invalid App options") from None
        value.validate()
        return value

    def validate(self):
        if type(self.enabled) is not bool:
            raise ConfigurationError("enabled must be a boolean")
        if not self.enabled:
            return
        try:
            parts = urlsplit(self.music_assistant_url)
            valid = (parts.scheme in {"http", "https"} and parts.hostname
                     and parts.username is None and parts.password is None
                     and not parts.query and not parts.fragment and parts.port != 0
                     and not any(c.isspace() for c in self.music_assistant_url))
            if not valid:
                raise ValueError
        except (TypeError, ValueError, AttributeError):
            raise ConfigurationError("Set a valid Music Assistant HTTP(S) base URL without credentials") from None
        if (not isinstance(self.music_assistant_token, str)
                or not 1 <= len(self.music_assistant_token) <= 8192
                or any(c.isspace() for c in self.music_assistant_token)):
            raise ConfigurationError("Set the Music Assistant access token in App configuration")
        try:
            address = IPv4Address(self.network_address)
            if address.is_unspecified or address.is_multicast or int(address) == 0xffffffff:
                raise ValueError
        except (ValueError, TypeError):
            raise ConfigurationError("Set this Home Assistant host's LAN IPv4 address") from None
        if type(self.player_port) is not int or not 1024 <= self.player_port <= 65535 or self.player_port == 8099:
            raise ConfigurationError("player_port must be 1024–65535 and different from the Ingress port")
