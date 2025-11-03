import requests
from urllib.parse import urlparse, unquote
import re


class Connector:
    """Handles HTTP connection and file metadata extraction"""

    def __init__(self, url: str, timeout: int = 10):
        self.url = url
        self.timeout = timeout
        self._headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def connect(self):
        """Connect to URL and extract file metadata"""
        try:
            r = requests.head(
                self.url,
                allow_redirects=True,
                headers=self._headers,
                timeout=self.timeout,
            )

            if r.status_code != 200:
                return None

            # Extract metadata
            content_size = r.headers.get("Content-Length")
            content_disposition = r.headers.get("Content-Disposition")

            # Get filename
            filename = (
                self._parse_filename(content_disposition)
                or self._extract_filename_from_url()
            )

            # Check range support
            accepts_ranges = r.headers.get("Accept-Ranges", "").lower() == "bytes"

            # Fallback for content-length
            if not content_size:
                try:
                    r_get = requests.get(
                        self.url,
                        stream=True,
                        headers=self._headers,
                        timeout=self.timeout,
                    )
                    content_size = r_get.headers.get("Content-Length")
                    r_get.close()
                except:
                    pass

            return {
                "type": r.headers.get("Content-Type"),
                "size": content_size,
                "filename": filename,
                "supports_resume": accepts_ranges,
                "range": "bytes" if accepts_ranges else None,
            }

        except requests.exceptions.Timeout:
            return None
        except requests.exceptions.RequestException:
            return None
        except Exception:
            return None

    def _parse_filename(self, content_disposition):
        """Parse filename from Content-Disposition header"""
        if not content_disposition:
            return None

        # RFC 5987 format: filename*=encoding'lang'value
        match = re.search(r"filename\*=([^']+)'([^']*)'(.+)", content_disposition)
        if match:
            return unquote(match.group(3))

        # Standard format: filename="value"
        match = re.search(r'filename="?([^"]+)"?', content_disposition)
        if match:
            return match.group(1)

        return None

    def _extract_filename_from_url(self):
        """Extract filename from URL path"""
        try:
            path = urlparse(self.url).path
            filename = unquote(path.split("/")[-1])

            # Remove query parameters
            filename = filename.split("?")[0]

            # Use default if empty or directory-like
            if not filename or filename.endswith("/"):
                filename = "download_file"

            return filename
        except:
            return "download_file"
