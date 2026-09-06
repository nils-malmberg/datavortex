from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

CSV_CONTENT = (
    b"name,age,score,category\n"
    b"Alice,30,85.5,A\n"
    b"Bob,25,90.0,B\n"
    b"Charlie,35,78.2,A\n"
    b"Diana,28,88.0,B\n"
)


def _upload_and_parse():
    resp = client.post("/api/upload", files={"file": ("test.csv", CSV_CONTENT, "text/csv")})
    session_id = resp.json()["session_id"]
    client.post("/api/parse", json={"session_id": session_id, "separator": ","})
    return session_id


def test_report_all_sections():
    session_id = _upload_and_parse()
    resp = client.post(
        "/api/report/pdf",
        json={
            "session_id": session_id,
            "sections": ["summary", "stats", "preview", "plots", "correlations", "metadata"],
            "plots": [{"kind": "1d", "params": {"plot_type": "histogram", "column": "age"}}],
        },
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"
    assert len(resp.content) > 1000


def test_report_selected_sections_only():
    session_id = _upload_and_parse()
    resp = client.post(
        "/api/report/pdf",
        json={"session_id": session_id, "sections": ["summary"]},
    )
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_report_no_sections_still_has_cover():
    session_id = _upload_and_parse()
    resp = client.post("/api/report/pdf", json={"session_id": session_id, "sections": []})
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_report_with_two_plots():
    session_id = _upload_and_parse()
    resp = client.post(
        "/api/report/pdf",
        json={
            "session_id": session_id,
            "sections": ["plots"],
            "plots": [
                {"kind": "1d", "params": {"plot_type": "histogram", "column": "age"}},
                {"kind": "2d", "params": {"plot_type": "scatter", "x": "age", "y": "score"}},
            ],
        },
    )
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_report_reflects_active_filter():
    session_id = _upload_and_parse()
    client.post(
        f"/api/data/{session_id}/filter",
        json={"filter": {"type": "condition", "column": "category", "operator": "eq", "value": "A"}},
    )
    resp = client.post(
        "/api/report/pdf",
        json={"session_id": session_id, "sections": ["summary"]},
    )
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_report_page_format_and_orientation():
    session_id = _upload_and_parse()
    resp = client.post(
        "/api/report/pdf",
        json={
            "session_id": session_id,
            "sections": ["summary"],
            "page_format": "Letter",
            "orientation": "landscape",
        },
    )
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"


def test_report_session_not_found():
    resp = client.post("/api/report/pdf", json={"session_id": "nope", "sections": ["summary"]})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_report_invalid_plot_params_rejected():
    session_id = _upload_and_parse()
    resp = client.post(
        "/api/report/pdf",
        json={
            "session_id": session_id,
            "sections": ["plots"],
            "plots": [{"kind": "2d", "params": {"plot_type": "scatter", "x": "does_not_exist", "y": "score"}}],
        },
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "COLUMN_NOT_FOUND"


def test_report_pdf_valid_even_with_no_optional_sections():
    session_id = _upload_and_parse()
    resp = client.post("/api/report/pdf", json={"session_id": session_id, "sections": []})
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"
    assert len(resp.content) > 2000  # les stats détaillées (toujours incluses) pèsent plus qu'une simple couverture


def test_detailed_stats_flowables_always_present_regardless_of_sections():
    """Phase 8.1 : les statistiques détaillées (qualité, corrélations,
    suggestions) sont générées même si l'utilisateur ne coche aucune section
    — elles ne sont plus optionnelles. Vérifié au niveau des flowables plutôt
    que du PDF final (dont le flux de contenu est compressé)."""
    import pandas as pd
    from reportlab.lib.units import cm

    from app.profile_service import detailed_profile
    from app.report import _detailed_stats_flowables, _styles, _suggestions_flowables
    from app.stats_service import advanced_stats

    df = pd.DataFrame({
        "age": [30, 25, 35, 28, None],
        "score": [85.5, 90.0, 78.2, 88.0, 91.0],
        "category": ["A", "B", "A", "B", "A"],
    })
    styles = _styles()
    stats = advanced_stats(df)
    profile = detailed_profile(df)

    stats_story = _detailed_stats_flowables(df, styles, 16 * cm, True, stats, profile)
    assert len(stats_story) > 5  # plusieurs tableaux/titres, pas juste un titre vide
    assert any("Statistiques détaillées" in getattr(f, "text", "") for f in stats_story)

    suggestions_story = _suggestions_flowables(styles, 16 * cm, profile)
    assert any("Suggestions" in getattr(f, "text", "") for f in suggestions_story)


def test_report_includes_groupby_plot():
    session_id = _upload_and_parse()
    resp = client.post(
        "/api/report/pdf",
        json={
            "session_id": session_id,
            "sections": [],
            "plots": [
                {
                    "kind": "groupby",
                    "params": {
                        "group_by": ["category"],
                        "aggregations": [{"column": "score", "func": "mean"}],
                    },
                    "title": "Score moyen par catégorie",
                }
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.content[:4] == b"%PDF"


def test_report_includes_pivot_plot():
    session_id = _upload_and_parse()
    resp = client.post(
        "/api/report/pdf",
        json={
            "session_id": session_id,
            "sections": [],
            "plots": [
                {
                    "kind": "pivot",
                    "params": {
                        "index": ["category"],
                        "columns": [],
                        "values": "score",
                        "aggfunc": "mean",
                    },
                    "title": "Pivot score par catégorie",
                }
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.content[:4] == b"%PDF"


def test_report_includes_ml_plot():
    session_id = _upload_and_parse()
    resp = client.post(
        "/api/report/pdf",
        json={
            "session_id": session_id,
            "sections": ["plots"],
            "plots": [
                {
                    "kind": "ml",
                    "params": {
                        "ml_type": "regression",
                        "features": ["age"],
                        "target": "score",
                        "model_type": "linear",
                    },
                    "title": "Régression âge/score",
                }
            ],
        },
    )
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"
