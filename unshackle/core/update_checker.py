from __future__ import annotations

import asyncio
from typing import Optional

import requests


class UpdateChecker:
    """Check for available updates from the GitHub repository."""

    REPO_URL = "https://api.github.com/repos/unshackle-dl/unshackle/releases/latest"
    TIMEOUT = 5

    @staticmethod
    def _compare_versions(current: str, latest: str) -> bool:
        """
        Simple semantic version comparison.

        Args:
            current: Current version string (e.g., "1.1.0")
            latest: Latest version string (e.g., "1.2.0")

        Returns:
            True if latest > current, False otherwise
        """
        try:
            current_parts = [int(x) for x in current.split(".")]
            latest_parts = [int(x) for x in latest.split(".")]

            max_length = max(len(current_parts), len(latest_parts))
            current_parts.extend([0] * (max_length - len(current_parts)))
            latest_parts.extend([0] * (max_length - len(latest_parts)))

            for current_part, latest_part in zip(current_parts, latest_parts):
                if latest_part > current_part:
                    return True
                elif latest_part < current_part:
                    return False

            return False
        except (ValueError, AttributeError):
            return False

    @classmethod
    async def check_for_updates(cls, current_version: str) -> Optional[str]:
        """
        Check if there's a newer version available on GitHub.

        Args:
            current_version: The current version string (e.g., "1.1.0")

        Returns:
            The latest version string if an update is available, None otherwise
        """
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: requests.get(cls.REPO_URL, timeout=cls.TIMEOUT))

            if response.status_code != 200:
                return None

            data = response.json()
            latest_version = data.get("tag_name", "").lstrip("v")

            if not latest_version:
                return None

            if cls._compare_versions(current_version, latest_version):
                return latest_version

        except Exception:
            pass

        return None

    @classmethod
    def check_for_updates_sync(cls, current_version: str) -> Optional[str]:
        """
        Synchronous version of update check.

        Args:
            current_version: The current version string (e.g., "1.1.0")

        Returns:
            The latest version string if an update is available, None otherwise
        """
        try:
            response = requests.get(cls.REPO_URL, timeout=cls.TIMEOUT)

            if response.status_code != 200:
                return None

            data = response.json()
            latest_version = data.get("tag_name", "").lstrip("v")

            if not latest_version:
                return None

            if cls._compare_versions(current_version, latest_version):
                return latest_version

        except Exception:
            pass

        return None
