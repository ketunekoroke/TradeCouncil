"""core.config の .env パーサ(インラインコメント除去・クォート保持)。"""

from core import config


def test_parse_env_strips_inline_comment(tmp_path):
    p = tmp_path / ".env"
    p.write_text(
        "MONEYFORWARD_ACCOUNTING_AUTH_CODE=wQjAbc123     # ブラウザ認可後に受け取った code\n"
        "FOO=bar\n",
        encoding="utf-8",
    )
    env = config._parse_env_file(p)
    assert env["MONEYFORWARD_ACCOUNTING_AUTH_CODE"] == "wQjAbc123"  # コメントと前後空白が除去される
    assert env["FOO"] == "bar"


def test_parse_env_keeps_hash_without_leading_space(tmp_path):
    p = tmp_path / ".env"
    p.write_text("KEY=abc#notacomment\n", encoding="utf-8")
    env = config._parse_env_file(p)
    assert env["KEY"] == "abc#notacomment"  # 空白を伴わない # は値の一部


def test_parse_env_quoted_value_preserved(tmp_path):
    p = tmp_path / ".env"
    p.write_text('KEY="value with # and spaces"\n', encoding="utf-8")
    env = config._parse_env_file(p)
    assert env["KEY"] == "value with # and spaces"  # クォート内は無加工


def test_parse_env_comment_and_blank_lines_skipped(tmp_path):
    p = tmp_path / ".env"
    p.write_text("# full line comment\n\nA=1\n", encoding="utf-8")
    env = config._parse_env_file(p)
    assert env == {"A": "1"}
