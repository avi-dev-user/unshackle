import base64
import secrets
from typing import Optional, Type, Union
from uuid import UUID

import requests
from pyplayready.cdm import Cdm as PlayReadyCdm
from pywidevine import PSSH, Device, DeviceTypes, Key, RemoteCdm
from pywidevine.license_protocol_pb2 import SignedDrmCertificate, SignedMessage

# Copyright 2024 by DevYukine.
# Copyright 2025 by sp4rk.y.


class DecryptLabsRemoteCDM(RemoteCdm):
    """Remote CDM implementation for DecryptLabs KeyXtractor API.

    Provides CDM functionality through DecryptLabs' remote API service,
    supporting multiple DRM schemes including Widevine and PlayReady.
    """

    def __init__(
        self,
        device_type: Union[DeviceTypes, str],
        system_id: int,
        security_level: int,
        host: str,
        secret: str,
        device_name: str,
        service_name: str,
        vaults=None,
    ):
        """Initialize DecryptLabs Remote CDM.

        Args:
            device_type: Type of device to emulate
            system_id: System identifier
            security_level: DRM security level
            host: DecryptLabs API host URL
            secret: DecryptLabs API key for authentication
            device_name: Device/scheme name (used as scheme identifier)
            service_name: Service/platform name
            vaults: Optional vaults reference for caching keys
        """
        self.response_counter = 0
        self.pssh = None
        self.api_session_ids = {}
        self.license_request = None
        self.service_name = service_name
        self.device_name = device_name
        self.keys = {}
        self.scheme = device_name
        self._has_cached_keys = False
        self.vaults = vaults
        self.security_level = security_level
        self.host = host

        class MockCertificateChain:
            """Mock certificate chain for DecryptLabs remote CDM compatibility."""

            def __init__(self, scheme: str, security_level: int):
                self.scheme = scheme
                self.security_level = security_level

            def get_name(self) -> str:
                """Return the certificate chain name for logging."""
                return f"DecryptLabs-{self.scheme}"

            def get_security_level(self) -> int:
                """Return the security level."""
                return self.security_level

        self.certificate_chain = MockCertificateChain(self.scheme, security_level)
        try:
            super().__init__(device_type, system_id, security_level, host, secret, device_name)
        except Exception:
            pass
        self.req_session = requests.Session()
        self.req_session.headers.update({"decrypt-labs-api-key": secret})

    @classmethod
    def from_device(cls, device: Device) -> Type["DecryptLabsRemoteCDM"]:
        raise NotImplementedError("You cannot load a DecryptLabsRemoteCDM from a local Device file.")

    def open(self) -> bytes:
        """Open a new CDM session.

        Returns:
            Random session ID bytes for internal tracking
        """
        return bytes.fromhex(secrets.token_hex(16))

    def close(self, session_id: bytes) -> None:
        """Close a CDM session.

        Args:
            session_id: Session identifier to close
        """
        pass

    def set_service_certificate(self, session_id: bytes, certificate: Optional[Union[bytes, str]]) -> str:
        """Set service certificate for L1/L2 schemes.

        Args:
            session_id: Session identifier
            certificate: Service certificate (bytes or base64 string)

        Returns:
            Success status string
        """
        if isinstance(certificate, bytes):
            certificate = base64.b64encode(certificate).decode()

        self.service_certificate = certificate
        self.privacy_mode = True

        return "success"

    def get_service_certificate(self, session_id: bytes) -> Optional[SignedDrmCertificate]:
        raise NotImplementedError("This method is not implemented in this CDM")

    def get_license_challenge(
        self, session_id: bytes, pssh: PSSH, license_type: str = "STREAMING", privacy_mode: bool = True
    ) -> bytes:
        """Generate license challenge using DecryptLabs API.

        Args:
            session_id: Session identifier
            pssh: PSSH initialization data
            license_type: Type of license (default: "STREAMING")
            privacy_mode: Enable privacy mode

        Returns:
            License challenge bytes or empty bytes if using cached keys
        """
        self.pssh = pssh

        scheme_to_use = self.scheme
        try:
            pssh_data = pssh.dumps()
            if b"edef8ba9-79d6-4ace-a3c8-27dcd51d21ed" in pssh_data or "edef8ba979d64acea3c827dcd51d21ed" in pssh_data:
                if self.scheme in ["SL2", "SL3"]:
                    scheme_to_use = "L1" if self.scheme == "SL2" else "L1"
                else:
                    scheme_to_use = self.scheme
        except Exception:
            scheme_to_use = self.scheme

        request_data = {
            "init_data": self.pssh.dumps(),
            "scheme": scheme_to_use,
            "service": self.service_name,
        }

        if scheme_to_use in ["L1", "L2"] and hasattr(self, "service_certificate"):
            request_data["service_certificate"] = self.service_certificate
        elif scheme_to_use in ["L1", "L2"]:
            pass

        request_data["get_cached_keys_if_exists"] = True

        if not hasattr(self, "session_schemes"):
            self.session_schemes = {}
        self.session_schemes[session_id] = scheme_to_use
        res = self.session(
            self.host + "/get-request",
            request_data,
        )

        if res.get("message_type") == "cached-keys":
            if session_id not in self.keys:
                self.keys[session_id] = []
            session_keys = self.keys[session_id]

            cached_keys_for_vault = {}

            for cached_key in res.get("cached_keys", []):
                kid_str = cached_key["kid"]
                try:
                    kid_uuid = UUID(kid_str)
                except ValueError:
                    try:
                        kid_uuid = UUID(bytes=bytes.fromhex(kid_str))
                    except ValueError:
                        kid_uuid = Key.kid_to_uuid(kid_str)

                session_keys.append(Key(kid=kid_uuid, type_="CONTENT", key=bytes.fromhex(cached_key["key"])))
                cached_keys_for_vault[kid_uuid] = cached_key["key"]

            if self.vaults and cached_keys_for_vault:
                try:
                    self.vaults.add_keys(cached_keys_for_vault)
                except Exception:
                    pass

            if self.service_name == "NF" or "netflix" in self.service_name.lower():
                request_data_no_cache = request_data.copy()
                request_data_no_cache["get_cached_keys_if_exists"] = False

                res_challenge = self.session(
                    self.host + "/get-request",
                    request_data_no_cache,
                )

                if res_challenge.get("challenge"):
                    self.license_request = res_challenge["challenge"]
                    self.api_session_ids[session_id] = res_challenge.get("session_id")
                    return base64.b64decode(self.license_request)

            self.license_request = ""
            self.api_session_ids[session_id] = None
            self._has_cached_keys = True
            return b""

        self.license_request = res["challenge"]
        self.api_session_ids[session_id] = res["session_id"]
        self._has_cached_keys = False

        return base64.b64decode(self.license_request)

    def parse_license(self, session_id: bytes, license_message: Union[SignedMessage, bytes, str]) -> None:
        """Parse license response and extract decryption keys.

        Args:
            session_id: Session identifier
            license_message: License response from DRM server
        """
        session_id_api = self.api_session_ids[session_id]
        if session_id not in self.keys:
            self.keys[session_id] = []
        session_keys = self.keys[session_id]

        if session_id_api is None and session_keys:
            return

        if isinstance(license_message, dict) and "keys" in license_message:
            session_keys.extend(
                [
                    Key(kid=Key.kid_to_uuid(x["kid"]), type_=x.get("type", "CONTENT"), key=bytes.fromhex(x["key"]))
                    for x in license_message["keys"]
                ]
            )

        else:
            if isinstance(license_message, bytes):
                license_response_b64 = base64.b64encode(license_message).decode()
            elif isinstance(license_message, str):
                license_response_b64 = license_message
            else:
                license_response_b64 = str(license_message)
            scheme_for_session = getattr(self, "session_schemes", {}).get(session_id, self.scheme)

            res = self.session(
                self.host + "/decrypt-response",
                {
                    "session_id": session_id_api,
                    "init_data": self.pssh.dumps(),
                    "license_request": self.license_request,
                    "license_response": license_response_b64,
                    "scheme": scheme_for_session,
                },
            )

            if scheme_for_session in ["SL2", "SL3"]:
                if "keys" in res and res["keys"]:
                    keys_data = res["keys"]
                    if isinstance(keys_data, str):
                        original_keys = keys_data.replace("\n", " ")
                        keys_separated = original_keys.split("--key ")
                        for k in keys_separated:
                            if ":" in k:
                                key_parts = k.strip().split(":")
                                if len(key_parts) == 2:
                                    try:
                                        kid_hex, key_hex = key_parts
                                        session_keys.append(
                                            Key(
                                                kid=UUID(bytes=bytes.fromhex(kid_hex)),
                                                type_="CONTENT",
                                                key=bytes.fromhex(key_hex),
                                            )
                                        )
                                    except (ValueError, TypeError):
                                        continue
                    elif isinstance(keys_data, list):
                        for key_info in keys_data:
                            if isinstance(key_info, dict) and "kid" in key_info and "key" in key_info:
                                session_keys.append(
                                    Key(
                                        kid=Key.kid_to_uuid(key_info["kid"]),
                                        type_=key_info.get("type", "CONTENT"),
                                        key=bytes.fromhex(key_info["key"]),
                                    )
                                )
            else:
                original_keys = res["keys"].replace("\n", " ")
                keys_separated = original_keys.split("--key ")
                formatted_keys = []
                for k in keys_separated:
                    if ":" in k:
                        key = k.strip()
                        formatted_keys.append(key)
                for keys in formatted_keys:
                    session_keys.append(
                        Key(
                            kid=UUID(bytes=bytes.fromhex(keys.split(":")[0])),
                            type_="CONTENT",
                            key=bytes.fromhex(keys.split(":")[1]),
                        )
                    )

    def get_keys(self, session_id: bytes, type_: Optional[Union[int, str]] = None) -> list[Key]:
        """Get decryption keys for a session.

        Args:
            session_id: Session identifier
            type_: Key type filter (optional)

        Returns:
            List of decryption keys for the session
        """
        return self.keys[session_id]

    def has_cached_keys(self, session_id: bytes) -> bool:
        """Check if this session has cached keys and doesn't need license request.

        Args:
            session_id: Session identifier to check

        Returns:
            True if session has cached keys, False otherwise
        """
        return getattr(self, "_has_cached_keys", False) and session_id in self.keys and len(self.keys[session_id]) > 0

    def session(self, url, data, retries=3):
        """Make authenticated request to DecryptLabs API.

        Args:
            url: API endpoint URL
            data: Request payload data
            retries: Number of retry attempts for failed requests

        Returns:
            API response JSON data

        Raises:
            ValueError: If API returns an error after retries
        """
        res = self.req_session.post(url, json=data).json()

        if res.get("message") != "success":
            if "License Response Decryption Process Failed at the very beginning" in res.get("Error", ""):
                if retries > 0:
                    return self.session(url, data, retries=retries - 1)
                else:
                    raise ValueError(f"CDM API returned an error: {res['Error']}")
            else:
                raise ValueError(f"CDM API returned an error: {res['Error']}")

        return res

    def use_cached_keys_as_fallback(self, session_id: bytes) -> bool:
        """Use cached keys from DecryptLabs as a fallback when license server fails.

        Args:
            session_id: Session identifier

        Returns:
            True if cached keys were successfully applied, False otherwise
        """
        if not hasattr(self, "_cached_keys_available") or not self._cached_keys_available:
            return False

        if session_id not in self.keys:
            self.keys[session_id] = []
        session_keys = self.keys[session_id]

        cached_keys_for_vault = {}

        for cached_key in self._cached_keys_available:
            kid_str = cached_key["kid"]
            try:
                kid_uuid = UUID(kid_str)
            except ValueError:
                try:
                    kid_uuid = UUID(bytes=bytes.fromhex(kid_str))
                except ValueError:
                    kid_uuid = Key.kid_to_uuid(kid_str)

            session_keys.append(Key(kid=kid_uuid, type_="CONTENT", key=bytes.fromhex(cached_key["key"])))
            cached_keys_for_vault[kid_uuid] = cached_key["key"]

        if self.vaults and cached_keys_for_vault:
            try:
                self.vaults.add_keys(cached_keys_for_vault)
            except Exception:
                pass

        self._has_cached_keys = True
        return True


