from packer.engine.extract.model import Extraction
from packer.workers.io import load_extraction, persist_extraction


class _Store:
    def __init__(self) -> None:
        self._blobs: dict[str, bytes] = {}

    def put_blob(self, key: str, data: bytes) -> str:
        self._blobs[key] = data
        return key

    def open_blob(self, key: str):
        from io import BytesIO

        return BytesIO(self._blobs[key])


def test_persist_and_load_round_trip_extraction():
    store = _Store()
    original = Extraction(
        files={"a.py": b"print(1)\n", "README.md": b"hello\n"},
        confidence=1.0,
        confidence_class="exact",
        notes=("byte-exact",),
    )

    extraction_id = persist_extraction(store, "job-1", original)
    restored = load_extraction(store, extraction_id)

    assert extraction_id == "job-1"
    assert restored == original


def test_load_accepts_prefixed_extraction_id():
    store = _Store()
    original = Extraction(files={"a.py": b"x=1\n"}, confidence=0.25, confidence_class="blind")
    persist_extraction(store, "job-2", original)

    restored = load_extraction(store, "extraction:job-2")

    assert restored == original
