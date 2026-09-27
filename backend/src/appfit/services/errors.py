from http import HTTPStatus


class ServiceError(Exception):
    """Domain error that routers translate into an HTTP response."""

    status_code = HTTPStatus.BAD_REQUEST

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(ServiceError):
    status_code = HTTPStatus.NOT_FOUND


class ConflictError(ServiceError):
    status_code = HTTPStatus.CONFLICT


class TooLargeError(ServiceError):
    status_code = HTTPStatus.REQUEST_ENTITY_TOO_LARGE


class UnavailableError(ServiceError):
    status_code = HTTPStatus.SERVICE_UNAVAILABLE
