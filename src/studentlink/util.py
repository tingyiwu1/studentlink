import unicodedata
from functools import partial
from enum import IntEnum
from dataclasses import dataclass
import re
import time
import asyncio
from pprint import pprint

class PageParseError(Exception):
    pass

class Sem(IntEnum):
    SUMMER1 = 1
    SUMMER2 = 2
    FALL = 3
    SPRING = 4


class Semester(int):
    # summer 1 2022 -> 20231
    # summer 2 2022 -> 20232
    # fall 2022 -> 20233
    # spring 2023 -> 20234
    def __new__(cls, sem: Sem, year: int):
        return super().__new__(cls, (year + int(sem < 4)) * 10 + sem)

    @classmethod
    def from_str(cls, str: str):
        semester, year = str.split(" ")
        semester = Sem[semester.upper()]
        year = int(year)
        return cls(semester, year)

    @classmethod
    def from_key(cls, key: int):
        return super().__new__(cls, key)

    @property
    def year(self) -> int:
        return self // 10 - int(self % 10 < 4)

    @property
    def semester(self) -> Sem:
        return Sem(self % 10)


class Abbr(str):
    def __new__(cls, text: str):
        if not (
            match := re.match(
                r"^([A-Z]{3}) ?([A-Z]{2}) ?(\d{3}) ?([A-Z]\d)$", text.upper()
            )
        ):
            raise ValueError(f"Invalid abbreviation: {text}")
        return super().__new__(cls, "{} {}{} {}".format(*match.groups()))

    def __iter__(self):
        yield from re.match(
            r"^([A-Z]{3}) ?([A-Z]{2}) ?(\d{3}) ?([A-Z]\d)$", self
        ).groups()


def normalize(text: str) -> str:
    if not isinstance(text, str):
        return None
    return unicodedata.normalize("NFKD", text).strip()

def async_ttl_cache(ttl_seconds: int, cache: dict = None):
    def decorator(func):
        _cache = {} if cache is None else cache
        async def wrapper(*args, **kwargs):
            key = (args, tuple(kwargs.items()))
            if key in _cache and time.time() - _cache[key][1] < ttl_seconds:
                result = _cache[key][0]
            else:
                result = asyncio.create_task(func(*args, **kwargs))
                _cache[key] = (result, time.time())
            return await result
        return wrapper
    return decorator