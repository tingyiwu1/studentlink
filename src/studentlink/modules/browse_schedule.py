from ._module import Module
from bs4 import BeautifulSoup
import re
from studentlink.util import normalize, Semester, Abbr, PageParseError
from studentlink.data.class_ import ClassView, Weekday, Event, Building
from datetime import datetime
from bs4.element import Tag


class BrowseSchedule(Module):
    MODULE_NAME = "reg/add/browse_schedule.pl"

    async def search_class(
        self,
        semester: Semester,
        college: str,
        department: str = None,
        course: int | str = None,
        section: str = None,
    ) -> list[ClassView]:
        params = {
            "SearchOptionCd": "S",
            "KeySem": semester,
            "College": college,
        }
        for k, v in zip(("Dept", "Course", "Section"), (department, course, section)):
            if v is not None:
                params[k] = v
        page = await self.get_page(params=params)
        if "No classes found for specified search criteria" in page:
            return []
        if "Semester must be in format YYYYS" in page:
            raise ValueError("Invalid semester")
        soup = BeautifulSoup(page, "html5lib")
        data_rows: list[Tag]
        try:
            _, *data_rows = soup.find(
                name="form", attrs={"name": "SelectForm"}
            ).tbody.find_all("tr", recursive=False)
        except AttributeError:
            raise PageParseError(f"Failed to parse class browse page: {page}")
        result = []
        for tr in data_rows:
            match tr.find_all("td", recursive=False):
                case [
                    Tag(
                        contents=[Tag(name="input") as selector, *_]
                        | [Tag(name="a") as selector]
                    ),
                    Tag(),
                    Tag(text=abbreviation),
                    Tag() as title_and_instructor,
                    Tag() as topic,
                    Tag(text=open_seats),
                    Tag(text=cr_hrs),
                    Tag(text=type),
                    Tag(contents=[Tag(name="a", contents=[*events_buildings])]),
                    Tag(contents=[*events_rooms]),
                    Tag(contents=[*events_days]),
                    Tag(contents=[*events_starts]),
                    Tag(contents=[*events_stops]),
                    Tag(text=notes),
                ]:
                    match selector:
                        case Tag(name="input", attrs={"value": reg_id}):
                            can_register = True
                        case Tag(name="a"):
                            reg_id = None
                            can_register = False
                    match topic:
                        case Tag(text=topic):
                            pass
                        case Tag():
                            topic = None
                    match title_and_instructor:
                        case Tag(contents=[title, Tag(name="br"), instructor]):
                            pass
                        case Tag(contents=[title]):
                            instructor = None
                    schedule = []
                    for building, room, days, start, stop in zip(
                        events_buildings,
                        events_rooms,
                        events_days,
                        events_starts,
                        events_stops,
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
                                stop=stop,
                            )
                            for day in days
                        ]
                    result.append(
                        ClassView(
                            abbr=Abbr(normalize(abbreviation)),
                            title=normalize(title),
                            can_register=can_register,
                            reg_id=reg_id,
                            instructor=normalize(instructor),
                            open_seats=int(normalize(open_seats)),
                            cr_hrs=normalize(cr_hrs),
                            type=normalize(type),
                            schedule=schedule,
                            notes=normalize(notes),
                        )
                    )
                case [Tag(contents=[]), *_]:
                    continue
                case _:
                    raise PageParseError(f"Failed to parse class browse page: {page}")
        return result
