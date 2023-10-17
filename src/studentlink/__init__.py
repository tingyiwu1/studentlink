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


class ConnectionError(Exception):
    pass


class InternalError(Exception):
    pass


class StudentLink:
    def __init__(
        self, session: aiohttp.ClientSession = None, logger: logging.Logger = None
    ):
        self.session, self.owns_session = (
            (session, False) if session else (aiohttp.ClientSession(), True)
        )
        self.logger = logger or logging.getLogger(__name__)
        self.modules: dict[type, Module] = {}

    async def __aenter__(self):
        if self.owns_session:
            await self.session.__aenter__()
        return self

    async def __aexit__(self, *args):
        if self.owns_session:
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
        if "not available: Connection refused" in t:
            raise ConnectionError("Connection refused")
        if "<title>Error &middot; Boston University</title>" in t:
            raise InternalError(f"{r.url}\n{t}")
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

    async def get_page(self, url, *, params: dict[str, str] = None) -> str:
        login_errors = []
        for _ in range(self.login_retries):
            r = await self.session.get(url, params=params)
            t = await r.text()
            if "not available: Connection refused" in t:
                raise ConnectionError("Connection refused")
            if "<title>Error &middot; Boston University</title>" in t:
                raise InternalError(f"{r.url}\n{t}")
            if "<title>Boston University | Login</title>" in t:
                try:
                    await self.login(r)
                    continue
                except LoginError as e:
                    login_errors.append(e)
                    continue
            elif "Web Login Service - Stale Request" in t:  # untested
                try:
                    await self.login()
                    continue
                except LoginError as e:
                    login_errors.append(e)
                    continue
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
        matches = re.findall(r"name=\"csrf_token\" value=\"(.+)\"", t)
        try:
            csrf_token = matches[0]
        except IndexError:
            raise LoginError(f"couldn't find csrf_token: {r.url}\n{t}")
        if "You have asked to login to " in t:
            r2 = await self.session.post(
                URL(
                    "https://shib.bu.edu/idp/profile/SAML2/POST-SimpleSign/SSO"
                ).with_query(execution=execution),
                data={
                    "csrf_token": csrf_token,
                    "j_username": self.username,
                    "j_password": self.password,
                    "_eventId_proceed": "",
                },
            )
        elif "Two-Step Login Started" in t:
            r2 = r
        else:
            raise LoginError(f"unknown login page: {r.url}\n{t}")
        r2: aiohttp.ClientResponse
        t2 = await r2.text()
        if "you must press the Continue button once to proceed." in t2:
            r8 = r2
        else:
            sid = r2.url.query.get("sid")
            if not sid:
                raise LoginError(f"sid not found in {r2.url}")
            matches2 = re.findall(r'name="tx" value="(.+)"', t2)
            try:
                tx = matches2[0]
            except IndexError:
                raise LoginError(f"couldn't find tx: {r2.url}\n{t2}")
            # r2_25 = await self.session.post(
            #     URL(
            #         "https://shib.bu.edu/idp/profile/SAML2/POST-SimpleSign/SSO"
            #     ).with_query(
            #         execution=execution[:-1] + "2",
            #     ),
            # )
            # t2_25 = await r2_25.text()
            # r2_5 = await self.session.get(
            #     URL(
            #         "https://shib.bu.edu/idp/profile/Authn/Duo/2FA/authorize"
            #     ).with_query(
            #         conversation=execution[:-1] + "2",
            #     )
            # )
            # t2_5 = await r2_5.text()
            # r2_75 = await self.session.get(
            #     URL(
            #         "https://api-c6b0c057.duosecurity.com/frame/frameless/v4/auth"
            #     ).with_query(
            #         sid=sid,
            #         tx=tx,
            #     )
            # )
            # t2_75 = await r2_75.text()  # _xsrf should be here
            matches2_5 = re.findall(r'name="_xsrf" value="(.+)"', t2)
            _xsrf = matches2_5[0]
            # needs form data
            r3 = await self.session.post(
                URL(
                    "https://api-c6b0c057.duosecurity.com/frame/frameless/v4/auth"
                ).with_query(
                    sid=sid,
                    tx=tx,
                ),
                data={
                    "tx": tx,
                    "_xsrf": _xsrf,
                    "parent": "None",
                    "java_version": "",
                    "flash_version": "",
                    "screen_resolution_width": 1512,
                    "screen_resolution_height": 982,
                    "color_depth": 30,
                    "ch_ua_error": "",
                    "client_hints": "eyJicmFuZHMiOlt7ImJyYW5kIjoiR29vZ2xlIENocm9tZSIsInZlcnNpb24iOiIxMTcifSx7ImJyYW5kIjoiTm90O0E9QnJhbmQiLCJ2ZXJzaW9uIjoiOCJ9LHsiYnJhbmQiOiJDaHJvbWl1bSIsInZlcnNpb24iOiIxMTcifV0sImZ1bGxWZXJzaW9uTGlzdCI6W3siYnJhbmQiOiJHb29nbGUgQ2hyb21lIiwidmVyc2lvbiI6IjExNy4wLjU5MzguMTQ5In0seyJicmFuZCI6Ik5vdDtBPUJyYW5kIiwidmVyc2lvbiI6IjguMC4wLjAifSx7ImJyYW5kIjoiQ2hyb21pdW0iLCJ2ZXJzaW9uIjoiMTE3LjAuNTkzOC4xNDkifV0sIm1vYmlsZSI6ZmFsc2UsInBsYXRmb3JtIjoibWFjT1MiLCJwbGF0Zm9ybVZlcnNpb24iOiIxMy40LjEiLCJ1YUZ1bGxWZXJzaW9uIjoiMTE3LjAuNTkzOC4xNDkifQ",
                    "is_cef_browser": False,
                    "is_ipad_os": False,
                    "is_ie_compatibility_mode": "",
                    "is_user_verifying_platform_authenticator_available": True,
                    "user_verifying_platform_authenticator_available_error": "",
                    "acting_ie_version": "",
                    "react_support": True,
                    "react_support_error_message": "",
                },
            )
            t3 = await r3.text()
            # r3_5 = await self.session.get(
            #     URL(
            #         "https://api-c6b0c057.duosecurity.com/frame/v4/auth/prompt"
            #     ).with_query(sid=sid)
            # )
            # t3_5 = await r3_5.text()
            r3_75 = await self.session.get(
                URL(
                    "https://api-c6b0c057.duosecurity.com/frame/v4/auth/prompt/data"
                ).with_query(sid=sid, post_auth_action="OIDC_EXIT")
            )
            t3_75 = await r3_75.text()
            json3_75 = await r3_75.json()
            # fails here message enum 57 but no idea what that means

            if not (device_key := json3_75.get("response").get("phones")[0]["key"]):
                raise LoginError(f"couldn't find device_key in {json3_75}")

            # r3_5 = await self.session.post(
            #     URL("https://api-c6b0c057.duosecurity.com/frame/v4/prompt"),
            #     data={
            #         "tx": tx,
            #         "parent": None,
            #         "_xsrf": '', # something
            #         # "client_hints":
            #     }
            # )
            # if "Logging you in..." in t3:  # duo remembers user
            if False: # TODO: skip until we see if this is necessary
                matches3 = re.findall(
                    r'name="js_cookie" value="(.+)"[\S\s]+name="js_parent" value="(.+)"',
                    t3,
                )
                try:
                    ((duo_sig, parent),) = matches3
                    duo_sig = html.unescape(duo_sig)
                    parent = html.unescape(parent)
                except ValueError:
                    raise LoginError(
                        f"couldn't find duo_sig and parent: {r3.url}\n{t3}"
                    )
            else:
                sid = r3.url.query.get("sid")
                if not sid:
                    raise LoginError(f"sid not found in {r3.url}")

                self.logger.info("sending duo push")
                r4 = await self.session.post(
                    "https://api-c6b0c057.duosecurity.com/frame/v4/prompt",
                    data={
                        "sid": sid,
                        "device": "phone1",  # TODO: make this more robust
                        "factor": "Duo Push",
                        "postAuthDestination": "OIDC_EXIT",
                        # "dampen_choice": "true",
                        # "out_of_date": "",
                        # "days_out_of_date": "",
                        # "days_to_block": "None",
                    },
                )
                response4 = (await r4.json())["response"]
                if not (txid := response4.get("txid")):
                    raise LoginError(f"couldn't find txid in {response4}")
                r5 = await self.session.post(
                    "https://api-c6b0c057.duosecurity.com/frame/v4/status",
                    data={"sid": sid, "txid": txid},
                )
                r6 = await self.session.post(
                    "https://api-c6b0c057.duosecurity.com/frame/v4/status",
                    data={"sid": sid, "txid": txid},
                )
                response6 = (await r6.json())["response"]
                # if not (result_url := response6.get("result_url")):
                #     raise LoginError(f"couldn't find result_url in {response6}")
                # r7 = await self.session.post(
                #     f"https://api-c6b0c057.duosecurity.com{result_url}",
                #     data={"sid": sid},
                # )
                # response7 = (await r7.json())["response"]
                # if not (parent := response7.get("parent")):
                #     raise LoginError(f"couldn't find parent in {response7}")
                # if not (duo_sig := response7.get("cookie")):
                #     raise LoginError(f"couldn't find cookie in {response7}")
                r8 = await self.session.post(
                    "https://api-c6b0c057.duosecurity.com/frame/v4/oidc/exit",
                    data={
                        "sid": sid,
                        "txid": txid,
                        "factor": "Duo Push",
                        "device_key": device_key,
                        "_xsrf": _xsrf,
                        "dampen_choice": True,
                    },
                )
            # r8 = await self.session.post(
            #     parent[:-1] + "2",  # e1s1 -> e1s2
            #     data={"_eventId": "proceed", "signedDuoResponse": f"{duo_sig}:{app}"},
            # )
        r8: aiohttp.ClientResponse
        t8 = await r8.text()
        matches8 = re.findall(r'input type="hidden" name="(.+?)" value="(.+?)"', t8)
        try:
            (_, relay_state), (_, SAMLResponse) = matches8
        except ValueError:
            raise LoginError(
                f"couldn't find relay_state and SAMLResponse: {r8.url}\n{t8}"
            )
        r9 = await self.session.post(
            "https://linklogin.bu.edu/Shibboleth.sso/SAML2/POST",
            data={
                "RelayState": html.unescape(relay_state),
                "SAMLResponse": html.unescape(SAMLResponse),
            },
        )
        # t9 = await r9.text()
        self.logger.info("logged in")

    def module(self, module: Callable[..., M]) -> M:
        if module not in self.modules:
            self.modules[module] = module(self)
        return self.modules[module]
