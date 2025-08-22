from typing_extensions import Self


class StatusManager:
    _instance = None
    __repair = False
    __disable = False

    def __new__(cls) -> Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def set_disable(self, value: bool):
        self.__disable = value

    def set_unready(self, value: bool):
        self.__repair = value

    def is_unready(self) -> bool:
        return self.__repair

    def is_disabled(self) -> bool:
        return self.__disable

    @property
    def ready(self) -> bool:
        return (not self.__repair) and (not self.__disable)
