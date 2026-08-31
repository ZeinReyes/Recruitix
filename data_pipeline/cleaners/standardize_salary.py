import re

MONTHLY_PERIODS = {"month", "months", "mo", "monthly", "/mo", "/month", "per month"}
ANNUAL_PERIODS = {"year", "years", "yr", "yrs", "annum", "annual", "annually",
                   "yearly", "/yr", "/year", "per annum"}
HOURLY_PERIODS = {"hour", "hours", "hr", "hrs", "hourly", "/hr", "/hour", "per hour"}
DAILY_PERIODS = {"day", "days", "daily", "/day", "per day"}
WEEKLY_PERIODS = {"week", "weeks", "weekly", "/week", "per week"}

NUMBER_PATTERN = r"\d[\d,]*(?:\.\d+)?[kK]?"

# Matches things like "13th month pay", "14th month", "half month pay" —
# these are bonus-pay mentions, not salary figures, and must be stripped
# BEFORE number extraction or they get parsed as a second salary value.
NON_SALARY_NUMBER_PATTERN = re.compile(
    r"\b\d+\s*(?:st|nd|rd|th)\s+month\b", re.IGNORECASE
)

# A dash/"to" separated range where only the second number carries the
# "k" suffix, e.g. "15-20k" or "15,000-20K" meaning 15,000-20,000.
RANGE_PATTERN = re.compile(
    r"(?P<low>\d[\d,]*(?:\.\d+)?)\s*(?:-|–|to)\s*(?P<high>\d[\d,]*(?:\.\d+)?)\s*(?P<k>[kK])?"
)


def _parse_number(token: str) -> float:
    token = token.strip().replace(",", "")
    if token.lower().endswith("k"):
        return float(token[:-1]) * 1000
    return float(token)


def _contains_period(text: str, period: str) -> bool:
    text_lower = text.lower()
    period = period.lower().strip()
    if period.startswith("/") or period.startswith("per "):
        return period in text_lower
    return bool(re.search(rf"\b{re.escape(period)}\b", text_lower))


def _detect_period(text: str):
    for period in ANNUAL_PERIODS:
        if _contains_period(text, period):
            return "annual"
    for period in HOURLY_PERIODS:
        if _contains_period(text, period):
            return "hourly"
    for period in DAILY_PERIODS:
        if _contains_period(text, period):
            return "daily"
    for period in WEEKLY_PERIODS:
        if _contains_period(text, period):
            return "weekly"
    for period in MONTHLY_PERIODS:
        if _contains_period(text, period):
            return "monthly"
    return None


def _detect_currency(text: str):
    text_upper = text.upper()
    if "₱" in text or "PHP" in text_upper or re.search(r"\bP\s*[\d,]", text_upper):
        return "PHP"
    if "USD" in text_upper or "$" in text:
        return "USD"
    if "EUR" in text_upper or "€" in text:
        return "EUR"
    if "GBP" in text_upper or "£" in text:
        return "GBP"
    if "JPY" in text_upper or "¥" in text:
        return "JPY"
    return None


def _is_not_disclosed(text: str) -> bool:
    patterns = [
        r"\bcompetitive\b", r"\bnegotiable\b", r"\bundisclosed\b",
        r"\bnot\s+disclosed\b", r"\bnot\s+specified\b",
        r"\bdepends?\s+on\s+experience\b", r"\bdoe\b",
        r"\bto\s+be\s+discussed\b", r"\btbd\b",
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def standardize_salary(raw: str, default_currency: str = "PHP") -> dict:
    result = {
        "salary_min": None, "salary_max": None, "salary_period": None,
        "salary_disclosed": False, "currency": None,
    }

    if raw is None:
        return result
    text = str(raw).strip()
    if not text:
        return result

    if _is_not_disclosed(text):
        return result

    detected_currency = _detect_currency(text)

    # Strip bonus-pay mentions ("13th month pay") so their numbers never
    # enter the salary figure extraction below.
    numeric_text = NON_SALARY_NUMBER_PATTERN.sub(" ", text)

    # Try to parse as an explicit range first, so a shared "k" suffix
    # ("15-20k") is distributed to both sides instead of only the second.
    range_match = RANGE_PATTERN.search(numeric_text)
    if range_match:
        low_raw, high_raw, k = (
            range_match.group("low"),
            range_match.group("high"),
            range_match.group("k"),
        )
        low = _parse_number(f"{low_raw}{k or ''}")
        high = _parse_number(f"{high_raw}{k or ''}")
        salary_min, salary_max = min(low, high), max(low, high)
    else:
        numbers = re.findall(NUMBER_PATTERN, numeric_text)
        if not numbers:
            return result
        try:
            values = [_parse_number(n) for n in numbers]
        except (ValueError, TypeError):
            return result
        if not values:
            return result
        if len(values) == 1:
            salary_min = salary_max = values[0]
        else:
            salary_min, salary_max = min(values[0], values[1]), max(values[0], values[1])

    # Reject non-positive figures. A salary of exactly 0 is never a real
    # disclosed figure -- it's almost always a bad parse (e.g. a stray
    # "0" surviving punctuation/placeholder text that _is_not_disclosed()
    # didn't catch). Letting a 0 through as "disclosed" poisons downstream
    # MIN() aggregates in the analytics API, making the lowest-salary KPI
    # look broken even though every other figure is fine.
    if salary_min <= 0 or salary_max <= 0:
        return result

    result.update({
        "salary_min": round(salary_min, 2),
        "salary_max": round(salary_max, 2),
        "salary_period": _detect_period(numeric_text),
        "salary_disclosed": True,
        "currency": detected_currency or default_currency,
    })
    return result


if __name__ == "__main__":
    tests = [
        "P30,000/month", "30K monthly", "P360,000/year",
        "P15,000 - P20,000/month", "Competitive salary", "600",
        "15-20k", "15k-20k", "P20,000/month + 13th month pay",
        "P18,000 + 14th month bonus", "P25,000", "0", "P0/month",
    ]
    for t in tests:
        print(f"{t!r:45} -> {standardize_salary(t)}")