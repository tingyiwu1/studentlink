from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, time
from studentlink.util import normalize
from .vo import View
from enum import IntEnum
from bs4.element import Tag


class Weekday(IntEnum):
    Sun = 0
    Mon = 1
    Tue = 2
    Wed = 3
    Thu = 4
    Fri = 5
    Sat = 6
    Su = 0
    M = 1
    Tu = 2
    W = 3
    Th = 4
    F = 5
    Sa = 6


@dataclass(frozen=True, kw_only=True)
class ClassView(View):
    abbreviation: str
    semester: str = None
    can_register: bool = None
    reg_id: str = None
    open_seats: int = None
    status: str = None
    cr_hrs: str = None
    title: str = None
    instructor: str = None
    topic: str = None
    type: str = None
    schedule: list[Event] = None
    notes: str = None


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
