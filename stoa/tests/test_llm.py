from bp import llm


def test_openrouter_gets_a_vendor_prefix() -> None:
    base = "https://openrouter.ai/api/v1"
    assert llm.wire_model("claude-haiku-5.5", base) == "anthropic/claude-haiku-5.5"
    assert llm.wire_model("gpt-6-luna", base) == "openai/gpt-6-luna"
    assert llm.wire_model("gemini-3.5-flash-lite", base) == "google/gemini-3.5-flash-lite"
    assert llm.wire_model("anthropic/claude-haiku-5.5", base) == "anthropic/claude-haiku-5.5"


def test_other_routers_keep_the_bare_name() -> None:
    assert llm.wire_model("claude-haiku-5.5", "https://router.example/v1") == "claude-haiku-5.5"


def test_cost_reads_both_usage_shapes() -> None:
    assert llm._cost_usd({"cost": 0.002}) == 0.002
    assert llm._cost_usd({"credits_charged": llm.CREDITS_PER_USD}) == 1.0
    assert llm._cost_usd({}) == 0.0


def test_cli_prompt_holds_the_system_text_the_tools_and_each_turn() -> None:
    messages = [
        {"role": "system", "content": "Answer from tools."},
        {"role": "user", "content": [{"type": "text", "text": "How many doors?"}]},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "count", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "c1", "content": '{"doors": 4}'},
    ]
    tools = [{"type": "function", "function": {"name": "count", "parameters": {"type": "object"}}}]
    system, prompt = llm.cli_prompt(messages, tools)
    assert "Answer from tools." in system
    assert '"name": "count"' in prompt
    assert "How many doors?" in prompt
    assert "[tool result for call c1]" in prompt
    assert '{"doors": 4}' in prompt
