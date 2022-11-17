from studentlink.modules.reg._reg_module import RegModule
from dataclasses import dataclass
from bs4 import BeautifulSoup
from bs4.element import Tag
from studentlink.util import normalize, Semester, Abbr, PageParseError
from studentlink.data.class_ import ClassView, Weekday, Event, Building
from datetime import datetime


class Plan(RegModule):
    MODULE_NAME = "reg/plan/_start.pl"

    async def get_planner(self, semester: Semester):
        page = await self.get_page(semester)
        soup = BeautifulSoup(page, "html5lib")
        data_rows: list[Tag]
        try:
            _, *data_rows = (
                soup.find("b", text="Semester:")
                .find_next("table")
                .tbody.find_all("tr", recursive=False)
            )
        except AttributeError:
            raise PageParseError(f"Failed to parse planner: {page}")
        result: list[PlannerClassView] = []
        for tr in data_rows:
            match tr.find_all("td", recursive=False):
                case [
                    Tag(contents=[Tag(name="a", text="Remove")]),
                    Tag(text=abbreviation),
                    Tag(text=open_seats),
                    Tag(text=cr_hrs),
                    Tag() as title_and_instructor,
                    Tag() as topic,
                    Tag(text=type),
                    Tag(contents=[Tag(name="a", contents=[*events_buildings])]),
                    Tag(contents=[*events_rooms]),
                    Tag(contents=[*events_days]),
                    Tag(contents=[*events_starts]),
                    Tag(contents=[*events_stops]),
                    Tag() as notes,
                ]:
                    match topic:
                        case Tag(text=topic):
                            pass
                        case Tag():
                            topic = None
                    match title_and_instructor:
                        case Tag(
                            contents=[
                                title,
                                Tag(name="br"),
                                Tag(text=instructor) | str(instructor),
                            ]
                        ):
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
                        PlannerClassView(
                            abbr=Abbr(normalize(abbreviation)),
                            title=normalize(title),
                            open_seats=int(normalize(open_seats)),
                            cr_hrs=normalize(cr_hrs),
                            instructor=normalize(instructor),
                            type=normalize(type),
                            schedule=schedule,
                            topic=normalize(topic),
                            notes=normalize(notes.get_text(separator="\n")),
                        )
                    )
                case [Tag(), *_]:
                    continue
                case _:
                    raise PageParseError(f"Failed to parse planner: {page}")
        return result

@dataclass(frozen=True, kw_only=True)
class PlannerClassView(ClassView):
    open_seats: int = None