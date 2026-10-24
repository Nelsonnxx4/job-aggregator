import sys

from app.config import settings
from app.services.notifications import send_telegram_test_message


def main() -> int:
    try:
        sent, error = send_telegram_test_message(settings)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not sent:
        print(f"Telegram test delivery failed: {error}", file=sys.stderr)
        return 1

    print("Telegram test message delivered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
