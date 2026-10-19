def aggregate(symbol_signals):
    bull=sum(1 for x in symbol_signals if x.get('side')=='BULLISH' and x.get('status')=='SETUP')
    bear=sum(1 for x in symbol_signals if x.get('side')=='BEARISH' and x.get('status')=='SETUP')
    return {'bullish_setups':bull,'bearish_setups':bear,'neutral_or_wait':len(symbol_signals)-bull-bear,'label':'bullish' if bull>bear else 'bearish' if bear>bull else 'mixed','source':'scan_breadth_only','not_fear_greed_index':True}
