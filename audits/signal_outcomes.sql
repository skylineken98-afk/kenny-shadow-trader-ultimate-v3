-- Read-only audit: earliest signal per contract / New York date.
-- Counts are observations, not fills; same contract on different days remains correlated.
with unique_signals as (
 select distinct on(contract,(created_at at time zone 'America/New_York')::date) *
 from public.kst_option_signals
 order by contract,(created_at at time zone 'America/New_York')::date,created_at,id
), evidence as (
 select s.*, h.target_at,h.stop_at,h.sample_count,h.largest_gap_seconds,
        s.created_at-s.quote_at as entry_age
 from unique_signals s
 left join lateral (
  select min(quote_at) filter(where estimated_return>=0.5) as target_at,
         min(quote_at) filter(where estimated_return<=-0.3) as stop_at,
         count(*) as sample_count,max(gap_seconds) as largest_gap_seconds
  from (
   select m.*,extract(epoch from m.quote_at-lag(m.quote_at,1,s.quote_at) over(order by m.quote_at)) as gap_seconds
   from public.kst_option_marks m
   where m.signal_id=s.id and m.quote_at>s.created_at and m.quote_at<=s.due_at
     and m.observed_at>=m.quote_at and m.observed_at-m.quote_at<=interval '5 minutes'
     and m.bid>=0 and m.ask>=m.bid and m.ask>0
  ) valid_marks
 ) h on true
)
select category,coalesce(context_label,'UNLABELED') as context,feed,
 count(*) as contract_days,
 count(*) filter(where state='CLOSED') as horizon_closed,
 count(*) filter(where state='CLOSED' and outcome_return>0) as horizon_positive,
 count(*) filter(where target_at<stop_at or (target_at is not null and stop_at is null)) as target_first_observed,
 count(*) filter(where stop_at<target_at or (stop_at is not null and target_at is null)) as stop_first_observed,
 count(*) filter(where target_at is null and stop_at is null) as neither_observed,
 count(*) filter(where sample_count=0) as no_valid_path_samples,
 count(*) filter(where largest_gap_seconds>300) as paths_with_over_5m_gap,
 count(*) filter(where entry_age>interval '60 seconds' or entry_age<interval '0 seconds') as entry_time_flags
from evidence group by category,context_label,feed order by contract_days desc;
