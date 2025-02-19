import re
from datetime import timedelta
from typing import Optional


class TimeSpanParser:
    """Parse time span strings into timedelta objects."""

    TIME_PATTERN = re.compile(r"^(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$")

    @staticmethod
    def parse(timespan: str) -> Optional[timedelta]:
        """
        Parse a time span string into a timedelta.
        Format: [<n>d][<n>h][<n>m][<n>s]
        Examples: '7d', '24h', '30m', '60s', '1d12h', '2d30m', '1h30m'
        """
        if not timespan:
            return None

        match = TimeSpanParser.TIME_PATTERN.match(timespan)
        if not match:
            raise ValueError(
                "Invalid timespan format. Use combinations of: "
                "##d (days), ##h (hours), ##m (minutes), ##s (seconds). "
                "Example: '7d12h30m'"
            )

        days, hours, minutes, seconds = match.groups()

        return timedelta(
            days=int(days or 0),
            hours=int(hours or 0),
            minutes=int(minutes or 0),
            seconds=int(seconds or 0),
        )
