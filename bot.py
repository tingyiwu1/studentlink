import asyncio
from dotenv import load_dotenv
import logging
import os
import re

from studentlink import StudentLinkAuth
from studentlink.util import Semester
from studentlink.modules.browse_schedule import BrowseSchedule
from studentlink.modules.reg import ConfirmClasses

load_dotenv()
logging.basicConfig(level=logging.INFO)

USERNAME, PASSWORD = os.environ["USERNAME"], os.environ["PASSWORD"]

SEMESTER = Semester.from_str("Spring 2023")


async def get_class(sl: StudentLinkAuth, abbr: str):
    abbr = abbr.upper()
    col, dep, cor, sec = re.match(
        r"^([A-Z]{3}) ?([A-Z]{2}) ?(\d{3}) ?([A-Z]\d)$", abbr
    ).groups()
    res = await sl.module(BrowseSchedule).search_class(SEMESTER, col, dep, cor, sec)
    for cv in res:
        if f"{col} {dep}{cor} {sec}" == cv.abbreviation:
            return cv

async def attempt_register(sl: StudentLinkAuth, abbr: str):
    cv = await get_class(sl, "CAS CS 131 A1")
    if cv.can_register:
        res = sl.module(ConfirmClasses).confirm_class(SEMESTER, cv.reg_id)
        if res[cv.reg_id][0]:
            logging.info("Successfully registered for %s", cv.abbreviation)
    else:
        logging.info("Cannot register for %s", cv.abbreviation)



async def poll():
    async with StudentLinkAuth(USERNAME, PASSWORD) as sl:
        while True:
            attempt_register(sl, "CAS CS 131 A1")
            await asyncio.sleep(5)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    task = loop.create_task(poll())

    try:
        loop.run_until_complete(task)
    except KeyboardInterrupt as e:
        print("Exiting...")
        task.cancel()
        loop.run_forever()
        task.exception()
    finally:
        loop.close()
