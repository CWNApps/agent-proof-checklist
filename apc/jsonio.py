"""Strict JSON loading: no duplicate keys, no NaN or Infinity, UTF-8 without a BOM."""
import json


class StrictJSONError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}:{detail}" if detail else code)
        self.code = code


def _pairs(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise StrictJSONError("DUPLICATE_KEY", k)
        out[k] = v
    return out


def _constant(name):
    raise StrictJSONError("JSON_INVALID", name)


def load_strict(data: bytes) -> object:
    if isinstance(data, str):
        data = data.encode("utf-8")
    if data.startswith(b"\xef\xbb\xbf"):
        raise StrictJSONError("JSON_INVALID", "bom")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise StrictJSONError("JSON_INVALID", "utf8") from None
    try:
        return json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
    except StrictJSONError:
        raise
    except (ValueError, RecursionError):
        raise StrictJSONError("JSON_INVALID") from None
