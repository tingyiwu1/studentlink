from studentlink.modules.reg._reg_module import RegModule
from bs4 import BeautifulSoup
from bs4.element import Tag
from studentlink.util import normalize, Semester
from studentlink.data.class_ import ClassView, Weekday, Event, Building
from datetime import datetime


class Drop(RegModule):
    MODULE_NAME = "reg/drop/_start.pl"

    async def get_drop_list(self, semester: Semester) -> list[ClassView]:
        page = await self.get_page(semester)
        soup = BeautifulSoup(page, "html5lib")
        data_rows: list[Tag]
        _, *data_rows = (
            soup.find(name="form", attrs={"name": "SelectForm"})
            .find_next("tbody")
            .find_all("tr", recursive=False)
        )
        result = []
        for tr in data_rows:
            match tr.find_all("td", recursive=False):
                case [
                    Tag(contents=[Tag(name="input", attrs={"name": "DropIt", "value": drop_id}), *_]),
                    Tag(text=abbreviation),
                    Tag(text=status),
                    Tag(text=cr_hrs),
                    Tag(contents=[title, Tag(name="br"), Tag(text=instructor) | str(instructor)]),
                    Tag(text=type),
                    Tag(contents=[*events_buildings]),
                    Tag(contents=[*events_rooms]),
                    Tag(contents=[*events_days]),
                    Tag(contents=[*events_starts]),
                    Tag(contents=[*events_stops]),
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
                            abbreviation=normalize(abbreviation),
                            status=normalize(status),
                            cr_hrs=normalize(cr_hrs),
                            title=normalize(title),
                            instructor=normalize(instructor),
                            type=normalize(type),
                            schedule=schedule,
                            drop_id=drop_id,
                        )
                    )
                    
                case [Tag(), *_]:
                    continue
                case _:
                    raise ValueError("Invalid tr")
        return result