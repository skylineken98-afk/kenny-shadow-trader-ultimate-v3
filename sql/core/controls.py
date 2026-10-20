import os

def execution_guard(requested_mode,explicit_approval=False,broker_verified=False,risk_controls_verified=False):
    if requested_mode=='paper':return {'allowed':True,'mode':'paper'}
    # Locked in this release even when flags accidentally set.
    return {'allowed':False,'mode':'disabled','reason':'Live trading not implemented or validated in this release'}
