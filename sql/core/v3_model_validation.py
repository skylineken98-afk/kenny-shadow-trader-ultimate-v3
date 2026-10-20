"""Time-ordered split, descriptive model validation only; no autonomous self-promotion."""
from datetime import datetime
from .research_backtest import evaluate

def time_split(rows,train_fraction=.7):
 if not 0.5<=train_fraction<=0.9:raise ValueError('Invalid fraction')
 seq=sorted(rows,key=lambda r:r['decision_time'])
 if len(seq)<20:return {'status':'INSUFFICIENT_SAMPLES','train':[],'test':[]}
 cutoff=int(len(seq)*train_fraction)
 return {'status':'SPLIT','train':seq[:cutoff],'test':seq[cutoff:]}

def validate(champion,challenger):
 a=time_split(champion);b=time_split(challenger)
 if a['status']!='SPLIT' or b['status']!='SPLIT':return {'status':'INSUFFICIENT_SAMPLES','automatic_promotion':False}
 result={'status':'EVALUATED','champion_test':evaluate(a['test']),
         'challenger_test':evaluate(b['test']),'automatic_promotion':False,
         'warning':'Chronological split is not enough alone: inspect instrument overlaps, costs, leakage and regimes.'}
 return result
