
#Task 1: DemoWebShop — Session Authentication

import xml.etree.ElementTree as ET
from playwright.sync_api import expect
from Assignment4_tests.test_parabank_e2e import BASE, fresh_logged_in_user, account_numbers



API = "https://parabank.parasoft.com/parabank/services/bank"


def get_demo_customer_id(page, username, password):
   
    from urllib.parse import quote
    url = API + "/login/" + quote(username, safe="") + "/" + quote(password, safe="")
    response = page.context.request.get(url, headers={"Accept": "application/xml"})
    
    assert response.status == 200, f"Demo customer lookup status {response.status}"
    
    customer = ET.fromstring(response.text())
    customer_id = customer.findtext("id")
    
    assert customer_id and customer_id.isdigit(), "No valid demo customer ID in API reply"
    return customer_id


def test_09_api_get_current_user_accounts(test_page, log):
    
    username, password = fresh_logged_in_user(test_page, log)
    
    customer_id = get_demo_customer_id(test_page, username, password)
    response = test_page.context.request.get(API + f"/customers/{customer_id}/accounts", headers={"Accept": "application/xml"})
   
    assert response.status == 200, f"GET accounts returned {response.status}"
   
    root = ET.fromstring(response.text())
    accounts = root.findall(".//account")
    
    assert accounts, "No accounts in API response"
    log.info("GET customer accounts passed, count=%d", len(accounts))
   
    # UI and API must show the same demo account number.
    
    ui_numbers = account_numbers(test_page)
    api_numbers = [a.findtext("id") for a in accounts]
    
    assert any(n in ui_numbers for n in api_numbers), "API accounts do not match UI accounts"


def test_10_api_create_account_and_verify_in_ui(test_page, log):
   
    username, password = fresh_logged_in_user(test_page, log)
    customer_id = get_demo_customer_id(test_page, username, password)
    old_numbers = account_numbers(test_page)
    
    assert old_numbers, "A source demo account is required"
    
    response = test_page.context.request.post(
        API + "/createAccount",
        params={"customerId": customer_id, "newAccountType": "1", "fromAccountId": old_numbers[0]},
        headers={"Accept": "application/xml"},
    )
    
    assert response.status in (200, 201), f"Create-account API status {response.status}"
    
    new_account = ET.fromstring(response.text())
    new_id = new_account.findtext("id")
    assert new_id and new_id.isdigit(), "Create-account API did not return an account ID"
    assert new_id not in old_numbers, "Created account ID should be new"
    
    # Refresh the real browser overview and compare with API result.
    
    test_page.get_by_role("link", name="Accounts Overview").click()
    test_page.reload()
    expect(test_page.get_by_role("link", name=new_id, exact=True)).to_be_visible(timeout=20000)
    log.info("Created demo account appears in UI; test ID=%s", new_id)
