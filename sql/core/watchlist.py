"""Returns a watchlist intent, not a claim that Robinhood has been updated."""
def paper_decision_to_watchlist_intent(symbol,instrument_type='stock',contract_symbol=None):
    if instrument_type=='option' and not contract_symbol:raise ValueError('Exact option contract required')
    return {'ticker':symbol,'instrument_type':instrument_type,'contract_symbol':contract_symbol,'status':'PENDING_USER_AUTHORIZED_INTEGRATION','order_placed':False,'notification_sent':False}
