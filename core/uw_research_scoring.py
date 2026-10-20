"""Confluence gating for research annotation, not vendor-data-based trade recommendations."""

def assess_research_readiness(technical, snapshot):
    """No score is fabricated from unknown UW response schemas."""
    trends=[technical.get(k) for k in ('4h','1h','5m')]
    aligned=len(trends)==3 and trends[0] in ('Bullish','Bearish') and len(set(trends))==1
    return {'technical_aligned':aligned,
            'direction':trends[0] if aligned else 'WAIT',
            'unusual_whales_data_present':bool(snapshot.get('sources')),
            'unusual_whales_sources':list(snapshot.get('sources',{})),
            'flow_confirmation':'UNVALIDATED_SCHEMA',
            'eligible_for_live_order':False,
            'message':'Raw vendor responses are not normalized into a score until live schema verification and backtests.'}
