import requests
from urllib.parse import urlparse, unquote
import re


class Connector:
    def __init__(self, url: str):
        self.url = url
        self.content_type = None
        self.content_size = None
        self.accepts_ranges = None
        self.decomposition = None
        self.Accept_ranges = False
        self.filename = None

    def _status_check(self, request):
        """Check if HTTP request was successful"""
        try:
            if request:
                return request.status_code == 200
            else:
                return False
        except Exception as e:
            print(f"Status check error: {e}")
            return None

    def _accept_range_checker(self, accept_range):
        """
        Checks if the server accepts range downloading
        """
        try:
            if accept_range and accept_range.lower() == "bytes":
                self.Accept_ranges = True
                return self.Accept_ranges
            else:
                return self.Accept_ranges
        except (ValueError, Exception) as e:
            print(f"Error: Error during range check... : {e}")
            return False

    def _parse_content_disposition(self, content_disposition):
        """
        Parse filename from Content-Disposition header
        """
        try:
            if not content_disposition:
                return None

            # Try to find filename* (RFC 5987) first
            filename_match = re.search(
                r"filename\*=([^']+)'([^']*)'(.+)", content_disposition
            )
            if filename_match:
                encoding = filename_match.group(1)
                filename = filename_match.group(3)
                return unquote(filename)

            # Try regular filename
            filename_match = re.search(r'filename="?([^"]+)"?', content_disposition)
            if filename_match:
                return filename_match.group(1)

            return None
        except Exception as e:
            print(f"Error parsing Content-Disposition: {e}")
            return None

    def _url_parser(self):
        """
        This is a fallback if the server doesn't provide Content-Disposition
        """
        try:
            content = urlparse(self.url)
            path = content.path
            filename = path.split("/")[-1]
            self.filename = unquote(filename)

            # If filename is empty or looks like a directory, use default
            if not self.filename or self.filename.endswith("/"):
                self.filename = "download_file"

            # Remove query parameters if they got included
            if "?" in self.filename:
                self.filename = self.filename.split("?")[0]

            return self.filename
        except Exception as e:
            print(f"Could not parse url: {e}")
            return "download_file"

    def connect(self):
        """
        Connects to the url and captures its contents
        """
        try:
            # Set a user agent to avoid blocks
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            r = requests.head(
                self.url, allow_redirects=True, headers=headers, timeout=10
            )

            # Only continues when the status returns a True
            if self._status_check(r):
                self.content_type = r.headers.get("Content-Type")
                self.content_size = r.headers.get("Content-Length")
                self.decomposition = r.headers.get("Content-Disposition")

                # Try to get filename from Content-Disposition first
                if self.decomposition:
                    parsed_filename = self._parse_content_disposition(
                        self.decomposition
                    )
                    if parsed_filename:
                        self.filename = parsed_filename

                # Fallback to URL parsing if no filename found
                if not self.filename:
                    self._url_parser()

                # Check if server accepts range requests
                self.accepts_ranges = r.headers.get("Accept-Ranges")
                self._accept_range_checker(self.accepts_ranges)

                # If no content-length, try a GET request
                if not self.content_size:
                    try:
                        r_get = requests.get(
                            self.url, stream=True, headers=headers, timeout=10
                        )
                        self.content_size = r_get.headers.get("Content-Length")
                        r_get.close()
                    except:
                        pass

                return {
                    "type": self.content_type,
                    "size": self.content_size,
                    "decomposition": self.decomposition,
                    "range": self.accepts_ranges,
                    "filename": self.filename,
                    "supports_resume": self.Accept_ranges,
                }
            else:
                print(f"Failed status Check. Status code: {r.status_code}")
                print("Double Check the url")
                return None

        except requests.exceptions.Timeout:
            print("Error: Connection timeout")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error in connection: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error in connection: {e}")
            return None

    def test_connection(self):
        """
        Test if URL is accessible and return basic info
        """
        try:
            r = requests.head(self.url, allow_redirects=True, timeout=5)
            return {
                "accessible": r.status_code == 200,
                "status_code": r.status_code,
                "redirected": len(r.history) > 0,
                "final_url": r.url,
            }
        except Exception as e:
            return {"accessible": False, "error": str(e)}
