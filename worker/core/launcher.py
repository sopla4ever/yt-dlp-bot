import asyncio
import logging

from yt_dlp import version as ytdlp_version

from core.callbacks import callbacks as cb
from yt_shared.config import MAX_SIMULTANEOUS_DOWNLOADS
from yt_shared.db import get_db
from yt_shared.rabbit import get_rabbitmq
from yt_shared.rabbit.rabbit_config import INPUT_QUEUE
from yt_shared.repositories.ytdlp import YtdlpRepository


class WorkerLauncher:

    def __init__(self) -> None:
        self._log = logging.getLogger(self.__class__.__name__)
        self._rabbit_mq = get_rabbitmq()

    async def start(self) -> None:
        log_format = '%(asctime)s - [%(levelname)s] - [%(name)s:%(lineno)s] - %(message)s'
        logging.basicConfig(format=log_format, level=logging.INFO)

        self._log.info('Starting worker instance')
        await asyncio.gather(self._setup_rabbit(), self._set_yt_dlp_version())

    async def _setup_rabbit(self) -> None:
        self._log.info('Setting up RabbitMQ connection')
        await self._rabbit_mq.register()
        await self._rabbit_mq.channel.set_qos(
            prefetch_count=MAX_SIMULTANEOUS_DOWNLOADS)
        await self._rabbit_mq.queues[INPUT_QUEUE].consume(cb.on_input_message)

    async def _set_yt_dlp_version(self):
        curr_version = ytdlp_version.__version__
        self._log.info('Setting current yt-dlp version (%s)', curr_version)
        async for db in get_db():
            await YtdlpRepository().create_or_update_version(db, curr_version)

    async def stop(self) -> None:
        loop = asyncio.get_running_loop()
        loop.run_until_complete(self._rabbit_mq.close())