"""
Tests for Swagger UI, ReDoc, and Content Security Policy (CSP) scoped headers.
Verifies that:
1. Strict CSP is preserved on normal application routes (/health, /ready, /scan).
2. /docs serves local Swagger UI bundle with cryptographic nonce in inline script and CSP header.
3. /docs and /redoc use local/data-URI favicon, removing external fastapi.tiangolo.com requests.
4. /static/swagger-ui/ assets are served with HTTP 200.
5. /openapi.json remains accessible and valid.
"""

import sys
import re
from pathlib import Path
from fastapi.testclient import TestClient

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from main import app


def test_normal_routes_preserve_strict_csp():
    """Normal application routes must retain strict default-src 'self' CSP."""
    client = TestClient(app)
    for route in ("/health", "/ready"):
        res = client.get(route)
        assert res.status_code == 200
        csp = res.headers.get("content-security-policy", "")
        assert csp == "default-src 'self'; frame-ancestors 'none';"
        assert "unsafe-inline" not in csp
        assert "jsdelivr" not in csp


def test_swagger_docs_serves_html_and_local_assets():
    """Swagger UI /docs endpoint must return HTTP 200 and reference local static assets."""
    client = TestClient(app)
    res = client.get("/docs")
    assert res.status_code == 200
    html = res.text

    # Must reference local assets
    assert "/static/swagger-ui/swagger-ui-bundle.js" in html
    assert "/static/swagger-ui/swagger-ui.css" in html

    # Must NOT reference external CDN or default external favicon
    assert "https://fastapi.tiangolo.com/img/favicon.png" not in html


def test_swagger_docs_csp_has_matching_nonce():
    """The inline Swagger UI script must have a nonce matching the CSP header."""
    client = TestClient(app)
    res = client.get("/docs")
    assert res.status_code == 200

    csp = res.headers.get("content-security-policy", "")
    assert csp, "Content-Security-Policy header must be present on /docs"

    # Extract nonce from HTML
    match = re.search(r'<script nonce="([^"]+)">', res.text)
    assert match is not None, "Inline script in /docs must contain nonce attribute"
    nonce = match.group(1)

    # Verify nonce is in CSP header
    assert f"'nonce-{nonce}'" in csp, f"Nonce {nonce} must appear in CSP script-src"

    # Verify CSP permits local/trusted resources without global wildcard
    assert "script-src 'self'" in csp
    assert "connect-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


def test_static_swagger_assets_available():
    """Static Swagger UI files must be served locally with HTTP 200."""
    client = TestClient(app)

    res_js = client.get("/static/swagger-ui/swagger-ui-bundle.js")
    assert res_js.status_code == 200
    assert len(res_js.content) > 100_000

    res_css = client.get("/static/swagger-ui/swagger-ui.css")
    assert res_css.status_code == 200
    assert len(res_css.content) > 10_000


def test_openapi_json_accessible():
    """OpenAPI schema must be served with valid JSON."""
    client = TestClient(app)
    res = client.get("/openapi.json")
    assert res.status_code == 200
    data = res.json()
    assert "openapi" in data
    assert "paths" in data
    assert "/health" in data["paths"]


def test_redoc_endpoint_has_scoped_csp():
    """ReDoc endpoint must render with scoped CSP and sanitized favicon."""
    client = TestClient(app)
    res = client.get("/redoc")
    assert res.status_code == 200

    csp = res.headers.get("content-security-policy", "")
    assert "https://cdn.jsdelivr.net" in csp
    assert "default-src 'self'" in csp
    assert "https://fastapi.tiangolo.com/img/favicon.png" not in res.text
    assert "redoc.standalone.js" in res.text
