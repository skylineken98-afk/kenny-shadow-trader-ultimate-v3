-- Kenny's winner definition: positive same-day close OR +30% target observed
-- before -30% stop. All prices are sampled research estimates, not fills.
-- Earliest signal per contract/New York day prevents budget duplication.
with signals as (
 select distinct on(contract,(created_at at time zone 'America/New_York')::date)
 *, ((created_at at time zone 'America/New_York')::date+time '16:00') at time zone 'America/New_York' as day_close
 from public.kst_option_signals
 order by contract,(created_at at time zone 'America/New_York')::date,created_at,id
), observations as (
 select s.*,h.target_at,h.stop_at,e.close_return,e.close_quote_at,
        (s.quote_at<=s.created_at and s.created_at-s.quote_at<=interval '60 seconds') as entry_time_ok
 from signals s
 left join lateral (
  select min(m.quote_at) filter(where (m.bid-s.entry_ask)/s.entry_ask>=.3) as target_at,
         min(m.quote_at) filter(where (m.bid-s.entry_ask)/s.entry_ask<=-.3) as stop_at
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
select (created_at at time zone 'America/New_York')::date as signal_day,
 category,context_label,feed,daily_result,count(*) as contract_days
from classified group by signal_day,category,context_label,feed,daily_result
order by signal_day,category,context_label,daily_result;
