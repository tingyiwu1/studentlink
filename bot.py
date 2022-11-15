import asyncio
from dotenv import load_dotenv
import logging
import os
import contextlib
from io import StringIO

from aiohttp import ClientSession

from studentlink import StudentLinkAuth
from studentlink.util import Semester, Abbr
from studentlink.data.class_ import ClassView
from studentlink.modules.browse_schedule import BrowseSchedule
from studentlink.modules.reg import ConfirmClasses, Drop, ConfirmDrop

load_dotenv()
logging.basicConfig(level=logging.INFO)

USERNAME, PASSWORD, DISC_URL = (
    os.environ["USERNAME"],
    os.environ["PASSWORD"],
    os.environ["DISC_URL"],
)

SEMESTER = Semester.from_str("Spring 2023")


class CannotReplace(Exception):
    pass


async def get_class_reg(sl: StudentLinkAuth, abbr: Abbr):
    res = await sl.module(BrowseSchedule).search_class(SEMESTER, *abbr)
    for cv in res:
        if abbr == cv.abbreviation:
            return cv


async def get_class_drop(sl: StudentLinkAuth, abbr: Abbr):
    res = await sl.module(Drop).get_drop_list(SEMESTER)
    for cv in res:
        if abbr == cv.abbreviation:
            return cv


async def attempt_register(sl: StudentLinkAuth, abbr: Abbr, logger: logging.Logger = logging.getLogger()):
    cv = await get_class_reg(sl, abbr)
    if cv is not None and cv.can_register:
        logger.info(f"Can register for {cv.abbreviation}")
        res = await sl.module(ConfirmClasses).confirm_class(SEMESTER, cv.reg_id)
        if res[cv.abbreviation][0]:
            logger.info(f"Successfully registered for {cv.abbreviation}")
    else:
        logger.info(f"Cannot register for {abbr}")


async def attempt_replace(sl: StudentLinkAuth, *, add: Abbr, replace: Abbr, logger: logging.Logger = logging.getLogger()):
    cv1 = await get_class_reg(sl, add)
    if cv1 is not None and cv1.can_register:
        async with disc_log(sl.session, add) as logger:
            logger.info(f"Can register for {cv1.abbreviation}")
            try:
                async with replace_class(sl, replace, logger) as cv2:
                    logger.info(
                        f"Replacing {cv2.abbreviation} with {cv1.abbreviation}"
                    )
                    res = await sl.module(ConfirmClasses).confirm_class(
                        SEMESTER, cv1.reg_id
                    )
                    if res[cv1.abbreviation][0]:
                        logger.info(f"Successfully registered for {cv1.abbreviation}")
                    else:
                        logger.info(f"Failed to register for {cv1.abbreviation}")
            except CannotReplace as e:
                logger.warning(e)
    else:
        logger.info(f"Cannot register for {add}")


@contextlib.asynccontextmanager
async def disc_log(session: ClientSession, name: str):
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    logger = logging.getLogger(name)
    logger.addHandler(handler)
    try:
        yield logger
    finally:
        await session.post(DISC_URL, data={"content": stream.getvalue(), "username": name})


@contextlib.asynccontextmanager
async def replace_class(sl: StudentLinkAuth, abbr: Abbr, logger: logging.Logger = logging.getLogger()):
    """context manager to drop a class to make room for another. MAKE SURE THEY OVERLAP"""
    cv_r, cv_d = await asyncio.gather(get_class_reg(sl, abbr), get_class_drop(sl, abbr))
    if cv_d is None or not cv_d.drop_id:
        raise CannotReplace(f"Cannot drop {abbr}")
    if cv_r is None or not cv_r.can_register:
        raise CannotReplace(f"Cannot register for {abbr}")
    try:
        res = await sl.module(ConfirmDrop).confirm_drop(SEMESTER, cv_d.drop_id)
        if res[cv_d.abbreviation][0]:
            logger.info(f"Successfully dropped {cv_d.abbreviation}")
            yield cv_d
        else:
            raise CannotReplace(
                f"Failed to drop {cv_d.abbreviation}: {res[cv_d.abbreviation][1]}"
            )
    finally:  # attempt to re-register original class so i don't get screwed over if something fails
        res = await sl.module(ConfirmClasses).confirm_class(SEMESTER, cv_r.reg_id)
        if res[cv_r.abbreviation][0]:
            logger.info(f"Successfully re-registered for {cv_r.abbreviation}")
        else:
            logger.info(
                f"Failed to re-register for {cv_r.abbreviation}: {res[cv_r.abbreviation][1]}"
            )


async def test_replace(sl: StudentLinkAuth, abbr: Abbr):
    try:
        async with replace_class(sl, abbr) as cv:
            logging.info(f"sleeping")
            await asyncio.sleep(5)
            logging.info(f"done sleeping")
    except CannotReplace as e:
        logging.warning(e)


async def poll():
    async with StudentLinkAuth(USERNAME, PASSWORD) as sl:
        await asyncio.gather(
            attempt_replace(sl, add=Abbr("CAS PS261 A5"), replace=Abbr("CAS PS261 A5")),
            attempt_replace(sl, add=Abbr("CAS PS261 A1"), replace=Abbr("CAS PS261 A1")),
        )
        # await test_replace(sl, Abbr("CAS MA241 A2"))
        # await attempt_replace(sl, Abbr("CAS PS261 A4"), Abbr("CAS PS261 A5"))
        # await attempt_replace(
        #     sl, add=Abbr("CAS PS261 A5"), replace=Abbr("CAS PS261 A5")
        # )


if __name__ == "__main__":
    asyncio.run(poll())
