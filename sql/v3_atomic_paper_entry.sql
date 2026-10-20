-- V3 DEVELOPMENT MIGRATION. Review and execute manually in Supabase SQL Editor.
-- Requires previously created v3_paper_accounts, v3_paper_orders,
-- paper_trades, paper_fills, ultimate_signals and v3_paper_audit.
-- Paper only: no brokerage interaction. Uses a row lock and a single SQL transaction.
-- PnL settlement/exit transactions are NOT included; keep automation disabled.
BEGIN;
CREATE OR REPLACE FUNCTION public.v3_record_paper_entry(
    p_agent text, p_signal uuid, p_occ text, p_asset text,
    p_direction text, p_ask numeric, p_stop numeric, p_target numeric,
    p_quote_time timestamptz, p_max_risk numeric,
    p_max_exposure numeric DEFAULT 0.25
) RETURNS uuid LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
DECLARE
    a public.v3_paper_accounts%ROWTYPE;
    s public.ultimate_signals%ROWTYPE;
    existing uuid;
    trade_id uuid;
    entry_cost numeric;
    risk_amount numeric;
BEGIN
    IF p_agent IS NULL OR p_occ !~ '^[A-Z0-9]{1,6} +[0-9]{6}[CP][0-9]{8}$'
       OR p_asset NOT IN ('call','put') OR p_direction NOT IN ('BULLISH','BEARISH')
       OR (p_asset = 'call' AND p_direction <> 'BULLISH')
       OR (p_asset = 'put' AND p_direction <> 'BEARISH')
       OR p_ask <= 0 OR p_stop <= 0 OR p_stop >= p_ask OR p_target <= p_ask
       OR p_max_risk <= 0 OR p_max_risk > 0.025 OR p_max_exposure <= 0 OR p_max_exposure > 0.25
       OR p_quote_time IS NULL OR p_quote_time > now()
       OR p_quote_time < now() - interval '60 seconds'
    THEN RAISE EXCEPTION 'Invalid paper entry parameters'; END IF;
    SELECT * INTO a FROM public.v3_paper_accounts WHERE agent=p_agent FOR UPDATE;
    IF NOT FOUND OR a.killed OR a.equity <= 0 OR a.day_start_equity <= 0
       OR a.equity <= a.day_start_equity * 0.95 THEN
       RAISE EXCEPTION 'Paper agent stopped or daily risk limit reached';
    END IF;
    SELECT * INTO s FROM public.ultimate_signals WHERE id=p_signal;
    IF NOT FOUND OR s.status <> 'SETUP' OR s.side <> p_direction THEN
       RAISE EXCEPTION 'Ineligible source signal';
    END IF;
    SELECT id INTO existing FROM public.v3_paper_orders
      WHERE agent=p_agent AND source_signal_id=p_signal::text AND symbol=p_occ;
    IF FOUND THEN RETURN existing; END IF;
    entry_cost := p_ask * 100;
    risk_amount := (p_ask - p_stop) * 100;
    IF entry_cost + a.open_cost > a.equity * p_max_exposure
       OR risk_amount > a.equity * p_max_risk THEN
       RAISE EXCEPTION 'Paper risk cap exceeded';
    END IF;
    INSERT INTO public.v3_paper_orders
      (agent, source_signal_id, symbol, asset, direction, state, detail, simulation_only)
    VALUES (p_agent, p_signal::text, p_occ, p_asset, p_direction,
      'SIMULATED_OPEN', jsonb_build_object('fill_price', p_ask::text, 'stop', p_stop::text,
      'target', p_target::text, 'cost', entry_cost::text, 'quantity', 1,
      'multiplier', 100, 'quote_timestamp', p_quote_time, 'simulation_only', true), true)
    RETURNING id INTO existing;
    INSERT INTO public.paper_trades
      (signal_id, agent_profile, account_id, symbol, asset_class, instrument,
       direction, quantity, status, entry_price, opened_at, metadata)
    VALUES (p_signal, p_agent, p_agent, s.symbol, p_asset, p_occ,
       'LONG', 1, 'OPEN', p_ask, now(),
       jsonb_build_object('paper_order_id',existing,'quote_timestamp',p_quote_time,
                          'simulation_only',true)) RETURNING id INTO trade_id;
    INSERT INTO public.paper_fills
      (trade_id, action, quantity, fill_price, filled_at, source, metadata)
    VALUES (trade_id, 'BUY', 1, p_ask, now(), 'assumed_ask',
      jsonb_build_object('simulation_only',true,'multiplier',100));
    UPDATE public.v3_paper_accounts SET open_cost = open_cost + entry_cost WHERE agent=p_agent;
    INSERT INTO public.v3_paper_audit(agent,event,detail)
    VALUES (p_agent, 'PAPER_ENTRY_RECORDED', jsonb_build_object('order_id',existing,'trade_id',trade_id));
    RETURN existing;
END;
$$;
REVOKE ALL ON FUNCTION public.v3_record_paper_entry(text,uuid,text,text,text,numeric,numeric,numeric,timestamptz,numeric,numeric) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.v3_record_paper_entry(text,uuid,text,text,text,numeric,numeric,numeric,timestamptz,numeric,numeric) FROM anon, authenticated;
GRANT EXECUTE ON FUNCTION public.v3_record_paper_entry(text,uuid,text,text,text,numeric,numeric,numeric,timestamptz,numeric,numeric) TO service_role;
COMMIT;
