

import os
from pathlib import Path

from playwright.sync_api import expect

WEBSHOP = "https://demowebshop.tricentis.com"
STATE = Path(__file__).resolve().parents[1] / "auth/webshop_state.json"


def saved_state_or_fail():
    """A missing/invalid state is a FAILURE, never an automatic re-login."""
    import json
    if not STATE.is_file():
        raise AssertionError("Missing auth/webshop_state.json. Run test_01_webshop_login_and_save_state first.")
    try:
        content = json.loads(STATE.read_text(encoding="utf-8"))
        assert isinstance(content.get("cookies"), list)
        assert isinstance(content.get("origins"), list)
        assert content["cookies"], "No cookies were saved"
    except (ValueError, TypeError, AssertionError) as exc:
        raise AssertionError("Invalid/empty auth/webshop_state.json. Re-run test_01_webshop_login_and_save_state.") from exc
    return str(STATE)


def test_01_webshop_login_and_save_state(test_page, log):
   
   #Log in with .env credentials and save the authenticated browser state."""
    
    email, password = os.getenv("WEBSHOP_EMAIL"), os.getenv("WEBSHOP_PASSWORD")
    assert email and password and not email.startswith("your-"), "Set WEBSHOP_EMAIL and WEBSHOP_PASSWORD in local .env"
    page = test_page
    log.info("Opening DemoWebShop login page")
    page.goto(WEBSHOP + "/login")
    page.locator("#Email").fill(email)
    page.locator("#Password").fill(password)
    page.locator("input.login-button").click()
    expect(page.locator(".header-links .account")).to_be_visible()
    log.info("Login successful; saving state (contents NOT logged)")
    STATE.parent.mkdir(exist_ok=True)
    page.context.storage_state(path=str(STATE))
    assert STATE.exists(), "Session state was not saved"


def test_02_webshop_reuse_session_without_login(test_page, log):
  
  #Open a NEW browser context using saved login state (no login form).
    
    old_page = test_page
    state_path = saved_state_or_fail()
    new_context = old_page.context.browser.new_context(storage_state=state_path)
    new_context.tracing.start(screenshots=True, snapshots=True, sources=True)
    old_page._extra_contexts.append(new_context)
    try:
        page = new_context.new_page()
        page.goto(WEBSHOP)
        expect(page.locator(".header-links .account")).to_be_visible()
        log.info("SUCCESS: a NEW browser context reused the saved session")
    finally:
        pass  
    
    # Shared fixture stops tracing and closes this extra context.


def test_03_webshop_search_book_and_add_to_cart(test_page, log):
  # Reuse saved state, search for a book, open it, and add it to the cart."""
    
    state_path = saved_state_or_fail()
    context = test_page.context.browser.new_context(storage_state=state_path)
    context.tracing.start(screenshots=True, snapshots=True, sources=True)
    test_page._extra_contexts.append(context)
    try:
        page = context.new_page()
        page.goto(WEBSHOP + "/books")
        expect(page.locator(".header-links .account")).to_be_visible()
        page.locator("#small-searchterms").fill("Computing and Internet")
        page.locator("input.search-box-button").click()
        products = page.locator(".product-item .product-title a")
        expect(products.first).to_be_visible()
        products.first.click()
        
        # The default demo search normally returns a book with a product add button.
        
        button = page.locator("input[id^='add-to-cart-button-']").first
        expect(button).to_be_visible()
        button.click()
        expect(page.locator("#bar-notification")).to_contain_text("added", timeout=15000)
        page.locator(".header-links .ico-cart").click()
        expect(page.locator(".cart-item-row").first).to_be_visible()
        log.info("Book appears in cart using saved session")
    finally:
        pass 
    # Shared fixture gathers any failure evidence.
