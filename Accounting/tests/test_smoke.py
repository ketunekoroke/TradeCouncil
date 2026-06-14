"""足場の健全性: パッケージ import と config の読み込み。"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_core_importable():
    import core  # noqa: F401


def test_cli_parser_builds():
    from scripts import cli

    parser = cli.build_parser()
    # 主要サブコマンドが定義されている
    args = parser.parse_args(["test"])
    assert args.command == "test"
    args = parser.parse_args(["hooks", "install"])
    assert args.command == "hooks" and args.hooks_command == "install"


def test_sharepoint_config_valid():
    cfg = json.loads((PROJECT_ROOT / "sharepoint.config.json").read_text(encoding="utf-8"))
    assert cfg["env_prefix"] == "AC"
    mirror = cfg["git_mirror"]
    assert mirror["remote"] == "Accounting/Docs"
    assert mirror["paths"] == ["Accounting/docs"]
    assert mirror["branch"] == "main"
