create or replace function public.kst_signal_scoreboard() returns jsonb language sql stable security invoker set search_path=public as $$
-- Kenny's winner definition: positive same-day close OR +30% target observed
-- before -30% stop. All prices are sampled research estimates, not fills.
-- Earliest signal per contract/New York day prevents budget duplication.
with signals as (
 select distinct on(contract,(created_at at time zone 'America/New_York')::date)
 *, ((created_at at time zone 'America/New_York')::date+time '16:00') at time zone 'America/New_York' as day_close
 from public.kst_option_signals
 order by contract,(created_at at time zone 'America/New_York')::date,created_at,id
), observations as (
 select s.*,h.target_at,h.stop_at,h.peak_return,e.close_return,e.close_quote_at,
        (s.quote_at<=s.created_at and s.created_at-s.quote_at<=interval '60 seconds') as entry_time_ok
 from signals s
 left join lateral (
  select min(m.quote_at) filter(where (m.bid-s.entry_ask)/s.entry_ask>=.3) as target_at,
         min(m.quote_at) filter(where (m.bid-s.entry_ask)/s.entry_ask<=-.3) as stop_at, max(m.estimated_return) as peak_return
  from public.kst_option_marks m where m.signal_id=s.id
   and m.quote_at>s.created_at and m.quote_at<=s.day_close
   and m.observed_at>=m.quote_at and m.observed_at-m.quote_at<=interval '5 minutes'
   and m.bid>=0 and m.ask>=m.bid and m.ask>0
 ) h on true
 left join lateral (
  select m.estimated_return as close_return,m.quote_at as close_quote_at
  from public.kst_option_marks m where m.signal_id=s.id
   and m.quote_at>=greatest(s.created_at,s.day_close-interval '5 minutes')
   and m.quote_at<=s.day_close and m.observed_at>=m.quote_at
   and m.observed_at-m.quote_at<=interval '5 minutes'
   and m.bid>=0 and m.ask>=m.bid and m.ask>0
  order by m.quote_at desc limit 1
 ) e on true
), classified as (
 select *,case
 when not entry_time_ok then 'ENTRY_TIME_FLAG'
 when target_at is not null and (stop_at is null or target_at<stop_at) then 'WIN_TARGET_FIRST_OBSERVED'
 when now()<day_close then 'PENDING_CLOSE'
 when close_return>0 then 'WIN_POSITIVE_CLOSE'
 when close_return<0 then 'LOSS_AT_CLOSE'
 when close_return=0 then 'FLAT_AT_CLOSE'
 else 'UNRESOLVED_NO_CLOSE_QUOTE' end as daily_result
 from observations
)
select jsonb_build_object('generated_at',now(),'basis','SAMPLED_SIGNAL_RESEARCH',
 'definition','Positive same-day closing reference OR +30% observed before -30%; duplicate contract/day entries removed. Missing close quotes unresolved.',
 'counts',(select coalesce(jsonb_object_agg(daily_result,n),'{}'::jsonb) from (select daily_result,count(*) as n from classified group by daily_result) c),
 'major_winners',coalesce((select jsonb_agg(to_jsonb(w)) from (
 select contract,underlying,expiration,category,created_at,entry_ask,entry_bid,feed,context_label,
 daily_result,close_return,close_quote_at,peak_return,target_at,stop_at,
 risk_snapshot->'profit_lock' as profit_lock
 from classified where daily_result like 'WIN_%' and peak_return>=.5
 order by peak_return desc,created_at desc limit 20) w),'[]'::jsonb),
 'winners',coalesce((select jsonb_agg(to_jsonb(w)) from (
 select contract,underlying,expiration,category,created_at,entry_ask,feed,context_label,daily_result,close_return,close_quote_at,peak_return,target_at,stop_at,risk_snapshot->'profit_lock' as profit_lock
 from classified where daily_result like 'WIN_%' order by created_at desc limit 30) w),'[]'::jsonb),
 'losers',coalesce((select jsonb_agg(to_jsonb(w)) from (
 select contract,underlying,expiration,category,created_at,entry_ask,feed,context_label,daily_result,close_return,close_quote_at,peak_return,risk_snapshot->'profit_lock' as profit_lock
 from classified where daily_result='LOSS_AT_CLOSE' order by created_at desc limit 30) w),'[]'::jsonb)
);

$$;
revoke all on function public.kst_signal_scoreboard() from public,anon,authenticated;
grant execute on function public.kst_signal_scoreboard() to service_role;
