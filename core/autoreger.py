import random
import traceback
from asyncio import Semaphore, sleep, create_task, wait
from itertools import zip_longest

from core.utils import logger, file_to_list, str_to_file


class AutoReger:
    def __init__(self):
        self.accounts = []
        self.proxies = []


    @classmethod
    def get_accounts(cls, accounts_file_path, proxies_file_path, with_id=False):
        instance = cls()
        # Baca file akun dan inisialisasi self.accounts
        with open(accounts_file_path, 'r') as file:
            instance.accounts = [line.strip() for line in file.readlines() if line.strip()]

        # Baca file proxy dan inisialisasi self.proxies
        with open(proxies_file_path, 'r') as file:
            instance.proxies = [line.strip() for line in file.readlines() if line.strip()]

        return instance

    async def start(self, worker_func: callable, threads: int = 1, delay: tuple = (0, 0)):
        if not self.accounts or not self.accounts[0]:
            logger.warning("No accounts found :(")
            return

        logger.info(f"Successfully grabbed {len(self.accounts)} accounts")

        self.semaphore = Semaphore(threads)
        self.delay = delay
        await self.define_tasks(worker_func)

        (logger.success if self.success else logger.warning)(
                   f"Successfully handled {self.success} accounts :)" if self.success
                   else "No accounts handled :( | Check logs in logs/out.log")

    async def define_tasks(self, worker_func: callable):
        await wait([create_task(self.worker(account, worker_func)) for account in self.accounts])

    async def worker(self, account: tuple, worker_func: callable):
        account_id = account[0][:15] if isinstance(account, str) else account[0]
        is_success = False

        try:
            async with self.semaphore:
                await self.custom_delay()

                is_success = await worker_func(*account)
        except Exception as e:
            logger.error(f"{account_id} | not handled | error: {e} {traceback.format_exc()}")

        self.success += int(is_success or 0)
        AutoReger.logs(account_id, account, is_success)

    async def custom_delay(self):
        if self.delay[1] > 0:
            sleep_time = random.uniform(*self.delay)
            logger.info(f"Sleep for {sleep_time:.1f} seconds")
            await sleep(sleep_time)

    @staticmethod
    def logs(account_id: str, account: tuple, is_success: bool = False):
        if is_success:
            log_func = logger.success
            log_msg = "handled!"
            file_name = "success"
        else:
            log_func = logger.warning
            log_msg = "failed!"
            file_name = "failed"

        file_msg = "|".join(str(x) for x in account)
        str_to_file(f"./logs/{file_name}.txt", file_msg)

        log_func(f"Account №{account_id} {log_msg}")
