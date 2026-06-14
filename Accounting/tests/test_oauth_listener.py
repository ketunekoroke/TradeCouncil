"""scripts/oauth_listener.py の純粋部分(redirect 解析)。socket は CI で bind しない。"""

from scripts import oauth_listener as listener


def test_split_redirect_http_localhost():
    assert listener._split_redirect("http://localhost:8765/callback") == ("localhost", 8765, "/callback")


def test_split_redirect_https_default_port():
    assert listener._split_redirect(
        "https://expense.moneyforward.com/api/oauth2-redirect.html"
    ) == ("expense.moneyforward.com", 443, "/api/oauth2-redirect.html")


def test_split_redirect_no_path_defaults_root():
    assert listener._split_redirect("http://127.0.0.1:9000") == ("127.0.0.1", 9000, "/")


def test_is_loopback_redirect_true():
    assert listener.is_loopback_redirect("http://localhost:8765/callback") is True
    assert listener.is_loopback_redirect("http://127.0.0.1:8765/cb") is True


def test_is_loopback_redirect_false():
    # expense の HTTPS redirect は loopback リスナでは受けられない
    assert listener.is_loopback_redirect("https://expense.moneyforward.com/api/oauth2-redirect.html") is False
    assert listener.is_loopback_redirect("https://localhost:8765/cb") is False  # https は対象外
    assert listener.is_loopback_redirect(None) is False
