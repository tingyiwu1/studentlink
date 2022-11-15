from ._module import Module
from bs4 import BeautifulSoup
import re
from studentlink.util import normalize, Abbr
from studentlink.data.class_ import ClassView, Weekday, Event, Building
from datetime import datetime
from bs4.element import Tag


class AllSched(Module):
    MODULE_NAME = "allsched.pl"

    async def get_schedule(self):
        page = await self.get_page()
        soup = BeautifulSoup(page, "html5lib")
        # probably fails if there are no classes
        data_rows: list[Tag]
        _, *data_rows = (
            soup.find_all(string=re.compile(r"Spring|Summer|Fall|Winter"))[0]
            .find_parent("table")
            .find_all("tr")
        )
        result: dict[str, list[ClassView]] = {}
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
                    raise ValueError("Invalid tr")
            if semester is None:
                raise ValueError("tr does not start with td that specifies a semester")
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
                                building = Building(abbreviation=abbr)
                                room = normalize(room).split("\n")[0]
                            case "NO", "ROOM":
                                building = room = None
                            case Tag(name="br"), Tag(name="br"): # skip line breaks
                                continue
                            case _:
                                raise ValueError("Invalid building or room")
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
                            ) for day in days
                        ]
                    result[semester].append(
                        ClassView(
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
                    )
                case [Tag(name="td", text="no\xa0reg\xa0activity"), *_]:
                    continue
                case _:
                    raise ValueError("Invalid tr")
        return result
