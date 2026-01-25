from playwright.sync_api import Page, expect
import re
import time


class FurniturePage:
    def __init__(self, page: Page):
        self.page = page
        self.url = "https://www.vidaxl.com/g/436/furniture"

        # Selectors (Locators)
        self.cookie_accept_btn = "button:has-text('Accept')"  # 假设有 Cookie 弹窗

        # PLP Sorting Elements
        self.sort_trigger = "button[aria-label*='Sort'], .sort-dropdown-trigger, button:has-text('Recommended')"
        self.product_price = "[data-testid='product-price'], .product-card .price"

        # Filter Modal Elements
        self.filter_btn = "button:has-text('Filters')"
        self.modal_content = "div[role='dialog'], .filter-modal"
        self.modal_category_header = f"{self.modal_content} button:has-text('Categories')"
        self.clear_all_filters_btn = "button:has-text('Clear all filters')"
        self.show_products_btn = "button:has-text('Show') >> text=products"

        # Inline Filters (Pills)
        self.inline_cat_trigger = "button:has-text('Categories')"
        self.inline_price_trigger = "button:has-text('Price')"
        self.inline_type_trigger = "button:has-text('Type')"

    def navigate(self):
        self.page.goto(self.url)
        # 处理 Cookie 弹窗 (如果有)
        try:
            if self.page.locator(self.cookie_accept_btn).is_visible(timeout=3000):
                self.page.locator(self.cookie_accept_btn).click()
        except:
            pass

    def select_sort_option(self, option_text):
        # 点击排序下拉框
        self.page.locator(self.sort_trigger).first.click()
        # 点击具体选项 (使用 text=模糊匹配)
        self.page.locator(f"li:has-text('{option_text}'), button:has-text('{option_text}')").click()
        self.page.wait_for_load_state('networkidle')

    def get_product_prices(self):
        # 等待价格元素加载
        self.page.wait_for_selector(self.product_price)
        price_elements = self.page.locator(self.product_price).all()
        prices = []
        for el in price_elements:
            text = el.inner_text()
            # 移除货币符号并转为浮点数
            clean_text = re.sub(r'[^\d.]', '', text)
            if clean_text:
                prices.append(float(clean_text))
        return prices

    def open_filter_modal(self):
        self.page.locator(self.filter_btn).click()

    def expand_modal_category(self):
        # 确保 Category 区域展开
        cat_header = self.page.locator(self.modal_category_header)
        if cat_header.get_attribute("aria-expanded") == "false":
            cat_header.click()

    def traverse_categories(self):
        """
        遍历 Filter 弹窗中的类目树。
        逻辑：查找列表项，如果是折叠的就展开，模拟遍历 3 层结构。
        """
        # 这是一个模拟递归遍历的简化版
        # 1. 找到所有一级类目
        level1_items = self.page.locator(".modal-body ul > li")

        # 演示：点击第一个有子菜单的类目
        if level1_items.count() > 0:
            first_item = level1_items.first
            # 检查是否有展开按钮
            expand_btn = first_item.locator("button, .icon-expand")
            if expand_btn.count() > 0:
                expand_btn.first.click()
                self.page.wait_for_timeout(500)  # 等待动画

                # 2. 尝试点击二级类目 (如果有)
                level2_items = first_item.locator("ul > li")
                if level2_items.count() > 0:
                    level2_items.first.click()  # 假设点击即选中或展开
                    print("Traversed Level 2 Category")

    def click_show_products(self):
        self.page.locator(self.show_products_btn).click()
        self.page.wait_for_load_state('networkidle')

    def clear_filters(self):
        # 有时候 Reset 按钮在 Modal 里面，有时候在 PLP 顶部
        if self.page.locator(self.clear_all_filters_btn).is_visible():
            self.page.locator(self.clear_all_filters_btn).click()
        else:
            # 尝试再次打开 Modal 点击 Reset
            self.open_filter_modal()
            self.page.locator(self.clear_all_filters_btn).click()
        self.page.wait_for_load_state('networkidle')

    def interact_inline_category(self):
        self.page.locator(self.inline_cat_trigger).click()
        # 随机选一个 checkbox
        self.page.locator("input[type='checkbox']").first.check()

    def interact_inline_price(self):
        self.page.locator(self.inline_price_trigger).click()
        # 假设有输入框或 Slider
        inputs = self.page.locator("input[type='number']")
        if inputs.count() >= 2:
            inputs.nth(0).fill("50")  # Min
            inputs.nth(1).fill("500")  # Max

    def interact_inline_type(self):
        self.page.locator(self.inline_type_trigger).click()
        self.page.locator("input[type='checkbox']").first.check()