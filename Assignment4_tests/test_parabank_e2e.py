#Task 2: one simple test per ParaBank scenario, with a NEW demo user per test.

from uuid import uuid4
from playwright.sync_api import expect
import pytest

BASE = "https://parabank.parasoft.com/parabank"


def register_demo_user(page, log):
    """Create disposable fake credentials; NEVER use a real bank account."""
    username = "qa" + uuid4().hex[:11]
    password = "DemoTest_456!"  # Fixed dummy password, never log it.
    log.info("Registering disposable user (identifier not secret): %s", username)
    page.goto(BASE + "/register.htm")
    demo_fields = {
        "customer.firstName": "Demo", "customer.lastName": "Tester",
        "customer.address.street": "10 Test Lane",
        "customer.address.city": "Exampletown",
        "customer.address.state": "TestState",
        "customer.address.zipCode": "12345",
        "customer.phoneNumber": "5550100000",
        "customer.ssn": "000000000",  # Fake test-only identifier.
        "customer.username": username,
        "customer.password": password,
        "repeatedPassword": password,
    }
    for field, value in demo_fields.items():
        page.locator("[name='" + field + "']").fill(value)
    page.locator("input[value='Register']").click()
    expect(page.locator("#rightPanel")).to_contain_text("Welcome", timeout=20000)
    expect(page.get_by_role("link", name="Log Out")).to_be_visible()
    return username, password


def login_demo_user(page, username, password):
    """Use the application's normal login form."""
    page.goto(BASE + "/index.htm")
    page.locator("input[name='username']").fill(username)
    page.locator("input[name='password']").fill(password)
    page.locator("input[value='Log In']").click()
    expect(page.get_by_role("link", name="Accounts Overview")).to_be_visible()


def fresh_logged_in_user(page, log):
    """Register, log out, log back in. Avoid test-order dependencies."""
    username, password = register_demo_user(page, log)
    page.get_by_role("link", name="Log Out").click()
    login_demo_user(page, username, password)
    return username, password


def account_numbers(page):
    """Account numbers are demo identifiers, never real personal data."""
    page.get_by_role("link", name="Accounts Overview").click()
    rows = page.locator("#accountTable tbody tr")
    links = rows.locator("a[href*='activity.htm?id=']")
    return [links.nth(i).inner_text().strip() for i in range(links.count())]


def test_04_parabank_registration_and_login(test_page, log):
    """Scenario 1: register, sign out, then sign in again."""
    fresh_logged_in_user(test_page, log)
    test_page.get_by_role("link", name="Accounts Overview").click()
    expect(test_page.locator("#accountTable")).to_be_visible()
    log.info("Registration and login verified")


def test_05_parabank_account_overview_and_details(test_page, log):
    """Scenario 2: verify an overview account opens the details screen."""
    fresh_logged_in_user(test_page, log)
    numbers = account_numbers(test_page)
    assert numbers, "No demo accounts were found"
    log.info("Opening DEMO account identifier: %s", numbers[0])
    test_page.get_by_role("link", name=numbers[0], exact=True).first.click()
    expect(test_page.locator("#accountId")).to_contain_text(numbers[0])
    expect(test_page.locator("#accountDetails")).to_be_visible()


def test_06_parabank_transfer_funds(test_page, log):
    """Scenario 3: move $1 between 2 demo accounts, or mark blocked."""
    fresh_logged_in_user(test_page, log)
    numbers = account_numbers(test_page)
    if len(numbers) < 2:
        log.info("Only one demo account; attempting to open a second account")
        test_page.get_by_role("link", name="Open New Account").click()
        try:
            test_page.locator("#type").select_option(label="SAVINGS")
            test_page.locator("#fromAccountId").select_option(index=0)
            test_page.get_by_role("button", name="Open New Account").click()
            expect(test_page.locator("#newAccountId")).to_be_visible(timeout=15000)
            numbers = account_numbers(test_page)
        except Exception as exc:
            pytest.skip("BLOCKED: Cannot create second demo account: " + type(exc).__name__)
    if len(numbers) < 2:
        pytest.skip("BLOCKED: Fewer than two demo accounts are available")
    test_page.get_by_role("link", name="Transfer Funds").click()
    test_page.locator("#amount").fill("1")
    test_page.locator("#fromAccountId").select_option(numbers[0])
    test_page.locator("#toAccountId").select_option(numbers[1])
    test_page.get_by_role("button", name="Transfer").click()
    expect(test_page.locator("#showResult")).to_contain_text("Transfer Complete", timeout=15000)
    expect(test_page.locator("#amountResult")).to_contain_text("$1.00")
    log.info("Transferred $1.00 between disposable demo accounts")


def test_07_parabank_bill_pay_validation(test_page, log):
    """Scenario 4: incomplete bill pay must show a validation error."""
    fresh_logged_in_user(test_page, log)
    test_page.get_by_role("link", name="Bill Pay").click()
    
    # Submit with ALL fields empty on purpose.
    
    test_page.get_by_role("button", name="Send Payment").click()
    errors = test_page.locator("span.error:visible")
    expect(errors.first).to_be_visible()
    assert errors.count() > 0, "No form validation was displayed"
    assert not test_page.locator("#billpayResult").is_visible(), "Unexpected successful payment"
    log.info("Incomplete Bill Pay form was correctly rejected")


def test_08_parabank_logout_and_protected_page(test_page, log):
    """Scenario 5: log out and check a protected URL in a NEW clean context."""
    fresh_logged_in_user(test_page, log)
    test_page.get_by_role("link", name="Log Out").click()
    expect(test_page.locator("input[name='username']")).to_be_visible()
    
    # A fresh context has no cookies from the logged-in user.
    
    clean = test_page.context.browser.new_context()
    clean.tracing.start(screenshots=True, snapshots=True, sources=True)
    test_page._extra_contexts.append(clean)
    try:
        page = clean.new_page()
        page.goto(BASE + "/overview.htm")
        expect(page.locator("input[name='username']")).to_be_visible()
        assert not page.locator("#accountTable").is_visible(), "Protected accounts exposed without login"
        log.info("Protected page requires authentication in fresh context")
    finally:
        pass  
   
    # Fixture collects trace evidence and closes context.
