class FullyKioskError(Exception):
    """Raised when Fully Kiosk Browser API request ended in error.
    Attributes:
        status_code - error code returned by Fully Kiosk Browser
        status - more detailed description
    """

    def __init__(self, status_code, status):
        self.status_code = status_code
        self.status = status
