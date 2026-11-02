"""Safety tests for the Part 10 reply bot (Notebooks/Part 10 .../bot.py).

These need no network and no credentials: the bot's decision logic is a pure
function, and the polling cycle is exercised against a fake client. Each test
pins down a behavior whose failure would make a student's copy of the bot
misbehave in public.

Run from the repository root with:  python -m pytest tests/
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BOT_DIR = Path(__file__).resolve().parents[1] / "Notebooks" / "Part 10 - Real-Time Streams and Bots"
sys.path.insert(0, str(BOT_DIR))

import bot  # noqa: E402


# --- The trigger -----------------------------------------------------------

@pytest.mark.parametrize("text", ["@examplebot.bsky.social ping", "PING!", "ping?", "hey, ping me back"])
def test_replies_to_the_command(text):
    assert bot.build_reply(text, operator="@someone.bsky.social").startswith("pong!")


@pytest.mark.parametrize("text", ["shipping update", "thanks for helping", "keeping it real",
                                  "pinging the team", "lovely weather today", ""])
def test_ignores_text_that_merely_contains_ping(text):
    assert bot.build_reply(text, operator="@someone.bsky.social") is None


# --- Disclosure ------------------------------------------------------------

def test_every_reply_discloses_its_operator():
    reply = bot.build_reply("ping", operator="@operator.example")
    assert "automated account" in reply
    assert "@operator.example" in reply


def test_default_operator_is_a_placeholder_not_a_real_person(monkeypatch):
    monkeypatch.delenv("BOT_OPERATOR", raising=False)
    assert bot.bot_operator() == bot.OPERATOR_PLACEHOLDER
    assert not bot.operator_is_set()


# --- The polling cycle -----------------------------------------------------

def make_mention(n, text):
    return SimpleNamespace(
        reason="mention",
        uri=f"at://did:plc:test{n}/app.bsky.feed.post/3kmention{n}",
        cid=f"bafyreitestcid{n}",
        record=SimpleNamespace(text=text, reply=None),
    )


class FakeClient:
    """Serves fixed notifications; send_post records calls and can fail."""

    def __init__(self, mentions, fail_on_send=None):
        self.sent = []
        self.fail_on_send = fail_on_send
        notifications = SimpleNamespace(notifications=mentions)
        self.app = SimpleNamespace(bsky=SimpleNamespace(notification=SimpleNamespace(
            list_notifications=lambda params: notifications)))

    def send_post(self, text, reply_to):
        if self.fail_on_send is not None and len(self.sent) == self.fail_on_send:
            raise ConnectionError("simulated network failure")
        self.sent.append(text)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(bot.time, "sleep", lambda seconds: None)


def test_live_run_refuses_without_an_operator(monkeypatch, tmp_path):
    monkeypatch.delenv("BOT_OPERATOR", raising=False)
    client = FakeClient([make_mention(1, "ping")])
    with pytest.raises(RuntimeError, match="BOT_OPERATOR"):
        bot.run_bot_once(client, dry_run=False, answered_path=tmp_path / "answered.json")
    assert client.sent == []


def test_dry_run_sends_nothing_and_writes_nothing(monkeypatch, tmp_path):
    monkeypatch.delenv("BOT_OPERATOR", raising=False)
    path = tmp_path / "answered.json"
    client = FakeClient([make_mention(1, "ping"), make_mention(2, "ping")])
    assert bot.run_bot_once(client, dry_run=True, answered_path=path) == 2
    assert client.sent == []
    assert not path.exists()  # a rehearsal must not mark mentions as answered


def test_each_send_is_recorded_before_the_next(monkeypatch, tmp_path):
    monkeypatch.setenv("BOT_OPERATOR", "@operator.example")
    path = tmp_path / "answered.json"
    mentions = [make_mention(1, "ping"), make_mention(2, "ping")]
    client = FakeClient(mentions, fail_on_send=1)  # first send works, second fails
    with pytest.raises(ConnectionError):
        bot.run_bot_once(client, dry_run=False, answered_path=path)
    # The reply that went out is on disk, so the next cycle won't repeat it
    assert json.loads(path.read_text()) == [mentions[0].uri]


def test_never_answers_the_same_mention_twice(monkeypatch, tmp_path):
    monkeypatch.setenv("BOT_OPERATOR", "@operator.example")
    path = tmp_path / "answered.json"
    mentions = [make_mention(1, "ping")]
    assert bot.run_bot_once(FakeClient(mentions), dry_run=False, answered_path=path) == 1
    second = FakeClient(mentions)
    assert bot.run_bot_once(second, dry_run=False, answered_path=path) == 0
    assert second.sent == []


def test_reply_cap_per_cycle(monkeypatch, tmp_path):
    monkeypatch.setenv("BOT_OPERATOR", "@operator.example")
    mentions = [make_mention(n, "ping") for n in range(bot.MAX_REPLIES_PER_RUN + 3)]
    client = FakeClient(mentions)
    sent = bot.run_bot_once(client, dry_run=False, answered_path=tmp_path / "a.json")
    assert sent == bot.MAX_REPLIES_PER_RUN == len(client.sent)
