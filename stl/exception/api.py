class ApiException(Exception):
    """Exception raised for errors with API."""

    def __init__(self, errors: list):
        super().__init__('\n'.join([msg['message'] for msg in errors]))


class ForbiddenException(ApiException):
    """HTTP 403 Forbidden Exception"""
    pass


class ServerException(ApiException):
    """HTTP 500 Server Error Exception"""
    pass
