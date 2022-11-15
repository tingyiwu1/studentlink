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
        login_retries: int = 3,
    ):
        super().__init__(session, logger)
        self.username = username
        self.password = password
        self.login_retries = login_retries

    async def __aenter__(self):
        await super().__aenter__()
        return self

    async def get_page(self, url, *, params: dict[str, str] = None) -> str:
        login_errors = []
        for _ in range(self.login_retries):
            r = await self.session.get(url, params=params)
            t = await r.text()
            if "<title>Boston University | Login</title>" in t:
                try:
                    await self.login(r)
                except LoginError as e:
                    login_errors.append(e)
                    logging.error(e)
                    continue
            else:
                return t
        raise LoginError(login_errors or "unknown error")

    async def login(self, r: aiohttp.ClientResponse = None):
        if r is None:
            r = await self.session.get(Module.mod_url("allsched.pl"))
        execution = r.url.query.get("execution")
        if not execution:
            raise LoginError(f"execution not found in {r.url}")
        self.logger.info("logging in")
        t = await r.text()
        if "You have asked to login to " in t:
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
        elif "Two-Step Login Started" in t:
            r2 = r
        else:
            raise LoginError(f"unknown login page: {t}")
        t2 = await r2.text()
        matches2 = re.findall(r"'sig_request': '(TX.+?):(APP.+?)'", t2)
        try:
            tx, app = matches2[0]
        except IndexError:
            raise LoginError(f"couldn't find tx and app: {t2}")
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
        t3 = await r3.text()
        assert t3
        
        if "Logging you in..." in t3: # 
            matches3 = re.findall(r'name="js_cookie" value="(.+)"[\S\s]+name="js_parent" value="(.+)"', t3)
            try:
                (duo_sig, parent), = matches3
                duo_sig = html.unescape(duo_sig)
                parent = html.unescape(parent)
            except ValueError:
                raise LoginError(f"couldn't find duo_sig and parent: {t3}")
            # logging.info("logged in with cookie")
        else:
            sid = r3.url.query.get("sid")
            if not sid:
                raise LoginError(f"sid not found in {r3.url}")
            
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
            response4 = (await r4.json())["response"]
            if not (txid := response4.get("txid")):
                raise LoginError(f"couldn't find txid in {response4}")
            await self.session.post(
                "https://api-c6b0c057.duosecurity.com/frame/status",
                data={"sid": sid, "txid": txid},
            )
            r6 = await self.session.post(
                "https://api-c6b0c057.duosecurity.com/frame/status",
                data={"sid": sid, "txid": txid},
            )
            response6 = (await r6.json())["response"]
            if not (result_url := response6.get("result_url")):
                raise LoginError(f"couldn't find result_url in {response6}")
            r7 = await self.session.post(
                f"https://api-c6b0c057.duosecurity.com{result_url}", data={"sid": sid}
            )
            response7 = (await r7.json())["response"]
            if not (parent := response7.get("parent")):
                raise LoginError(f"couldn't find parent in {response7}")
            if not (duo_sig := response7.get("cookie")):
                raise LoginError(f"couldn't find cookie in {response7}")
        r8 = await self.session.post(
            parent,
            data={"_eventId": "proceed", "signedDuoResponse": f"{duo_sig}:{app}"},
        )
        t8 = await r8.text()
        matches8 = re.findall(
            r'input type="hidden" name="(.+?)" value="(.+?)"', t8
        )
        try:
            (_, relay_state), (_, SAMLResponse) = matches8
        except ValueError as e:
            raise LoginError(f"couldn't find relay_state and SAMLResponse: {t8}")
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
