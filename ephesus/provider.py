"""Minimal Claude Messages adapter. No package installs are needed."""

from collections.abc import Callable
import json
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .contracts import REPORT_SCHEMA

MESSAGES_URL = "https://api.anthropic.com/v1/messages"


class ProviderError(RuntimeError):
    pass


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ClaudeProvider:
    mode = "live_claude"

    def __init__(self, key: str, model: str, opener: Callable | None = None):
        if not key or not model:
            raise ValueError("An Anthropic API key and explicit model ID are required")
        self.key = key
        self.model = model
        self.opener = opener or build_opener(NoRedirects()).open

    def send(self, *, system, messages, tools, timeout):
        payload = {
            "model": self.model,
            "max_tokens": 2000,
            "system": system,
            "messages": messages,
            "output_config": {"format": {"type": "json_schema", "schema": REPORT_SCHEMA}},
        }
        if tools:
            payload["tools"] = tools
        request = Request(MESSAGES_URL, data=json.dumps(payload).encode("utf-8"), headers={
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": self.key,
        }, method="POST")
        try:
            with self.opener(request, timeout=timeout) as response:
                data = json.load(response)
        except HTTPError as exc:
            raise ProviderError(f"Claude returned HTTP {exc.code}") from None
        except (URLError, TimeoutError, OSError):
            raise ProviderError("Claude request failed or timed out") from None
        except (ValueError, UnicodeError):
            raise ProviderError("Claude returned an unreadable response") from None
        if not isinstance(data, dict) or data.get("type") != "message":
            raise ProviderError("Claude response did not contain a message")
        return data
