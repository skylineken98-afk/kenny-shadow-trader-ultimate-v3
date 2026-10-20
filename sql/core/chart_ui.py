"""Read-only trading charts. Overlay levels relate to the UNDERLYING, not option-premium levels."""
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from core.market import history,levels

def make_chart(symbol,mode='Swings',plan=None):
    m={'0DTE':('5d','5m',160),'Swings':('6mo','1d',140),'LEAPS':('2y','1wk',110),
       'Stocks':('6mo','1d',140),'Crypto':('30d','1h',180),'Forex':('60d','1h',180),
       'Futures':('30d','1h',180)}
    period,interval,bars=m.get(mode,m['Swings'])
    df=history(symbol,period,interval)
    if df.empty or len(df)<30:return None,None
    df=df.tail(bars)
    fig=make_subplots(rows=2,cols=1,shared_xaxes=True,vertical_spacing=.035,row_heights=[.78,.22])
    fig.add_trace(go.Candlestick(x=df.index,open=df['Open'],high=df['High'],low=df['Low'],close=df['Close'],name=symbol,
        increasing_line_color='#28cba0',decreasing_line_color='#f16b86'),row=1,col=1)
    for n,color in [(20,'#68b8ff'),(50,'#ad86ff'),(200,'#efbe70')]:
        if len(df)>=n:
            ema=df.Close.astype(float).ewm(span=n,adjust=False).mean()
            fig.add_trace(go.Scatter(x=df.index,y=ema,name=f'EMA {n}',line=dict(color=color,width=1.3)),row=1,col=1)
    if mode=='0DTE' and 'Volume' in df:
        typical=(df.High.astype(float)+df.Low.astype(float)+df.Close.astype(float))/3
        vol=df.Volume.astype(float)
        idx=pd.to_datetime(df.index)
        groups=idx.date
        numerator=(typical*vol).groupby(groups).cumsum()
        denominator=vol.groupby(groups).cumsum().replace(0,float('nan'))
        fig.add_trace(go.Scatter(x=df.index,y=numerator/denominator,name='Session VWAP',line=dict(color='#f1e37b',width=1.5)),row=1,col=1)
    z=levels(df)
    if z:
        for name,val,color in [('Support',z['support'],'#30caa8'),('Resistance',z['resistance'],'#f4a365')]:
            fig.add_hline(y=val,line_dash='dash',line_color=color,line_width=1.2,
                          annotation_text=f'{name} {val:.2f}',row=1,col=1)
    # These are underlying theoretical levels from strategy rules, NOT contract prices.
    if plan:
        for name,key,color in [('Underlying entry','entry','#60c5fa'),('Underlying stop','stop','#f36978'),('Underlying target','target','#a9e476')]:
            val=plan.get(key)
            if val is not None:
                fig.add_hline(y=float(val),line_color=color,line_dash='dot',annotation_text=f'{name} {float(val):.2f}',row=1,col=1)
    fig.add_trace(go.Bar(x=df.index,y=df['Volume'],name='Volume',marker_color='#54719c',opacity=.6),row=2,col=1)
    fig.update_layout(template='plotly_dark',height=475,paper_bgcolor='#0b1224',plot_bgcolor='#0b1224',
          margin=dict(l=10,r=10,t=35,b=10),legend=dict(orientation='h',y=1.07,x=0),
          xaxis_rangeslider_visible=False,title=f'{symbol} · {interval} underlying candles · {str(df.index[-1])[:16]}')
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor='#202c47')
    return fig,z
