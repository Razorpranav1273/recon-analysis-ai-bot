"""
HTTP Client Utility for Recon Analysis Bot
Provides a centralized HTTP client with proper error handling and session management.
"""

import requests
import urllib3
from urllib3.util.retry import Retry
from typing import Dict, Any, Optional
from datetime import datetime
import json
import threading
from src.utils.logging import logger
from urllib.parse import urlparse
import time

# Disable SSL warnings for API calls
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class SharedSessionManager:
    """
    Manages shared requests sessions for connection reuse.
    Thread-safe singleton for optimal connection pooling.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._sessions = {}
                    cls._instance._session_lock = threading.Lock()
        return cls._instance

    def get_session(
        self,
        verify_ssl: bool = False,
        timeout: int = 60,
        max_retries: int = 3,
        retry_backoff_factor: float = 0.3,
        retry_status_forcelist: tuple = (429, 500, 501, 502, 504),
    ) -> requests.Session:
        """
        Get or create a shared session with specified configuration including retry logic.

        Args:
            verify_ssl: Whether to verify SSL certificates
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
            retry_backoff_factor: Backoff factor for retry delays
            retry_status_forcelist: HTTP status codes that should trigger retries

        Returns:
            Configured requests.Session instance with retry logic
        """
        session_key = f"ssl_{verify_ssl}_timeout_{timeout}_retries_{max_retries}_backoff_{retry_backoff_factor}"

        with self._session_lock:
            if session_key not in self._sessions:
                session = requests.Session()

                # Configure retry strategy
                retry_strategy = Retry(
                    total=max_retries,
                    status_forcelist=retry_status_forcelist,
                    backoff_factor=retry_backoff_factor,
                    respect_retry_after_header=True,
                    raise_on_status=False,
                )

                # Configure session with connection pooling and retry logic
                adapter = requests.adapters.HTTPAdapter(
                    pool_connections=10,
                    pool_maxsize=20,
                    max_retries=retry_strategy,
                    pool_block=False,
                )

                session.mount("https://", adapter)
                session.mount("http://", adapter)

                # Set default headers
                session.headers.update(
                    {
                        "User-Agent": "ReconAnalysisBot/1.0",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    }
                )

                self._sessions[session_key] = session
                logger.debug(f"Created new shared session: {session_key}")

            return self._sessions[session_key]

    def close_all_sessions(self):
        """Close all managed sessions."""
        with self._session_lock:
            for session in self._sessions.values():
                session.close()
            self._sessions.clear()
            logger.debug("Closed all shared sessions")


# Global session manager instance
_session_manager = SharedSessionManager()


class HTTPClient:
    """
    Centralized HTTP client for making API requests with proper error handling.
    Uses shared session manager for optimal connection reuse.
    """

    def __init__(
        self,
        verify_ssl: bool = False,
        timeout: int = 30,
        use_shared_session: bool = True,
        max_retries: int = 3,
        retry_backoff_factor: float = 0.3,
        retry_status_forcelist: tuple = (429, 500, 501, 502, 504),
    ):
        """
        Initialize HTTP client.

        Args:
            verify_ssl: Whether to verify SSL certificates
            timeout: Request timeout in seconds
            use_shared_session: Whether to use shared session for connection reuse
            max_retries: Maximum number of retries for failed requests
            retry_backoff_factor: Backoff factor for exponential backoff
            retry_status_forcelist: HTTP status codes that should trigger retries
        """
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.use_shared_session = use_shared_session
        self.max_retries = max_retries
        self.retry_backoff_factor = retry_backoff_factor
        self.retry_status_forcelist = retry_status_forcelist

        if use_shared_session:
            self.session = _session_manager.get_session(
                verify_ssl=verify_ssl,
                timeout=timeout,
                max_retries=max_retries,
                retry_backoff_factor=retry_backoff_factor,
                retry_status_forcelist=retry_status_forcelist,
            )
            self._owns_session = False
        else:
            self.session = requests.Session()
            self._owns_session = True

            retry_strategy = Retry(
                total=max_retries,
                status_forcelist=retry_status_forcelist,
                backoff_factor=retry_backoff_factor,
                respect_retry_after_header=True,
                raise_on_status=False,
            )

            adapter = requests.adapters.HTTPAdapter(max_retries=retry_strategy)
            self.session.mount("https://", adapter)
            self.session.mount("http://", adapter)

            self.session.headers.update(
                {
                    "User-Agent": "ReconAnalysisBot/1.0",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                }
            )

    def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a GET request."""
        return self._make_request("GET", url, headers=headers, params=params)

    def post(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Make a POST request."""
        return self._make_request("POST", url, data=data, headers=headers)

    def _make_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Internal method to make HTTP requests."""
        parsed = urlparse(url)
        host = parsed.netloc or parsed.scheme
        start = time.perf_counter()

        try:
            request_headers = self.session.headers.copy()
            if headers:
                request_headers.update(headers)

            request_kwargs = {
                "url": url,
                "headers": request_headers,
                "timeout": self.timeout,
                "verify": self.verify_ssl,
            }

            if params:
                request_kwargs["params"] = params

            if data:
                request_kwargs["json"] = data

            logger.info(
                f"Making {method} request to {url}",
                method=method,
                url=url,
                timeout=self.timeout,
            )

            response = self.session.request(method, **request_kwargs)
            duration = time.perf_counter() - start

            result = self._parse_response(response, url)
            return result

        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Request timeout",
                "error_type": "timeout",
                "url": url,
                "timestamp": datetime.now().isoformat(),
            }

        except requests.exceptions.SSLError as e:
            return {
                "success": False,
                "error": f"SSL Error: {str(e)}",
                "error_type": "ssl_error",
                "url": url,
                "timestamp": datetime.now().isoformat(),
            }

        except requests.exceptions.ConnectionError as e:
            return {
                "success": False,
                "error": f"Connection Error: {str(e)}",
                "error_type": "connection_error",
                "url": url,
                "timestamp": datetime.now().isoformat(),
            }

        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Request Error: {str(e)}",
                "error_type": "request_error",
                "url": url,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.exception(f"Unexpected Error: {str(e)}")
            return {
                "success": False,
                "error": f"Unexpected Error: {str(e)}",
                "error_type": "unexpected_error",
                "url": url,
                "timestamp": datetime.now().isoformat(),
            }

    def _parse_response(self, response: requests.Response, url: str) -> Dict[str, Any]:
        """Parse HTTP response and return standardized result."""
        try:
            if response.headers.get("content-type", "").startswith("application/json"):
                response_data = response.json()
            else:
                response_data = response.text

            if response.status_code == 200:
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "data": response_data,
                    "url": url,
                    "timestamp": datetime.now().isoformat(),
                }
            elif response.status_code == 404:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": "Resource not found",
                    "error_type": "not_found",
                    "data": response_data,
                    "url": url,
                    "timestamp": datetime.now().isoformat(),
                }
            else:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": f"HTTP {response.status_code}: {response.reason}",
                    "error_type": "http_error",
                    "data": response_data,
                    "url": url,
                    "timestamp": datetime.now().isoformat(),
                }

        except json.JSONDecodeError:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": "Invalid JSON response",
                "error_type": "json_decode_error",
                "data": response.text,
                "url": url,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": f"Response parsing error: {str(e)}",
                "error_type": "parse_error",
                "data": None,
                "url": url,
                "timestamp": datetime.now().isoformat(),
            }

    def close(self):
        """Close the HTTP session."""
        if self._owns_session and self.session:
            self.session.close()
            logger.debug("Closed dedicated HTTP session")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

