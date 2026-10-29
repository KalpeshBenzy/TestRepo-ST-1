#Shared beginner-friendly browser setup and failure evidence.

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")


def pytest_configure(config):
   #Write timestamped output to both terminal and a log file."""
    
    (ROOT / "logs").mkdir(exist_ok=True)
    logger = logging.getLogger("assignment")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    for handler in (logging.StreamHandler(), logging.FileHandler(ROOT / "logs/pytest.log", encoding="utf-8")):
        handler.setFormatter(fmt)
        logger.addHandler(handler)


@pytest.fixture
def log():
    return logging.getLogger("assignment")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    setattr(item, "report_" + report.when, report)
    if report.failed:
        logger = logging.getLogger("assignment")
        # Pytest's failure representation contains the failed assertion/traceback.
        logger.error("FAILED %s [%s]\n%s", item.nodeid, report.when, report.longrepr)


@pytest.fixture
def test_page(request, log):
    """A fresh Chromium context, with automatic screenshot/trace on failure."""
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", request.node.name)[:90]
    unique = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_" + uuid4().hex[:6]
    file_stem = name + "_" + unique
    log.info("START %s", request.node.nodeid)
    with sync_playwright() as pw:
        launch_options = {"headless": True}
        if os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE"):
            launch_options["executable_path"] = os.environ["PLAYWRIGHT_CHROMIUM_EXECUTABLE"]
        browser = pw.chromium.launch(**launch_options)
        context = browser.new_context(accept_downloads=False)
        context.set_default_timeout(15000)
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = context.new_page()
        page._extra_contexts = []  # Track any extra contexts created by individual tests.
        page.on("console", lambda msg: log.error("Browser console error: %s", msg.text[:300]) if msg.type == "error" else None)
        page.on("pageerror", lambda err: log.error("Browser page error: %s", str(err)[:300]))
        page.on("response", lambda response: log.warning("HTTP failure %s %s", response.status, response.url.split("?")[0]) if response.status >= 400 else None)
        try:
            yield page
        finally:
            rep = getattr(request.node, "report_call", None)
            setup_rep = getattr(request.node, "report_setup", None)
            failed = bool((rep and rep.failed) or (setup_rep and setup_rep.failed))
            # Also capture any secondary browser contexts used for session reuse.
            for index, extra in enumerate(page._extra_contexts):
                try:
                    if failed:
                        extra_page = extra.pages[-1] if extra.pages else extra.new_page()
                        extra_page.screenshot(path=str(ROOT / "artifacts/screenshots" / (file_stem + f"_extra{index}.png")), full_page=True)
                        extra.tracing.stop(path=str(ROOT / "artifacts/traces" / (file_stem + f"_extra{index}.zip")))
                    else:
                        extra.tracing.stop()
                except Exception as exc:
                    log.exception("Could not collect secondary-context evidence: %s", exc)
                finally:
                    extra.close()
            if failed:
                screenshot = ROOT / "artifacts/screenshots" / (file_stem + ".png")
                trace = ROOT / "artifacts/traces" / (file_stem + ".zip")
                try:
                    page.screenshot(path=str(screenshot), full_page=True, timeout=10000)
                    log.error("Screenshot: %s", screenshot)
                except Exception as exc:
                    log.exception("Could not capture screenshot: %s", exc)
                try:
                    context.tracing.stop(path=str(trace))
                    log.error("Trace: %s", trace)
                except Exception as exc:
                    log.exception("Could not save trace: %s", exc)
            else:
                context.tracing.stop()
            context.close()
            browser.close()
            log.info("END %s status=%s", request.node.nodeid, "FAILED" if failed else "PASSED")
