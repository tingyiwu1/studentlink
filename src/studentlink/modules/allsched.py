from ._module import Module
from dataclasses import dataclass
from bs4 import BeautifulSoup
import re
import asyncio
from studentlink.util import normalize, Abbr, PageParseError
from studentlink.data.class_ import ScheduleClassView, Weekday, Event, Building
from studentlink.modules.bldg import Bldg
from datetime import datetime
from bs4.element import Tag


class AllSched(Module):
    MODULE_NAME = "allsched.pl"

    async def get_schedule(self, populate_buildings: bool = False):
        page = await self.get_page()
        soup = BeautifulSoup(page, "html5lib")
        # probably fails if there are no classes
        data_rows: list[Tag]
        try:
            _, *data_rows = (
                soup.find_all(string=re.compile(r"Spring|Summer|Fall|Winter"))[0]
                .find_parent("table")
                .find_all("tr")
            )
        except AttributeError:
            raise PageParseError(f"Failed to parse allched: {page}")
        result: dict[str, list[ScheduleClassView]] = {}
        semester = None
        for tr in data_rows:
            match tr.find_all("td"):
                case [
                    Tag(
                        name="td",
                        attrs={"rowspan": _},
                        contents=[Tag(name="font", contents=[semester, *_]), *_],
                    ),
                    *rest,
                ]:
                    if not isinstance(semester, str):  # skip divider rows
                        continue
                    semester = normalize(semester).split("\n")[0]
                    result[semester] = []
                case [*rest]:
                    pass
                case _:
                    raise PageParseError(f"Invalid row: \n{tr}\nin page:\n{page}")
            if semester is None:
                raise PageParseError(
                    f"tr does not start with td that specifies a semester: \n{tr}\n{page}"
                )
            match rest:
                case [
                    Tag(name="td", text=abbreviation),
                    Tag(name="td"),
                    Tag(name="td", text=status),
                    Tag(name="td", text=cr_hrs),
                    Tag(
                        name="td",
                        contents=[
                            Tag(name="font", contents=[title, _, instructor]),
                            *_,
                        ],
                    ),
                    Tag(name="td", text=topic),
                    Tag(name="td", text=type),
                    Tag(
                        name="td",
                        contents=[Tag(name="font", contents=[*events_buildings]), *_],
                    ),
                    Tag(
                        name="td",
                        contents=[Tag(name="font", contents=[*events_rooms]), *_],
                    ),
                    Tag(
                        name="td",
                        contents=[Tag(name="font", contents=[*events_days]), *_],
                    ),
                    Tag(
                        name="td",
                        contents=[Tag(name="font", contents=[*events_starts]), *_],
                    ),
                    Tag(
                        name="td",
                        contents=[Tag(name="font", contents=[*events_stops]), *_],
                    ),
                    Tag(name="td", text=notes),
                ]:
                    result[semester].append(
                        self.create_schedule_class_view(
                            semester,
                            abbreviation,
                            status,
                            cr_hrs,
                            title,
                            instructor,
                            topic,
                            type,
                            notes,
                            events_buildings,
                            events_rooms,
                            events_days,
                            events_starts,
                            events_stops,
                            populate_buildings,
                        )
                    )
                case [Tag(name="td", text="no\xa0reg\xa0activity"), *_]:
                    continue
                case _:
                    raise PageParseError(f"Invalid row: \n{tr}\nin page:\n{page}")
        result = {k: await asyncio.gather(*v) for k, v in result.items()}
        return result

    async def create_schedule_class_view(
        self,
        semester,
        abbreviation,
        status,
        cr_hrs,
        title,
        instructor,
        topic,
        type,
        notes,
        events_buildings,
        events_rooms,
        events_days,
        events_starts,
        events_stops,
        populate_buildings: bool = False,
    ):
        schedule = []
        for building, room, days, start, stop in zip(
            events_buildings,
            events_rooms,
            events_days,
            events_starts,
            events_stops,
        ):
            match building, room:
                case Tag(name="a", text=abbr), _:
                    building = (
                        Building(abbreviation=abbr)
                        if not populate_buildings
                        else await self.client.module(Bldg).get_building(abbr)
                    )
                    room = normalize(room).split("\n")[0]
                case "NO", "ROOM":
                    building = room = None
                case Tag(name="br"), Tag(name="br"):  # skip line breaks
                    continue
                case _:
                    raise PageParseError(
                        f"Invalid building or room: {building}, {room}"
                    )
            days = [Weekday[day] for day in days.split(",")]
            start = datetime.strptime(normalize(start), "%I:%M%p").time()
            stop = datetime.strptime(normalize(stop), "%I:%M%p").time()
            schedule += [
                Event(
                    building=building,
                    room=room,
                    day=day,
                    start=start,
                    stop=stop,
                )
                for day in days
            ]
        return ScheduleClassView(
            abbr=Abbr(normalize(abbreviation)),
            semester=semester,
            status=normalize(status),
            cr_hrs=normalize(cr_hrs),
            title=normalize(title),
            instructor=normalize(instructor),
            topic=normalize(topic),
            type=normalize(type),
            schedule=schedule,
            notes=normalize(notes),
        )
