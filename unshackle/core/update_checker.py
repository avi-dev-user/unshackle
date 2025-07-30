from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Optional

import requests


class UpdateChecker:
    """Check for available updates from the GitHub repository."""

    REPO_URL = "https://api.github.com/repos/unshackle-dl/unshackle/releases/latest"
    TIMEOUT = 5
    DEFAULT_CHECK_INTERVAL = 24 * 60 * 60  # 24 hours in seconds

    @classmethod
    def _get_cache_file(cls) -> Path:
        """Get the path to the update check cache file."""
        from unshackle.core.config import config

        return config.directories.cache / "update_check.json"

    @classmethod
    def _should_check_for_updates(cls, check_interval: int = DEFAULT_CHECK_INTERVAL) -> bool:
        """
        Check if enough time has passed since the last update check.

        Args:
            check_interval: Time in seconds between checks (default: 24 hours)

        Returns:
            True if we should check for updates, False otherwise
        """
        cache_file = cls._get_cache_file()

        if not cache_file.exists():
            return True

        try:
            with open(cache_file, "r") as f:
                cache_data = json.load(f)

            last_check = cache_data.get("last_check", 0)
            current_time = time.time()

            return (current_time - last_check) >= check_interval

        except (json.JSONDecodeError, KeyError, OSError):
            # If cache is corrupted or unreadable, allow check
            return True

    @classmethod
    def _update_cache(cls, latest_version: Optional[str] = None) -> None:
        """
        Update the cache file with the current timestamp and latest version.

        Args:
            latest_version: The latest version found, if any
        """
        cache_file = cls._get_cache_file()

        try:
            # Ensure cache directory exists
            cache_file.parent.mkdir(parents=True, exist_ok=True)

            cache_data = {"last_check": time.time(), "latest_version": latest_version}

            with open(cache_file, "w") as f:
                json.dump(cache_data, f)

        except (OSError, json.JSONEncodeError):
            # Silently fail if we can't write cache
            pass

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
    def check_for_updates_sync(cls, current_version: str, check_interval: Optional[int] = None) -> Optional[str]:
        """
        Synchronous version of update check with rate limiting.

        Args:
            current_version: The current version string (e.g., "1.1.0")
            check_interval: Time in seconds between checks (default: from config)

        Returns:
            The latest version string if an update is available, None otherwise
        """
        # Use config value if not specified
        if check_interval is None:
            from unshackle.core.config import config

            check_interval = config.update_check_interval * 60 * 60  # Convert hours to seconds

        # Check if we should skip this check due to rate limiting
        if not cls._should_check_for_updates(check_interval):
            return None

        try:
            response = requests.get(cls.REPO_URL, timeout=cls.TIMEOUT)

            if response.status_code != 200:
                # Update cache even on failure to prevent rapid retries
                cls._update_cache()
                return None

            data = response.json()
            latest_version = data.get("tag_name", "").lstrip("v")

            if not latest_version:
                cls._update_cache()
                return None

            # Update cache with the latest version info
            cls._update_cache(latest_version)

            if cls._compare_versions(current_version, latest_version):
                return latest_version

        except Exception:
            # Update cache even on exception to prevent rapid retries
            cls._update_cache()
            pass

        return None
