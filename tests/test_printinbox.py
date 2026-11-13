"""Prints sent to the Rosetta Plotter printer arrive as drawings."""
import os

from rosetta.app.printinbox import RECENT_S, PrintInbox, is_finished_pdf

PDF = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
NOW = 1_800_000_000.0


class Rig:
    def __init__(self, tmp_path):
        self.source = tmp_path / "spool" / "print.pdf"
        self.source.parent.mkdir()
        self.copies = tmp_path / "copies"
        self.arrived: list[list[str]] = []
        self.now = NOW
        self.inbox = PrintInbox(self.source, self.copies, self.arrived.append, clock=lambda: self.now)

    def print(self, data: bytes = PDF, age: float = 0.0) -> None:
        self.source.write_bytes(data)
        stamp = self.now - age
        os.utime(self.source, (stamp, stamp))


def test_nothing_printed_nothing_arrives(tmp_path):
    rig = Rig(tmp_path)
    assert rig.inbox.check() is None and rig.arrived == []


def test_a_print_arrives_once_it_has_stopped_changing(tmp_path):
    rig = Rig(tmp_path)
    rig.print()
    assert rig.inbox.check() is None  # seen once: it may still be growing
    copy = rig.inbox.check()
    assert copy is not None and copy.read_bytes() == PDF
    assert rig.arrived == [[str(copy)]]
    assert copy.parent == rig.copies and copy.name.startswith("Print ")
    assert rig.source.exists()  # the spooler's file is left alone
    assert rig.inbox.check() is None and len(rig.arrived) == 1  # the same print isn't taken twice


def test_a_half_written_print_waits(tmp_path):
    rig = Rig(tmp_path)
    rig.print(PDF[:20])
    assert rig.inbox.check() is None and rig.inbox.check() is None
    rig.now += 2
    rig.print(PDF)
    assert rig.inbox.check() is None
    assert rig.inbox.check() is not None


def test_each_new_print_arrives(tmp_path):
    rig = Rig(tmp_path)
    rig.print()
    rig.inbox.check()
    first = rig.inbox.check()
    rig.now += 5
    rig.print(PDF + b"\n")
    rig.inbox.check()
    second = rig.inbox.check()
    assert first != second and len(rig.arrived) == 2


def test_an_old_print_is_not_imported_when_the_app_opens(tmp_path, monkeypatch):
    rig = Rig(tmp_path)
    rig.print(age=RECENT_S + 60)
    monkeypatch.setattr(rig.inbox, "_watch", lambda: None)
    rig.inbox.start()
    assert rig.inbox.check() is None and rig.inbox.check() is None


def test_a_print_made_just_before_the_app_opened_is_imported(tmp_path, monkeypatch):
    rig = Rig(tmp_path)
    rig.print(age=60)
    monkeypatch.setattr(rig.inbox, "_watch", lambda: None)
    rig.inbox.start()
    rig.inbox.check()
    assert rig.inbox.check() is not None


def test_is_finished_pdf(tmp_path):
    path = tmp_path / "x.pdf"
    assert not is_finished_pdf(path)
    path.write_bytes(b"hello")
    assert not is_finished_pdf(path)
    path.write_bytes(PDF)
    assert is_finished_pdf(path)
