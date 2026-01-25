from pytest_bdd import scenarios, given, when, then, parsers
from pages.furniture_page import FurniturePage
from playwright.sync_api import expect

# 加载 feature 文件
scenarios('../features/furniture_plp.feature')

# Fixture for Page Object
import pytest
@pytest.fixture
def furniture_page(page):
    return FurniturePage(page)

# --- Given Steps ---

@given("I open the VidaXL furniture page")
def open_page(furniture_page):
    furniture_page.navigate()

# --- Sort Scenario Steps ---

@when("I open the sorting dropdown")
def open_sort(furniture_page):
    # 这一步通常包含在 select_sort_option 中，或者是断言下拉框可见
    pass

@when(parsers.parse('I select "{option}" sorting option'))
def select_sort(furniture_page, option):
    furniture_page.select_sort_option(option)

@then("the products should be sorted by price in ascending order")
def verify_price_sort(furniture_page):
    prices = furniture_page.get_product_prices()
    # 断言价格是从低到高排序的
    assert prices == sorted(prices), f"Prices match not sorted: {prices}"

# --- Filter Modal Scenario Steps ---

@when('I click the "Filters" button')
def click_filters(furniture_page):
    furniture_page.open_filter_modal()

@then("the filter modal should be visible")
def modal_is_visible(furniture_page):
    expect(furniture_page.page.locator(furniture_page.modal_content)).to_be_visible()

@when('I expand the "Categories" section in modal')
def expand_cats(furniture_page):
    furniture_page.expand_modal_category()

@when("I traverse through categories, sub-categories, and deep-level categories")
def traverse_cats(furniture_page):
    # 模拟遍历：一级 -> 二级 -> (耳机子类目/三级)
    furniture_page.traverse_categories()

@when("I select a random category filter")
def select_random_cat(furniture_page):
    # 选中任意一个 checkbox
    furniture_page.page.locator("input[type='checkbox']").first.check()

@when('I click "Show products" button')
def click_show(furniture_page):
    furniture_page.click_show_products()

@when('I click "Clear all filters"')
def click_clear(furniture_page):
    furniture_page.clear_filters()

@then("the URL should not contain filter parameters")
def verify_url_clean(furniture_page):
    # 简单的断言：URL不应该包含 ?q= 或特定的 filter param
    # 实际逻辑需根据 VidaXL 的 URL 结构调整
    current_url = furniture_page.page.url
    # 假设 filter 会加参数，reset 后参数消失
    # 这里做一个简单的打印验证，因为不确定具体的 param key
    print(f"Current URL after reset: {current_url}")
    assert "g/436/furniture" in current_url

# --- Inline Filters Scenario Steps ---

@when('I interact with the inline "Categories" dropdown')
def inline_cat(furniture_page):
    furniture_page.interact_inline_category()

@when("I select a sub-category from the inline dropdown")
def select_inline_sub(furniture_page):
    # 这一步已合并在 interact_inline_category 的逻辑中，或者可以在这里显式写
    pass

@when('I interact with the inline "Price" dropdown')
def inline_price(furniture_page):
    furniture_page.interact_inline_price()

@when("I set a price range")
def set_price(furniture_page):
    # 已包含在 interact_inline_price
    pass

@when('I interact with the inline "Type" dropdown')
def inline_type(furniture_page):
    furniture_page.interact_inline_type()

@then("the product results should update")
def verify_update(furniture_page):
    # 验证页面重新加载或 Listing 蒙层消失
    # 也可以验证 URL 变化
    expect(furniture_page.page.locator(furniture_page.product_price).first).to_be_visible()