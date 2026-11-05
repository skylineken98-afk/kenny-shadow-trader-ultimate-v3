"""KST user-funded AI adapter.

Every request requires an API key explicitly supplied for this request by the
authenticated user's client. No site-owned key, fallback, stored key or
caller-specified URL is accepted. KST never places broker orders.
"""
import json,re
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

PROVIDERS={
    "openai":("gpt-4.1-mini","https://api.openai.com/v1/responses"),
    "anthropic":("claude-haiku-5-5","https://api.anthropic.com/v1/messages"),
    "google":("gemini-2.5-flash","https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"),
}
# Fixed allowlist prevents attacker-chosen costly models or arbitrary endpoints.
def provider_config(provider):
    if provider not in PROVIDERS:raise ValueError("Select OpenAI, Anthropic, or Google")
    return PROVIDERS[provider]

def validate_key(provider,key):
    from .service import ApiError
    if provider not in PROVIDERS:raise ApiError(400,"Unsupported AI provider")
    if not isinstance(key,str) or not 16<=len(key)<=512 or re.search(r"[^\x21-\x7e]",key):
        raise ApiError(400,"Connect a valid API key for your selected AI provider")
    if provider=="openai" and not key.startswith("sk-"):
        raise ApiError(400,"OpenAI API keys must be supplied from an API project")
    if provider=="anthropic" and not key.startswith("sk-ant-"):
        raise ApiError(400,"Use an Anthropic API key")
    if provider=="google" and not key.startswith("AIza"):
        raise ApiError(400,"Use a Google Gemini API key")
    return key

def _text(part):
    if isinstance(part,str):return part
    if isinstance(part,list):
        return "\n".join(p.get("text","") for p in part if isinstance(p,dict) and p.get("type")=="input_text")
    return ""

def _openai_input(inputs):
    return inputs

def _messages(inputs):
    # Other providers receive exactly the same bounded, untrusted KST context.
    out=[]
    for item in inputs:
        role=item.get("role")
        if role not in ("user","assistant"):continue
        body=_text(item.get("content"))
        if body:out.append({"role":role,"content":body})
    return out

def _google_messages(inputs):
    return [{"role":"model" if x["role"]=="assistant" else "user",
             "parts":[{"text":x["content"]}]} for x in _messages(inputs)]

def _post(url,headers,payload,timeout=55):
    from .service import ApiError
    request=Request(url,data=json.dumps(payload).encode(),headers={**headers,"Content-Type":"application/json"},method="POST")
    try:
        with urlopen(request,timeout=timeout) as r:return json.load(r)
    except HTTPError as exc:
        if exc.code in (401,403):raise ApiError(401,"Your AI provider rejected your key or permissions") from None
        if exc.code in (402,429):raise ApiError(429,"Your AI provider reports insufficient credits or a rate limit") from None
        if exc.code==400:raise ApiError(400,"Your AI provider rejected this model or request") from None
        raise ApiError(502,"Your AI provider request failed") from None
    except (TimeoutError,URLError):
        raise ApiError(502,"The selected AI provider is unavailable") from None

def complete(provider,key,inputs,instructions,max_tokens,emit=None,openai_http=None):
    from .service import ApiError
    provider_config(provider)
    key=validate_key(provider,key)
    max_tokens=min(2000,max(256,int(max_tokens)))
    if provider!="openai" and any(isinstance(i.get("content"),list) for i in inputs):
        raise ApiError(400,"Chart images currently require the OpenAI API connection")
    if provider=="openai":
        from .logic import response_text
        url=PROVIDERS["openai"][1]
        data={"model":PROVIDERS["openai"][0],"instructions":instructions,
              "input":_openai_input(inputs),"store":False,"max_output_tokens":max_tokens}
        if emit is not None:
            from .streaming import request as stream
            resp=stream(url,{"Authorization":"Bearer "+key},data,emit,timeout=55)
        else:
            resp=(openai_http or _post)(url,{"Authorization":"Bearer "+key},data,timeout=55)
        return response_text(resp)
    if provider=="anthropic":
        data={"model":PROVIDERS["anthropic"][0],"max_tokens":max_tokens,
              "system":instructions,"messages":_messages(inputs)}
        resp=_post(PROVIDERS["anthropic"][1],
                   {"x-api-key":key,"anthropic-version":"2023-06-01"},data)
        result="\n".join(c.get("text","") for c in resp.get("content",[]) if c.get("type")=="text").strip()
    else:
        # Static Google host and model; never put an API key in a URL or query.
        data={"systemInstruction":{"parts":[{"text":instructions}]},
              "contents":_google_messages(inputs),
              "generationConfig":{"maxOutputTokens":max_tokens}}
        resp=_post(PROVIDERS["google"][1],{"x-goog-api-key":key},data)
        result="\n".join(p.get("text","") for c in resp.get("candidates",[])
                         for p in c.get("content",{}).get("parts",[]) if isinstance(p,dict)).strip()
    if not result:raise ApiError(502,"The selected AI returned no text; check your account and request")
    result=result[:14000]
    # Non-OpenAI responses are currently one final delta rather than token-streamed.
    if emit is not None:emit({"type":"delta","text":result})
    return result
