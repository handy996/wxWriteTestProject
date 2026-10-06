package com.example.editorial.shared;

/** Only fixed, reviewed messages may cross the HTTP boundary. No exception causes/payloads. */
public final class PublicFailure extends RuntimeException {
    private final int status;
    private final String code;
    public PublicFailure(int status, String code) { super(code); this.status = status; this.code = code; }
    public int status() { return status; }
    public String code() { return code; }
    public boolean retryable() { return status == 429 || status == 503; }
    public String safeMessage() {
        return switch (status) {
            case 400, 422 -> "Request is invalid";
            case 401 -> "Authentication required";
            case 403 -> "Request is not permitted";
            case 404 -> "Resource not found";
            case 409 -> "Request conflicts with existing state";
            case 412 -> "Resource has changed";
            case 428 -> "Required precondition is missing";
            case 429 -> "Too many requests";
            default -> "Service temporarily unavailable";
        };
    }
}
