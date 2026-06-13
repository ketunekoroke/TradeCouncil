"""git pre-commit hook 本体(インストールは `tc hooks install`)。

1. ステージされた内容の秘密情報スキャン
2. config/policies/*.yaml: 決裁レコード(decision ブロック)なしの変更を拒否
3. config/generated/*: AUTO-GENERATED ヘッダの無いファイル(=手編集の疑い)を拒否
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hook_common import find_secret  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def staged_files() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return [line.strip() for line in (out.stdout or "").splitlines() if line.strip()]


def staged_content(path: str) -> str:
    out = subprocess.run(
        ["git", "show", f":{path}"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return (out.stdout or "") if out.returncode == 0 else ""


def main() -> int:
    errors: list[str] = []
    for path in staged_files():
        norm = path.replace("\\", "/")

        if norm.endswith(".example"):
            continue  # テンプレート(REPLACE_WITH_... のプレースホルダ)は対象外

        content = staged_content(path)

        if norm.startswith((".env",)):
            errors.append(f"{path}: .env はコミット禁止")
            continue

        label = find_secret(content)
        if label:
            errors.append(f"{path}: 秘密情報らしき内容({label})")

        if norm.startswith("config/policies/") and norm.endswith((".yaml", ".yml")):
            if "decision:" not in content or "decision_id:" not in content:
                errors.append(
                    f"{path}: 決裁レコード(decision ブロック)が無い。"
                    "ポリシー変更は tc policy record 経由のみ(運営規程 §2.3)"
                )

        if norm.startswith("config/generated/") and "AUTO-GENERATED" not in content:
            errors.append(f"{path}: AUTO-GENERATED ヘッダが無い(手編集の疑い)")

    if errors:
        print("pre-commit 検査エラー:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
