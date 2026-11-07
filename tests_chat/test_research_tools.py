from datetime import datetime, timezone
import pytest
from kst_chat.research_tools import run_research_tool, ResearchToolError

NOW = datetime(2026, 11, 7, tzinfo=timezone.utc)

class FakeStore:
    def rows(self, table, **kwargs):
        if table == "kst_option_signals":
            return [{"created_at":NOW.isoformat(), "underlying":"AAPL",
                "contract":"AAPL260911C00150000", "option_type":"call",
                "category":"Swings", "entry_ask":1.2, "quote_at":NOW.isoformat(),
                "feed":"indicative", "score":65, "context_label":"UP_SETUP_ALIGNED"}]
        if table == "ultimate_signals":
            return [{"created_at":NOW.isoformat(), "symbol":"AAPL", "side":"bullish",
                "entry":150, "stop":148, "target":155, "details":{}}]
        raise AssertionError(table)

def test_snapshot_is_explicitly_not_fresh_scan():
    result=run_research_tool(FakeStore(),"research_snapshot",
        {"symbol":"AAPL","horizon":"swings","direction":"bullish","max_contract_cost":150},now=NOW)
    assert result["fresh_scan_triggered"] is False
    assert result["broker_orders_enabled"] is False
    assert len(result["data"]["contract_candidates"])==1

def test_budget_and_direction_filter():
    assert not run_research_tool(FakeStore(),"research_snapshot",
        {"symbol":"AAPL","max_contract_cost":100},now=NOW)["data"]["contract_candidates"]
    assert not run_research_tool(FakeStore(),"research_snapshot",
        {"symbol":"AAPL","direction":"bearish"},now=NOW)["data"]["contract_candidates"]

@pytest.mark.parametrize("tool,args",[
    ("place_order",{}),("research_snapshot",{"user_id":"other"}),
    ("research_snapshot",{"symbol":"AAPL;DROP"}),
    ("research_snapshot",{"max_contract_cost":-1}),
])
def test_rejects_unsafe_or_invalid_requests(tool,args):
    with pytest.raises(ResearchToolError):
        run_research_tool(FakeStore(),tool,args,now=NOW)
