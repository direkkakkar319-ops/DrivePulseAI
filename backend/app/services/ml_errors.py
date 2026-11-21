"""Safe, model-independent upstream failure contract."""


class MLServiceError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code
