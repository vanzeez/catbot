import pytest

from data.to_laya_format import convert_row

ROWS = [
    {
        "id": "a",
        "lang": "en",
        "question_id": "risk_tier",
        "label": "T2",
        "split": "train",
        "state": 'Request: delete notes\nAction: run_command {"command": "rm notes.txt"}',
    },
    {
        "id": "b",
        "lang": "hi",
        "question_id": "confirm_reply",
        "label": "A",
        "split": "test",
        "state": "Question: Kya main delete karun?\nReply: हाँ",
    },
    {
        "id": "c",
        "lang": "en",
        "question_id": "verify_call",
        "label": "wrong_tool",
        "split": "train",
        "state": "Request: lower the volume\nAction: lock_screen {}",
    },
]


def test_convert_three_rows():
    out = [convert_row(r) for r in ROWS]
    assert out[0]["expected"] == {"risk_tier": "T2"}
    assert set(out[0]["questions"]["risk_tier"]["criteria"]) == {"T0", "T1", "T2", "T3"}
    assert out[1]["questions"]["confirm_reply"]["type"] == "choice"
    assert out[2]["state"].startswith("Request: lower the volume")


def test_bad_label_rejected():
    with pytest.raises(ValueError):
        convert_row({**ROWS[0], "label": "T9"})


def test_items_from_rows_accepts_format():
    train = pytest.importorskip("laya.train")
    tf = pytest.importorskip("transformers")
    import glob
    import os

    hits = glob.glob(
        os.path.expanduser(
            "~/.cache/huggingface/hub/models--convaiinnovations--laya/snapshots/*/tokenizer"
        )
    )
    if not hits:
        pytest.skip("laya checkpoint not cached")
    path = os.path.dirname(hits[0])
    tok = tf.AutoTokenizer.from_pretrained(os.path.join(path, "tokenizer"))
    items, skipped = train.items_from_rows(tok, [convert_row(r) for r in ROWS], 512, 192)
    assert len(items) == 3 and not skipped
