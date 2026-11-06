"""KST membership pricing policy — research only until Stripe phase schedule tested.

No revenue-linked price changes or account P/L dependent charges.
Each user's first 12 months have a fixed, disclosed price contract.
"""
from decimal import Decimal

FIRST_YEAR_MONTHLY_CENTS=10000
RENEWAL_MONTHLY_CENTS=15000
INTRO_MONTHS=12
INTRO_FREE_DAYS=30
INTRO_HALF_OFF_PERCENT=50
VALID_INTRO_CODES=frozenset(("ENZO","MAYVI"))

def monthly_amount(month, code=None):
    if isinstance(month,bool) or not isinstance(month,int) or month<1:
        raise ValueError("Month must be a positive integer")
    if code is not None and code not in VALID_INTRO_CODES:
        raise ValueError("Unknown introductory offer")
    if month>INTRO_MONTHS:
        return RENEWAL_MONTHLY_CENTS
    if code and month==1:
        return 0
    if code:
        return FIRST_YEAR_MONTHLY_CENTS*(100-INTRO_HALF_OFF_PERCENT)//100
    return FIRST_YEAR_MONTHLY_CENTS

def display_pricing(code=None):
    if code is not None and code not in VALID_INTRO_CODES:
        raise ValueError("Unknown intro code")
    return {"currency":"USD","months_1_to_12_regular":FIRST_YEAR_MONTHLY_CENTS,
            "first_month_intro":0 if code else FIRST_YEAR_MONTHLY_CENTS,
            "months_2_to_12_intro":monthly_amount(2,code),
            "month_13_plus":RENEWAL_MONTHLY_CENTS,
            "intro_free_days":INTRO_FREE_DAYS if code else 0,
            "price_changes_require_disclosure":True,
            "pricing_is_independent_of_member_trade_returns":True}

def validate_stripe_price(price,expected_cents):
    recurring=price.get("recurring") or {}
    return (price.get("active") is True
            and price.get("currency")=="usd"
            and price.get("unit_amount")==expected_cents
            and recurring.get("interval")=="month"
            and recurring.get("interval_count",1)==1)

def require_ready_for_subscription(env):
    """Protect clients from an undisclosed or unscheduled renewal increase.

    The production flag must only be enabled after phase scheduling, webhook
    verification and end-to-end Stripe test checkout are implemented.
    """
    if not env.get("STRIPE_YEAR_TWO_PRICE_ID"):
        raise ValueError("Year-two $150 monthly price is not configured")
    if env.get("KST_BILLING_PHASES_VERIFIED")!="true":
        raise ValueError("KST introductory and renewal billing schedule is not yet verified")
    return True
