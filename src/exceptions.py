"""Custom exceptions for the application."""

class PDFConverterError(Exception):
    """Base exception for PDF conversion errors."""
    pass


class PDFConversionEmptyError(PDFConverterError):
    """Raised when PDF conversion yields no images."""
    pass


class APIRequestError(Exception):
    """Base exception for API request errors."""
    pass


class APIResponseEmptyError(APIRequestError):
    """Raised when API returns empty response."""
    pass


class APIAuthenticationError(APIRequestError):
    """Raised when API key is invalid."""
    pass