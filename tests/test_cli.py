import pytest

from styx import cli

# The CLI uses the real default Argon2id parameters (64 MiB), as users do.


def set_passwords(monkeypatch, *answers):
    it = iter(answers)
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(it))


def test_cli_roundtrip_file_and_folder(tmp_path, monkeypatch, capsys):
    f = tmp_path / "a.txt"
    f.write_bytes(b"hello")
    d = tmp_path / "dir"
    (d / "sub").mkdir(parents=True)
    (d / "sub" / "b.txt").write_bytes(b"world")

    set_passwords(monkeypatch, "pw", "pw")
    assert cli.main(["encrypt", str(f), str(d)]) == 0
    assert f.read_bytes().startswith(b"STYX")
    assert (d / "sub" / "b.txt").read_bytes().startswith(b"STYX")

    set_passwords(monkeypatch, "bad")
    assert cli.main(["decrypt", str(f), str(d)]) == 1
    assert "FAILED" in capsys.readouterr().err

    set_passwords(monkeypatch, "pw")
    assert cli.main(["decrypt", str(f), str(d)]) == 0
    assert f.read_bytes() == b"hello"
    assert (d / "sub" / "b.txt").read_bytes() == b"world"


def test_cli_password_mismatch(tmp_path, monkeypatch):
    f = tmp_path / "a.txt"
    f.write_bytes(b"x")
    set_passwords(monkeypatch, "one", "two")
    with pytest.raises(SystemExit):
        cli.main(["encrypt", str(f)])
    assert f.read_bytes() == b"x"


def test_cli_has_no_password_argument():
    with pytest.raises(SystemExit):
        cli.main(["encrypt", "--password", "secret", "x"])