class DecryptLabsRemotePlayReadyCDM(PlayReadyCdm):
    """PlayReady Remote CDM implementation for DecryptLabs KeyXtractor API.

    Provides PlayReady CDM functionality through DecryptLabs' remote API service,
    supporting PlayReady DRM schemes like SL2 and SL3.
    """

    def __init__(
        self,
        security_level: int,
        host: str,
        secret: str,
        device_name: str,
        service_name: str,
        vaults=None,
        client_version: str = "10.0.16384.10011",
    ):
        """Initialize DecryptLabs Remote PlayReady CDM.

        Args:
            security_level: DRM security level
            host: DecryptLabs API host URL
            secret: DecryptLabs API key for authentication
            device_name: Device/scheme name (used as scheme identifier)
            service_name: Service/platform name
            vaults: Optional vaults reference for caching keys
            client_version: PlayReady client version
        """
        super().__init__(
            security_level=security_level,
            certificate_chain=None,
            encryption_key=None,
            signing_key=None,
            client_version=client_version,
        )

        self.host = host
        self.service_name = service_name
        self.device_name = device_name
        self.scheme = device_name
        self.vaults = vaults
        self.keys = {}
        self.api_session_ids = {}
        self.pssh_b64 = None
        self.license_request = None
        self._has_cached_keys = False

        self.req_session = requests.Session()
        self.req_session.headers.update({"decrypt-labs-api-key": secret})

        class MockCertificateChain:
            """Mock certificate chain for DecryptLabs remote CDM compatibility."""

            def __init__(self, scheme: str, security_level: int):
                self.scheme = scheme
                self.security_level = security_level

            def get_name(self) -> str:
                """Return the certificate chain name for logging."""
                return f"DecryptLabs-{self.scheme}"

            def get_security_level(self) -> int:
                """Return the security level."""
                return self.security_level

        self.certificate_chain = MockCertificateChain(self.scheme, security_level)

    def set_pssh_b64(self, pssh_b64: str):
        """Set the original base64-encoded PSSH box for DecryptLabs API.

        Args:
            pssh_b64: Base64-encoded PSSH box from the manifest
        """
        self.pssh_b64 = pssh_b64

    def open(self) -> bytes:
        """Open a new CDM session.

        Returns:
            Random session ID bytes for internal tracking
        """
        return bytes.fromhex(secrets.token_hex(16))

    def close(self, session_id: bytes) -> None:
        """Close a CDM session.

        Args:
            session_id: Session identifier to close
        """
        pass

    def get_license_challenge(self, session_id: bytes, _) -> str:
        """Generate license challenge using DecryptLabs API for PlayReady.

        Args:
            session_id: Session identifier

        Returns:
            License challenge as XML string
        """
        if not (hasattr(self, "pssh_b64") and self.pssh_b64):
            raise ValueError("DecryptLabs CDM requires original PSSH box data. Call set_pssh_b64() first.")

        init_data = self.pssh_b64

        request_data = {
            "init_data": init_data,
            "scheme": self.scheme,
            "service": self.service_name,
            "get_cached_keys_if_exists": False,
        }

        res = self.session(
            self.host + "/get-request",
            request_data,
        )

        if res.get("message_type") == "cached-keys":
            self._cached_keys_available = res.get("cached_keys", [])
        else:
            self._cached_keys_available = None

        self.license_request = res["challenge"]
        self.api_session_ids[session_id] = res["session_id"]
        self._has_cached_keys = False

        try:
            return base64.b64decode(self.license_request).decode()
        except Exception:
            return self.license_request

    def parse_license(self, session_id: bytes, license_message: str) -> None:
        """Parse license response and extract decryption keys.

        Args:
            session_id: Session identifier
            license_message: License response from DRM server (XML string)
        """
        session_id_api = self.api_session_ids[session_id]
        if session_id not in self.keys:
            self.keys[session_id] = []
        session_keys = self.keys[session_id]

        if session_id_api is None and session_keys:
            return

        try:
            license_response_b64 = base64.b64encode(license_message.encode("utf-8")).decode("utf-8")
        except Exception:
            return

        if not (hasattr(self, "pssh_b64") and self.pssh_b64):
            raise ValueError("DecryptLabs CDM requires original PSSH box data. Call set_pssh_b64() first.")
        init_data = self.pssh_b64

        res = self.session(
            self.host + "/decrypt-response",
            {
                "session_id": session_id_api,
                "init_data": init_data,
                "license_request": self.license_request,
                "license_response": license_response_b64,
                "scheme": self.scheme,
            },
        )

        if "keys" in res and res["keys"]:
            keys_data = res["keys"]
            if isinstance(keys_data, str):
                original_keys = keys_data.replace("\n", " ")
                keys_separated = original_keys.split("--key ")
                for k in keys_separated:
                    if ":" in k:
                        key_parts = k.strip().split(":")
                        if len(key_parts) == 2:
                            try:
                                kid_hex, key_hex = key_parts
                                session_keys.append(
                                    Key(
                                        kid=UUID(bytes=bytes.fromhex(kid_hex)),
                                        type_="CONTENT",
                                        key=bytes.fromhex(key_hex),
                                    )
                                )
                            except (ValueError, TypeError):
                                continue
            elif isinstance(keys_data, list):
                for key_info in keys_data:
                    if isinstance(key_info, dict) and "kid" in key_info and "key" in key_info:
                        session_keys.append(
                            Key(
                                kid=Key.kid_to_uuid(key_info["kid"]),
                                type_=key_info.get("type", "CONTENT"),
                                key=bytes.fromhex(key_info["key"]),
                            )
                        )

    def get_keys(self, session_id: bytes) -> list:
        """Get decryption keys for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of decryption keys for the session
        """
        return self.keys.get(session_id, [])

    def has_cached_keys(self, session_id: bytes) -> bool:
        """Check if this session has cached keys and doesn't need license request.

        Args:
            session_id: Session identifier to check

        Returns:
            True if session has cached keys, False otherwise
        """
        return getattr(self, "_has_cached_keys", False) and session_id in self.keys and len(self.keys[session_id]) > 0

    def session(self, url, data, retries=3):
        """Make authenticated request to DecryptLabs API.

        Args:
            url: API endpoint URL
            data: Request payload data
            retries: Number of retry attempts for failed requests

        Returns:
            API response JSON data

        Raises:
            ValueError: If API returns an error after retries
        """
        res = self.req_session.post(url, json=data).json()

        if res.get("message") != "success":
            if "License Response Decryption Process Failed at the very beginning" in res.get("Error", ""):
                if retries > 0:
                    return self.session(url, data, retries=retries - 1)
                else:
                    raise ValueError(f"CDM API returned an error: {res['Error']}")
            else:
                raise ValueError(f"CDM API returned an error: {res['Error']}")

        return res

    def use_cached_keys_as_fallback(self, session_id: bytes) -> bool:
        """Use cached keys from DecryptLabs as a fallback when license server fails.

        Args:
            session_id: Session identifier

        Returns:
            True if cached keys were successfully applied, False otherwise
        """
        if not hasattr(self, "_cached_keys_available") or not self._cached_keys_available:
            return False

        if session_id not in self.keys:
            self.keys[session_id] = []
        session_keys = self.keys[session_id]

        cached_keys_for_vault = {}

        for cached_key in self._cached_keys_available:
            kid_str = cached_key["kid"]
            try:
                kid_uuid = UUID(kid_str)
            except ValueError:
                try:
                    kid_uuid = UUID(bytes=bytes.fromhex(kid_str))
                except ValueError:
                    kid_uuid = Key.kid_to_uuid(kid_str)

            session_keys.append(Key(kid=kid_uuid, type_="CONTENT", key=bytes.fromhex(cached_key["key"])))
            cached_keys_for_vault[kid_uuid] = cached_key["key"]

        if self.vaults and cached_keys_for_vault:
            try:
                self.vaults.add_keys(cached_keys_for_vault)
            except Exception:
                pass

        self._has_cached_keys = True
        return True
