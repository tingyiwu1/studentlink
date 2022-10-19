from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, time
from studentlink.util import normalize
from .vo import View
from enum import IntEnum
from bs4.element import Tag

Weekday = IntEnum("Weekday", "Sun Mon Tue Wed Thu Fri Sat", start=0)


@dataclass(frozen=True, kw_only=True)
class ClassView(View):
    abbreviation: str
    semester: str
    status: str
    cr_hrs: str
    title: str
    instructor: str
    topic: str
    type: str
    schedule: list[Event]
    notes: str

@dataclass(frozen=True, kw_only=True)
class Event(View):
    day: Weekday
    start: time
    stop: time
    building: Building = None
    room: str = None


@dataclass(frozen=True, kw_only=True)
class Building(View):
    abbreviation: str
    description: str = None
    address: str = None
