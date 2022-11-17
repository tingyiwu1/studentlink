from ._module import Module
from bs4 import BeautifulSoup
import re
from studentlink.util import normalize, Abbr, PageParseError
from studentlink.data.class_ import ScheduleClassView, Weekday, Event, Building
from datetime import datetime
from bs4.element import Tag

class RegSched(Module):
    MODULE_NAME = "regsched.pl"
    
    async def get_schedule(self):
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
            raise PageParseError(f"Failed to parse regsched: {page}")
        result: dict[str, list[ScheduleClassView]] = {}
        semester = None
        for tr in data_rows:
            match tr.find_all("td"):
                case [
                    Tag(
                        name="td",
                        attrs={"rowspan": _},
                        contents=[semester, *_],
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
                raise PageParseError(f"tr does not start with td that specifies a semester: \n{tr}\n{page}")
            match rest:
                case [
                    Tag(name="td", text=abbreviation),
                    Tag(name="td", text=status),
                    Tag(name="td", text=cr_hrs),
                    Tag(name="td") as title_and_instructor,
                    Tag(name="td", text=topic),
                    Tag(name="td", text=type),
                    Tag(name="td", contents=[Tag(name="a", contents=[*event_buildings]), *_]),
                    Tag(name="td", contents=[*event_rooms]),
                    Tag(name="td", contents=[*events_days]),
                    Tag(name="td", contents=[*event_starts]),
                    Tag(name="td", contents=[*event_stops]),
                    Tag(name="td", text=notes)
                ]:
                    match title_and_instructor:
                        case Tag(contents=[title, Tag(name="br"), instructor]):
                            pass
                        case Tag(contents=[title]):
                            instructor = None
                    schedule = []
                    for building, room, days, start, stop in zip(
                        event_buildings, 
                        event_rooms,
                        events_days,
                        event_starts,
                        event_stops
                    ):
                        match building, room:
                            case "NO", "ROOM":
                                building = room = None
                            case Tag(name="br"), Tag(name="br"):
                                continue
                            case str(), str():
                                building = Building(abbreviation=normalize(building))
                                room = normalize(room)
                        days = [Weekday[day] for day in normalize(days).split(",")]
                        start = datetime.strptime(normalize(start), "%I:%M%p").time()
                        stop = datetime.strptime(normalize(stop), "%I:%M%p").time()
                        schedule += [
                            Event(
                                building=building,
                                room=room,
                                day=day,
                                start=start,
                                stop=stop
                            ) for day in days
                        ]
                    result[semester].append(
                        ScheduleClassView(
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
                case [
                    Tag(
                        name="td",
                        contents=[
                            Tag(name="b", text="Total\xa0Credits") | Tag(name="hr"),
                            *_
                        ]
                    ) | Tag(name="td", text="no\xa0reg\xa0activity"),
                    *_
                ]:
                    continue
                case _:
                    raise PageParseError(f"Invalid row: \n{tr}\nin page:\n{page}")
        return result