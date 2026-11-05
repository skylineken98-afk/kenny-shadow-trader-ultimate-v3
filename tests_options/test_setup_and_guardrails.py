import re,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
def test_every_env_var_in_code_is_in_env_example():
    example=(ROOT/'.env.example').read_text()
    used=set()
    for pkg in ('kst_options','kst_chat'):
        for f in (ROOT/pkg).glob('*.py'):
            used|=set(re.findall(r"(?:getenv|environ\.get|env\.get|environ)\(?\[?['\"]([A-Z][A-Z0-9_]{3,})['\"]",f.read_text()))
    missing=sorted(v for v in used if v+'=' not in example)
    assert not missing,missing
def test_schema_guardrails_present_and_ordered():
    s=(ROOT/'kst_options/schema.sql').read_text()
    assert s.index('add column if not exists peak_bid')<s.index('function public.kst_agent_mark')
    for text in ('Daily research loss limit','15-minute cooldown after a losing','TRAILING_GIVEBACK'):assert text in s
    assert "OBSERVED_TARGET" not in s   # runners are not capped at +50%
    assert 'OBSERVED_STOP' in s         # loss stop remains
def test_no_stray_or_dev_files_in_runtime_requirements():
    assert 'pytest' not in (ROOT/'requirements.txt').read_text()
    assert not (ROOT/'.env - Copy.example').exists()
