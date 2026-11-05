"""BYOK transport and provider-cost isolation tests. No real API calls."""
import uuid
import pytest
from kst_chat.user_provider import complete,validate_key,PROVIDERS
from kst_chat.service import ApiError,handle
from test_chat import Store,U1,C1,ENV

def test_supported_providers_are_fixed():
 assert set(PROVIDERS)=={"openai","anthropic","google"}
 for name,key in [("openai","sk-user-test-credential-12345"),
                  ("anthropic","sk-ant-user-credential-12345"),
                  ("google","AIzaThisIsAnIllustrativeTestKey")]:
  assert validate_key(name,key)==key
 with pytest.raises(ApiError):validate_key("custom", "sk-something-long-enough")

def test_missing_user_key_cannot_fallback_to_owner_key():
 db=Store()
 env={**ENV,"OPENAI_API_KEY":"sk-owner-secret-that-must-never-fund-users"}
 request={"conversation_id":C1,"request_id":str(uuid.uuid4()),"message":"What stock is strongest?"}
 def fail(*args,**kwargs):raise AssertionError("Owner-funded provider call")
 with pytest.raises(ApiError) as exc:
  handle("POST","/api/chat/message",request,U1,db,env,fail)
 assert exc.value.status==400 and db.reserves==0
 assert not db.data["kst_chat_turns"]

def test_provider_key_never_in_research_or_history():
 db=Store();key="sk-test-user-billed-credential"
 request={"conversation_id":C1,"request_id":str(uuid.uuid4()),"message":"Market outlook","ai_provider":"openai"}
 def fake(url,headers,payload,**kwargs):
  assert headers["Authorization"]=="Bearer "+key
  assert payload["store"] is False
  return {"output":[{"type":"message","content":[{"type":"output_text","text":"KST has insufficient fresh evidence"}]}]}
 response=handle("POST","/api/chat/message",request,U1,db,ENV,fake,ai_key=key)
 assert "insufficient" in response["text"]
 assert key not in str(db.data)

def test_anthropic_uses_user_key_and_site_data(monkeypatch):
 seen={}
 def fake(url,headers,payload,timeout=55):
  seen.update(url=url,headers=headers,payload=payload)
  return {"content":[{"type":"text","text":"IWM research based on KST"}]}
 monkeypatch.setattr("kst_chat.user_provider._post",fake)
 text=complete("anthropic","sk-ant-user-example-credential",
      [{"role":"user","content":"KST data reference"},{"role":"user","content":"Compare IWM"}],
      "Be factual",500)
 assert "IWM" in text and seen["headers"]["x-api-key"].startswith("sk-ant-")
 assert seen["payload"]["system"]=="Be factual"
 assert seen["payload"]["messages"][0]["content"]=="KST data reference"

def test_gemini_uses_own_key_without_leaking_in_url(monkeypatch):
 seen={}
 def fake(url,headers,payload,timeout=55):
  seen.update(url=url,headers=headers,payload=payload)
  return {"candidates":[{"content":{"parts":[{"text":"Data-driven answer"}]}}]}
 monkeypatch.setattr("kst_chat.user_provider._post",fake)
 text=complete("google","AIzaExampleCredentialNotReal",
     [{"role":"user","content":"KST market data"}],"Use citations",600)
 assert text=="Data-driven answer"
 assert "AIza" not in seen["url"]
 assert seen["headers"]["x-goog-api-key"].startswith("AIza")
 assert seen["payload"]["contents"][0]["parts"][0]["text"]=="KST market data"

def test_non_openai_image_request_rejected_before_external_call():
 with pytest.raises(ApiError) as exc:
  complete("anthropic","sk-ant-user-example-credential",
    [{"role":"user","content":[{"type":"input_text","text":"Review chart"},
       {"type":"input_image","image_url":"data:image/jpeg;base64,abc"}]}],
    "No inventions",512)
 assert exc.value.status==400

def test_paid_membership_gate_blocks_unpaid_key_owners():
 db=Store();env={**ENV,"MEMBERSHIP_ENFORCED":"true"}
 request={"conversation_id":C1,"request_id":str(uuid.uuid4()),"message":"Top contracts"}
 with pytest.raises(ApiError) as exc:
  handle("POST","/api/chat/message",request,U1,db,env,ai_key="sk-user-billed-credential")
 assert exc.value.status==403 and db.reserves==0

def test_research_endpoints_do_not_allow_byok_paywall_bypass():
 db=Store();env={**ENV,"MEMBERSHIP_ENFORCED":"true"}
 for method,path,body in [
   ("GET","/api/chat/suggestions",{}),
   ("POST","/api/chat/market-refresh",{"symbol":"NVDA"}),
   ("POST","/api/chat/ticker-search",{"query":"AAPL"}),
   ("POST","/api/chat/history-search",{"query":"IWM"})]:
  with pytest.raises(ApiError) as exc:
   handle(method,path,body,U1,db,env)
  assert exc.value.status==403
 assert db.reserves==0
