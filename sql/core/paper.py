import uuid
from core.db import insert,fetch,now
from core.risk import sizing,permitted

def open_paper_trade(symbol,asset_class,side,entry,stop,target,equity=10000,cash=10000,day_start_equity=10000,gross_exposure=0,kill=False,agent='conservative'):
    if asset_class not in ('stock','crypto','forex','future'):
        return {'ok':False,'error':'Only simplified spot-equivalent paper positions are supported. Options/futures contract mechanics are not implemented.'}
    if side not in ('BUY','SELL'):return {'ok':False,'error':'invalid side'}
    if entry<=0 or stop is None or target is None:return {'ok':False,'error':'invalid prices'}
    qty=sizing(cash,equity,entry,stop)
    if qty<1:return {'ok':False,'error':'position sizing returned 0'}
    allowed,reason=permitted(equity,day_start_equity,gross_exposure,qty*entry,killed=kill)
    if not allowed:return {'ok':False,'error':reason}
    row={'id':str(uuid.uuid4()),'created_at':now(),'symbol':symbol,'asset_class':asset_class,'side':side,'qty':qty,'entry':entry,'stop':stop,'target':target,'status':'OPEN','agent':agent,'simulation_only':True}
    return insert('paper_trades',row)

def close_paper_trade(trade,fill_price,fee=0):
    if trade['status']!='OPEN':return {'ok':False,'error':'trade is not open'}
    direction=1 if trade['side']=='BUY' else -1
    pnl=round((fill_price-trade['entry'])*trade['qty']*direction-fee,2)
    from core.db import client
    c=client()
    if c is None:return {'ok':False,'error':'Supabase not configured'}
    try:
        c.table('paper_trades').update({'status':'CLOSED','exit_price':fill_price,'closed_at':now(),'pnl':pnl}).eq('id',trade['id']).eq('status','OPEN').execute()
        return {'ok':True,'pnl':pnl}
    except Exception as exc:return {'ok':False,'error':str(exc)}
