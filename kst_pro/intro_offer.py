"""KST introductory membership offer, exclusively server validated.

ENZO and MAYVI are equivalent mutually exclusive offers:
30 free trial days, then 50% off monthly billing through month 12 after signup.
Only one redemption per authenticated KST account.
"""
from urllib.parse import urlsplit
import re

CODES=frozenset(("ENZO","MAYVI"))
TRIAL_DAYS=30

def code_from_input(value):
 if value is None or value=="":return None
 if not isinstance(value,str):raise ValueError("Invalid introductory code")
 code=value.strip().upper()
 if code not in CODES:raise ValueError("Invalid introductory code")
 return code

def intro_coupon(env,lookup):
 """Require preconfigured Stripe coupon exactly matching the advertised offer.

 Stripe repeating coupons run from redemption time, including trial, so a
 12-month coupon covers the first ~11 paid monthly invoices after free month.
 """
 coupon_id=env.get("STRIPE_INTRO_COUPON_ID","").strip()
 if not re.fullmatch(r"[A-Za-z0-9_-]{3,100}",coupon_id):
  raise ValueError("The introductory discount is not configured in Stripe")
 coupon=lookup("GET","coupons/"+coupon_id,env)
 if not coupon.get("valid") or coupon.get("percent_off")!=50 or coupon.get("duration")!="repeating" or coupon.get("duration_in_months")!=12:
  raise ValueError("Stripe coupon must provide 50% off for the first 12 months")
 return coupon_id

def intro_checkout_data(code,coupon_id):
 if code not in CODES:raise ValueError("Invalid introductory code")
 return {"subscription_data[trial_period_days]":str(TRIAL_DAYS),
         "payment_method_collection":"always",
         "discounts[0][coupon]":coupon_id,
         "metadata[kst_intro_code]":code,
         "subscription_data[metadata][kst_intro_code]":code}
