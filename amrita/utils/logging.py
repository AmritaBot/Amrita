from asyncio import Lock
from datetime import datetime
from pathlib import Path
from typing import Literal

import aiofiles
from pydantic import BaseModel, Field

from amrita.config import get_amrita_config

_lock = Lock()


class LoggingEvent(BaseModel):
    log_level: Literal["WARNING", "ERROR", "FATAL", "INFO"]
    description: str
    message: str
    time: datetime = Field(default_factory=datetime.now)


class LoggingData(BaseModel):
    data: list[LoggingEvent] = []

    @staticmethod
    async def _limit_length():
        data = await LoggingData.get()
        while len(data.data) > get_amrita_config().max_event_record:
            data.data.pop(0)
        await data.save()

    async def save(self):
        async with _lock:
            async with aiofiles.open(
                Path(get_amrita_config().log_dir) / "event.json", "w", encoding="utf-8"
            ) as f:
                await f.write(self.model_dump_json())

    @staticmethod
    async def get():
        await LoggingData._limit_length()
        log_path = Path(get_amrita_config().log_dir) / "event.json"
        if not log_path.exists():
            data = LoggingData()
            async with aiofiles.open(log_path, "w", encoding="utf-8") as f:
                await f.write(data.model_dump_json())
        else:
            async with aiofiles.open(log_path, encoding="utf-8") as f:
                data = LoggingData.model_validate_json(await f.read())
        return data

    @staticmethod
    def _get_data_sync():
        log_path = Path(get_amrita_config().log_dir) / "event.json"
        if not log_path.exists():
            data = LoggingData()
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(data.model_dump_json())
        else:
            with open(log_path, encoding="utf-8") as f:
                data = LoggingData.model_validate_json(f.read())
        return data
    async def append(self, event: LoggingEvent):
        self.data.append(event)
        await self.save()
