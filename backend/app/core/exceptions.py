"""Application exception hierarchy."""


class AppError(Exception):
    """Base application error."""
    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code = 404
    error_code = "not_found"


class ValidationError(AppError):
    status_code = 422
    error_code = "validation_error"


class DuplicateMessageError(AppError):
    """Raised when a message_id has already been processed."""
    status_code = 200  # Return 200 with original reply
    error_code = "duplicate_message"


class PaymentError(AppError):
    status_code = 500
    error_code = "payment_error"


class PaySwiftError(AppError):
    status_code = 502
    error_code = "payswift_error"


class PaySwiftUncertainError(PaySwiftError):
    """Payment outcome is unknown (timeout/race). Must reconcile before retry."""
    def __init__(self, message: str, idempotency_key: str = ""):
        super().__init__(message)
        self.idempotency_key = idempotency_key

class PolicyViolationError(AppError):
    status_code = 422
    error_code = "policy_violation"


class LLMError(AppError):
    status_code = 500
    error_code = "llm_error"
