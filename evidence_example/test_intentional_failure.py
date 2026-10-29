"""Intentional demo failure to show logging, screenshot and trace creation."""

def test_intentional_failure_evidence(test_page, log):
    test_page.set_content("<html><body><h1>Safe Offline Screenshot Demo</h1><p>Intentional failure evidence, no credentials.</p></body></html>")
    log.info("Deliberately failing to demonstrate error evidence")
    assert 1 == 2, "EXPECTED DEMO FAILURE: show screenshot and trace"
