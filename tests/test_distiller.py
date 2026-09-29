from agents.distiller import distil, should_distil
from agents.knowledge_writer import write_knowledge
from tests.fakes import FakeAnthropic, FakeSupabase

OLD_BRAIN = "## Interpreting user context\n- Old heuristic. *(seen in 2 queries)*"


def _db(last_distilled=None, learnings=None, brain=OLD_BRAIN, query_count=10):
    return FakeSupabase({
        "agent_config": [{
            "id": 1,
            "distilled_brain": brain,
            "last_distilled": last_distilled,
            "query_count": query_count,
        }],
        "learnings": learnings if learnings is not None else [
            {"category": "token_pattern", "outcome_summary": "Old learning.", "created_at": "2026-09-01T00:00:00+00:00"},
            {"category": "context_methodology", "outcome_summary": "Nursery via kindergarten tag.", "created_at": "2026-09-10T00:00:00+00:00"},
            {"category": "synthesiser_insight", "outcome_summary": "KT1 tops safety.", "created_at": "2026-09-11T00:00:00+00:00"},
        ],
        "distillation_history": [],
    })


def test_happy_path_rewrites_brain_and_records_history():
    db = _db(last_distilled="2026-09-05T00:00:00+00:00")
    client = FakeAnthropic(payload={
        "distilled_brain": "## Interpreting user context\n- New heuristic. *(seen in 3 queries)*",
        "change_summary": "Refined: nursery handling.",
    })

    result = distil(supabase=db, client=client)

    assert result["status"] == "ok"
    assert result["learnings_consumed"] == 2
    config = db.tables["agent_config"][0]
    assert "New heuristic" in config["distilled_brain"]
    assert config["last_distilled"] == "2026-09-11T00:00:00+00:00"
    history = db.tables["distillation_history"]
    assert len(history) == 1
    assert history[0]["previous_brain"] == OLD_BRAIN
    assert history[0]["change_summary"] == "Refined: nursery handling."
    assert history[0]["query_count"] == 10
    sent = client.calls[0]["messages"][0]["content"]
    assert "Old heuristic" in sent
    assert "KT1 tops safety." in sent
    assert "Old learning." not in sent


def test_consumes_all_learnings_when_never_distilled():
    db = _db(last_distilled=None, brain=None)
    client = FakeAnthropic(payload={"distilled_brain": "## District insights\n- X.", "change_summary": "Added: X."})

    result = distil(supabase=db, client=client)

    assert result["learnings_consumed"] == 3
    assert db.tables["distillation_history"][0]["previous_brain"] is None


def test_bad_json_keeps_old_brain():
    db = _db()
    result = distil(supabase=db, client=FakeAnthropic(text="not json at all {"))

    assert result["status"] == "failed"
    assert db.tables["agent_config"][0]["distilled_brain"] == OLD_BRAIN
    assert db.tables["distillation_history"] == []


def test_empty_brain_keeps_old_brain():
    db = _db()
    result = distil(supabase=db, client=FakeAnthropic(payload={"distilled_brain": "  ", "change_summary": "x"}))

    assert result["status"] == "failed"
    assert db.tables["agent_config"][0]["distilled_brain"] == OLD_BRAIN


def test_api_error_keeps_old_brain_and_does_not_raise():
    db = _db()
    result = distil(supabase=db, client=FakeAnthropic(raises=RuntimeError("boom")))

    assert result["status"] == "failed"
    assert db.tables["agent_config"][0]["distilled_brain"] == OLD_BRAIN


def test_truncated_by_max_tokens_keeps_old_brain():
    db = _db()
    client = FakeAnthropic(payload={"distilled_brain": "x", "change_summary": "y"})
    real = client._create
    client.messages.create = lambda **kw: setattr(r := real(**kw), "stop_reason", "max_tokens") or r

    result = distil(supabase=db, client=client)

    assert result["status"] == "failed"
    assert db.tables["agent_config"][0]["distilled_brain"] == OLD_BRAIN


def test_no_new_learnings_skips_without_calling_claude():
    db = _db(last_distilled="2026-09-30T00:00:00+00:00")
    client = FakeAnthropic(payload={})

    result = distil(supabase=db, client=client)

    assert result["status"] == "skipped"
    assert client.calls == []


def test_should_distil_threshold():
    assert should_distil(10, every_n=10)
    assert should_distil(20, every_n=10)
    assert not should_distil(9, every_n=10)
    assert not should_distil(0, every_n=10)
    assert not should_distil(10, every_n=0)


def test_knowledge_writer_flags_distillation_at_threshold(monkeypatch):
    monkeypatch.setattr("agents.distiller.DISTILL_EVERY_N", 10)
    db = FakeSupabase({"agent_config": [{"id": 1, "query_count": 9}], "learnings": []})

    result = write_knowledge([{"category": "token_pattern", "content": "A learning."}], supabase=db)

    assert result["query_count"] == 10
    assert result["distillation_triggered"] is True
    assert len(db.tables["learnings"]) == 1


def test_knowledge_writer_does_not_flag_below_threshold(monkeypatch):
    monkeypatch.setattr("agents.distiller.DISTILL_EVERY_N", 10)
    db = FakeSupabase({"agent_config": [{"id": 1, "query_count": 3}], "learnings": []})

    result = write_knowledge([], supabase=db)

    assert result["query_count"] == 4
    assert result["distillation_triggered"] is False
