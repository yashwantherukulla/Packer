from packer.engine.common.progress import (
    ProgressCallback,
    ProgressEvent,
    RecordingProgress,
    null_progress,
)


def test_null_progress_is_a_noop():
    null_progress(step="x", pct=0.5)  # must not raise


def test_recording_progress_captures_events():
    rec = RecordingProgress()
    rec(step="train", pct=0.25, detail="epoch 1")
    rec(step="train", pct=1.0)
    assert rec.events == [
        ProgressEvent(step="train", pct=0.25, detail="epoch 1"),
        ProgressEvent(step="train", pct=1.0, detail=None),
    ]


def test_recording_progress_satisfies_protocol():
    cb: ProgressCallback = RecordingProgress()
    cb(step="s", pct=0.0)
