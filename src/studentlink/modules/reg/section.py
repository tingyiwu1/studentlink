from studentlink.modules.reg._reg_module import RegModule
from dataclasses import dataclass
from bs4 import BeautifulSoup
from bs4.element import Tag
from studentlink.util import normalize, Semester, Abbr, PageParseError
from studentlink.data.class_ import RegisteredClassView, Weekday, Event, Building
from datetime import datetime

class Section(RegModule):
    MODULE_NAME = "reg/section/_start.pl"
    
    async def get_section_change(self, semester: Semester):
        page = await self.get_page(semester)
        soup = BeautifulSoup(page, "html5lib")
        data_rows: list[Tag]
        try:
            _, *data_rows = (
                soup.find("th", text="Semester:").find_next("table").tbody.find_all("tr", recursive=False)
            )
        except AttributeError:
            raise PageParseError(f"Failed to parse section change: {page}")
        result: list[SectionClassView] = []
        for tr in data_rows:
            match tr.find_all("td", recursive=False):
                case [
                    Tag(contents=[Tag(name="a") | str()]) as abbreviation,
                    Tag(text=status),
                    Tag(text=cr_hrs),
                    Tag() as title_and_instructor,
                    Tag(text=type),
                    Tag(contents=[*events_buildings]),
                    Tag(contents=[*events_rooms]),
                    Tag(contents=[*events_days]),
                    Tag(contents=[*events_starts]),
                    Tag(contents=[*events_stops]),
                ]:
                    match title_and_instructor:
                        case Tag(
                            contents=[
                                title, Tag(name="br"), instructor
                            ]
                        ):
                            pass
                        case Tag(contents=[title]):
                            instructor = None
                    match abbreviation:
                        case Tag(contents=[Tag(name="a", text=abbreviation)]):
                            can_switch = True
                        case Tag(text = abbreviation):
                            can_switch = False
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
                        SectionClassView(
                            abbr=Abbr(normalize(abbreviation)),
                            status=normalize(status),
                            title=normalize(title),
                            cr_hrs=normalize(cr_hrs),
                            instructor=normalize(instructor),
                            type=normalize(type),
                            schedule=schedule,
                            can_switch=can_switch,
                        )
                    )
                case [Tag(), *_]:
                    continue
                case _:
                    raise PageParseError(f"Failed to parse section change: {page}")
        return result

@dataclass(frozen=True, kw_only=True)
class SectionClassView(RegisteredClassView):
    can_switch: bool = None