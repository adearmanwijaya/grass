import asyncio
import uuid
import time
import aiohttp
from fake_useragent import UserAgent
from tenacity import stop_after_attempt, retry, retry_if_not_exception_type, wait_random, retry_if_exception_type
import itertools
import sys
import threading
from data.config import MIN_PROXY_SCORE
from .grass_sdk.extension import GrassWs
from .grass_sdk.website import GrassRest
from .utils import logger
from .utils.exception import WebsocketClosedException, LowProxyScoreException, ProxyScoreNotFoundException, \
    ProxyForbiddenException
from better_proxy import Proxy
from core.utils.global_store import mined_grass_counts, lock


class Grass(GrassWs, GrassRest):
    def __init__(self, _id: int, email: str, password: str, proxy: str = None):
        self.mined_grass_count = 0 
        self.has_mined_successfully = False  # Tambahkan ini
        if proxy:
            if "@" in proxy:
                # Proxy dengan autentikasi
                self.proxy = Proxy.from_str(proxy).as_url
            else:
                # Proxy tanpa autentikasi
                self.proxy = f"socks://{proxy}"
        else:
            self.proxy = None
        super(GrassWs, self).__init__(email=email, password=password, user_agent=UserAgent().random, proxy=self.proxy)
        self.proxy_score = None
        self.id = _id
        self.animation = itertools.cycle(['|', '/', '-', '\\'])

        self.session = aiohttp.ClientSession(trust_env=True, connector=aiohttp.TCPConnector(ssl=False))

    async def load_user_id(self):
        loop = asyncio.get_event_loop()
        with open('user_id.txt', mode='r') as f:
            return await loop.run_in_executor(None, f.read)
    def animate(self, countdown_event):
        while True:
            for remaining in range(120, 0, -1):
                sys.stdout.write(f"\rSisa waktu untuk ping lagi: {remaining} detik {next(self.animation)}")
                sys.stdout.flush()
                time.sleep(1)
                if countdown_event.is_set():
                    break
    async def start(self):
        countdown_event = threading.Event()
        animation_thread = threading.Thread(target=self.animate, args=(countdown_event,))
        animation_thread.daemon = True
        animation_thread.start()

        user_id = await self.load_user_id()  # Load user_id from file
        browser_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, self.proxy or ""))

        await self.run(browser_id, user_id, countdown_event)




    async def run(self, browser_id: str, user_id: str, countdown_event):
        global mined_grass_counts
        while True:
            try:
                await self.connection_handler()
                await self.auth_to_extension(browser_id, user_id)

                while True:
                    await self.send_ping()
                    await self.send_pong()
                    if not self.has_mined_successfully:
                        self.mined_grass_count += 1
                        self.has_mined_successfully = True  # Setelah berhasil mining, set flag ini
                    
                    async with lock:
                        mined_grass_counts[self.id] = self.mined_grass_count
                        total_mined = sum(mined_grass_counts.values())  # Hitung total mined_grass_counts
                    logger.info(f"{self.id} | Mined grass | Total : {total_mined}")    
                    
                    countdown_event.clear()
                    for _ in range(120):
                        await asyncio.sleep(1)
                        if countdown_event.is_set():
                            break
                    countdown_event.set()  # Reset the event for the next countdown
            except WebsocketClosedException as e:
                logger.info(f"Websocket closed: {e}. Retrying...")
                if self.has_mined_successfully:  # Hanya kurangi jika sebelumnya berhasil
                    async with lock:
                        self.mined_grass_count = max(0, self.mined_grass_count - 1)
                        self.has_mined_successfully = False  # Reset flag setelah gagal
                        mined_grass_counts[self.id] = self.mined_grass_count
            except ConnectionResetError as e:
                logger.info(f"Connection reset: {e}. Retrying...")
                if self.has_mined_successfully:  # Hanya kurangi jika sebelumnya berhasil
                    async with lock:
                        self.mined_grass_count = max(0, self.mined_grass_count - 1)
                        self.has_mined_successfully = False  # Reset flag setelah gagal
                        mined_grass_counts[self.id] = self.mined_grass_count
            await asyncio.sleep(1)

    @retry(stop=stop_after_attempt(30),
           retry=(retry_if_exception_type(ConnectionError) | retry_if_not_exception_type(ProxyForbiddenException)),
           wait=wait_random(0.5, 1),
           reraise=True)
    async def connection_handler(self):
        logger.info(f"{self.id} | Connecting...")
        await self.connect()
        logger.info(f"{self.id} | Connected")

    @retry(stop=stop_after_attempt(20),
           retry=retry_if_not_exception_type(LowProxyScoreException),
           before_sleep=lambda retry_state, **kwargs: logger.info(f"{retry_state.outcome.exception()}"),
           wait=wait_random(5, 7),
           reraise=True)
    async def handle_proxy_score(self, min_score: int):
        if (proxy_score := await self.get_proxy_score_by_device_id()) is None:
            raise ProxyScoreNotFoundException(f"{self.id} | Proxy score not. Retrying...")
        elif proxy_score >= min_score:
            self.proxy_score = proxy_score
            logger.success(f"{self.id} | Proxy score: {self.proxy_score}")
            return True
        else:
            raise LowProxyScoreException(f"{self.id} | Too low proxy score: {proxy_score} for {self.proxy}. Exit...")
