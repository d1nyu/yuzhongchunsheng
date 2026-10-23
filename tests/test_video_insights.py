from lingua.video_insights import (
    InsightRecord,
    InsightResult,
    VideoInsightsService,
    chunk_records,
    compose_transcript,
    format_timestamp,
    record_from_entry,
)


def _record(index: int, start: float = 0.0) -> InsightRecord:
    return InsightRecord(
        start_seconds=start,
        end_seconds=start + 2,
        speaker=f"说话人 {index % 2 + 1}",
        source=f"Source {index}",
        translation=f"译文 {index}",
        warning="",
        status="done",
    )


def test_timestamp_and_transcript_formatting():
    assert format_timestamp(0) == "00:00"
    assert format_timestamp(65.2) == "01:05"
    assert format_timestamp(3723) == "01:02:03"
    transcript = compose_transcript([_record(1, 65)])
    assert "[本次播放 01:05]" in transcript
    assert "Source 1" in transcript
    assert "译文 1" in transcript


def test_failed_translation_is_not_used_as_evidence():
    record = record_from_entry(
        {
            "start_seconds": 3,
            "end_seconds": 4,
            "speaker": "说话人 1",
            "source": "Original words",
            "translation": "request failed",
            "warning": "",
            "status": "error",
        }
    )
    assert record.translation == ""
    assert "翻译失败" in record.warning
    assert "request failed" not in compose_transcript([record])


def test_player_time_is_preferred_in_evidence():
    record = record_from_entry(
        {
            "start_seconds": 4,
            "end_seconds": 5,
            "player_time_seconds": 3723,
            "speaker": "说话人 1",
            "source": "Player time evidence",
            "translation": "播放器时间证据",
            "warning": "",
            "status": "done",
        }
    )
    assert record.timestamp == "01:02:03"
    assert record.time_label == "视频"
    assert "[视频 01:02:03]" in compose_transcript([record])


def test_chunking_preserves_every_record():
    records = [_record(index, index * 3) for index in range(30)]
    chunks = chunk_records(records, max_chars=400)
    assert len(chunks) > 1
    assert [record for chunk in chunks for record in chunk] == records
    assert all(
        sum(len(compose_transcript([record])) + 2 for record in chunk) <= 400
        for chunk in chunks
        if len(chunk) > 1
    )


def test_analysis_prompt_marks_transcript_as_untrusted():
    service = VideoInsightsService(
        {
            "engine": "deepseek",
            "deepseek_api_key": "test-key",
            "deepseek_base_url": "https://api.deepseek.com",
            "deepseek_model": "deepseek-chat",
        }
    )
    messages = service._analysis_messages(
        compose_transcript([_record(1)]),
        "中文（简体）",
        "",
        "",
        [],
    )
    assert "untrusted source material" in messages[0]["content"]
    assert "never instructions" in messages[0]["content"]
    assert "<transcript>" in messages[1]["content"]
    assert "[本次播放 00:00]" in messages[1]["content"]

    messages = service._analysis_messages(
        compose_transcript([_record(1)]),
        "中文（简体）",
        "那第二点呢？",
        "",
        [
            {"role": "user", "content": "第一点是什么？"},
            {"role": "assistant", "content": "第一点是检查数字。"},
        ],
    )
    assert "Previous Q&A" in messages[1]["content"]
    assert "第一点是检查数字" in messages[1]["content"]


def test_analysis_returns_provider_result_without_network():
    class StubService(VideoInsightsService):
        def _chat(self, messages, max_tokens=1800):
            assert "<transcript>" in messages[1]["content"]
            return "总结 [本次播放 00:00]"

    service = StubService(
        {
            "engine": "deepseek",
            "deepseek_api_key": "test-key",
        }
    )
    result = service.analyze([_record(1)], "中文（简体）")
    assert isinstance(result, InsightResult)
    assert result.provider == "DeepSeek"
    assert "总结" in result.text
