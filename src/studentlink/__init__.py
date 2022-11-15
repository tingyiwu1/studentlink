from __future__ import annotations
from typing import Callable, TypeVar
import aiohttp
import logging
import html
import re
from yarl import URL

from .modules._module import Module, PublicModule

M = TypeVar("M", bound=Module)
PM = TypeVar("PM", bound=PublicModule)

class LoginError(Exception):
    pass

class StudentLink:
    def __init__(
        self, session: aiohttp.ClientSession = None, logger: logging.Logger = None
    ):
        self.session = session or aiohttp.ClientSession()
        self.logger = logger or logging.getLogger(__name__)
        self.modules: dict[type, Module] = {}

    async def __aenter__(self):
        await self.session.__aenter__()
        return self

    async def __aexit__(self, *args):
        await self.session.__aexit__(*args)
        self.session = None

    def module(self, module: Callable[[], PM]) -> PM:
        if not issubclass(module, PublicModule):
            raise TypeError(
                f"{module} requires authentication; use StudentLinkAuth instead"
            )
        if module not in self.modules:
            self.modules[module] = module(self)
        return self.modules[module]

    async def get_page(self, url, *, params: dict[str, str] = None) -> str:
        r = await self.session.get(url, params=params)
        t = await r.text()
        if "<title>Boston University | Login</title>" in t:
            raise TypeError(
                f"This page requires authentication; use StudentLinkAuth instead"
            )
        return t


class StudentLinkAuth(StudentLink):
    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession = None,
        logger: logging.Logger = None,
    ):
        super().__init__(session, logger)
        self.username = username
        self.password = password

    async def __aenter__(self):
        await super().__aenter__()
        for _ in range(3):
            try:
                await self.login()
                break
            except LoginError:
                continue
        else:
            raise RuntimeError("failed to log in")
        return self

    async def get_page(self, url, *, params: dict[str, str] = None) -> str:
        for _ in range(3):
            r = await self.session.get(url, params=params)
            t = await r.text()
            if "<title>Boston University | Login</title>" in t:
                try:
                    await self.login()
                except LoginError:
                    continue
            else:
                return t
        raise RuntimeError("failed to log in")

    async def login(self):
        r1 = await self.session.get(Module.mod_url("allsched.pl"))
        execution = r1.url.query["execution"]
        self.logger.info("logging in")
        r2 = await self.session.post(
            URL("https://shib.bu.edu/idp/profile/SAML2/Redirect/SSO").with_query(
                execution=execution
            ),
            data={
                "j_username": self.username,
                "j_password": self.password,
                "_eventId_proceed": "",
            },
        )
        tx, app = re.findall(r"'sig_request': '(TX.+?):(APP.+?)'", await r2.text())[0]
        r3 = await self.session.post(
            URL("https://api-c6b0c057.duosecurity.com/frame/web/v1/auth").with_query(
                tx=tx,
                parent=str(
                    URL(
                        "https://shib.bu.edu/idp/profile/SAML2/Redirect/SSO"
                    ).with_query(execution=execution)
                ),
            )
        )
        sid = r3.url.query["sid"]
        logging.info("sending duo push")
        r4 = await self.session.post(
            "https://api-c6b0c057.duosecurity.com/frame/prompt",
            data={
                "sid": sid,
                "device": "phone1",  # TODO: make this more robust
                "factor": "Duo Push",
                "dampen_choice": "true",
                "out_of_date": "",
                "days_out_of_date": "",
                "days_to_block": "None",
            },
        )
        txid = (await r4.json())["response"]["txid"]
        await self.session.post(
            "https://api-c6b0c057.duosecurity.com/frame/status",
            data={"sid": sid, "txid": txid},
        )
        r6 = await self.session.post(
            "https://api-c6b0c057.duosecurity.com/frame/status",
            data={"sid": sid, "txid": txid},
        )
        response = (await r6.json())["response"]
        result_url = response.get("result_url")
        if not result_url:
            raise LoginError(response)
        r7 = await self.session.post(
            f"https://api-c6b0c057.duosecurity.com{result_url}", data={"sid": sid}
        )
        parent = (await r7.json())["response"]["parent"][:-1] + "2"
        duo_sig = (await r7.json())["response"]["cookie"]
        r8 = await self.session.post(
            parent,
            data={"_eventId": "proceed", "signedDuoResponse": f"{duo_sig}:{app}"},
        )
        (_, relay_state), (_, SAMLResponse) = re.findall(
            r'input type="hidden" name="(.+?)" value="(.+?)"', await r8.text()
        )
        await self.session.post(
            "https://linklogin.bu.edu/Shibboleth.sso/SAML2/POST",
            data={
                "RelayState": html.unescape(relay_state),
                "SAMLResponse": html.unescape(SAMLResponse),
            },
        )
        logging.info("logged in")

    def module(self, module: Callable[..., M]) -> M:
        if module not in self.modules:
            self.modules[module] = module(self)
        return self.modules[module]
