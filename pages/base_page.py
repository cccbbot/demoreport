#!/usr/bin/python
# -*- coding: UTF-8 -*-
import time

from playwright.sync_api import Page, expect
import logging

logger = logging.getLogger(__name__)

class BasePage:
    def __init__(self, page: Page):
        self.page = page
        self.context = page.context

    def get_session_cookies(self) -> list:
        return self.context.cookies()

    def set_session_cookie(self, name: str, value: str, domain: str = None):
        cookies = self.get_session_cookies()

        new_cookie = {
            "name": name,
            "value": value,
            "domain": domain or ".baidu.com",
            "path": "/",
        }

        cookies = [c for c in cookies if c["name"] != name]
        cookies.append(new_cookie)

        self.context.add_cookies(cookies)

    def clear_session_storage(self):
        for p in self.context.pages:
            try:
                p.evaluate("localStorage.clear(); sessionStorage.clear();")
            except:
                pass

    def add_session_route(self, url_pattern: str, handler):
        self.context.route(url_pattern, handler)
        print(f"Add Session Route: {url_pattern}")

    # def record_session_video(self):
    #     if hasattr(self.page, 'video'):
    #         return self.page.video.path()
    #     return None



    def navigate(self, url):
        self.page.goto(url)


    def handle_cookie_banner(self,name="Reject All"):
        try:
            reject_btn = self.page.get_by_role("button", name=name, exact=False)
            if reject_btn.is_visible(timeout=30000):
                reject_btn.click()
            else:
                self.page.locator(f"button:has-text('{name}')").click(timeout=2000)
        except:
            logger.info("No cookie banner found or already accepted.")


    def check_highlight_text(self, container_selector, text):
        #  .locator("visible=true") is used to filter element with display:none or hidden
        target_element = self.page.locator(container_selector)\
            .get_by_text(text, exact=False)\
            .locator("visible=true")\
            .first

        try:
            target_element.scroll_into_view_if_needed()
        except Exception:
            pass

        if target_element.is_visible():
            try:
                target_element.highlight()
                time.sleep(0.3)
            except Exception:
                pass

        logger.info(f"Check locator({container_selector}) contains text: [{text}]")

        expect(target_element).to_be_visible()

        return target_element


    def get_numeric_price(self, selector=".full-price.price-success", element_name="full-price"):
        import re
        import time

        price_el = self.page.locator(selector).locator("visible=true").first

        if price_el.is_visible():
            logger.info(f"get element [{element_name}]...")
            price_el.scroll_into_view_if_needed()
            price_el.highlight()
            time.sleep(0.5)
        # get raw text (example: "$ 219 99" or "$ 219.99" )
        raw_text = price_el.inner_text()
        logger.info(f"raw text: [{raw_text}]")

        # European site (using commas as decimal points)
        raw_text = raw_text.replace(',','.')

        if not raw_text.__contains__("."):
            match = re.search(r'(\d+)\s*(\d{2})', raw_text)
            if match:
                price_value = float(f"{match.group(1)}.{match.group(2)}")

                logger.info(f"get price value: {price_value} (type: {type(price_value)})")

                assert price_value > 0
                return price_value
        else:
            raw_text = raw_text.strip()
            if "Free" in raw_text or "free" in raw_text:
                logger.info(f"Change Free to 0.00")
                return 0.0
            else:
                clean_text = re.sub(r'[^\d.]', '', raw_text)
                try:
                    return float(clean_text)
                except:
                    logger.info(f"Change Price Failed and return None, raw text: {raw_text}")
                    return None


    def click(self, selector, name="element"):
        self.page.click(selector)

    def input_text(self, selector, text, name="field"):
        self.page.fill(selector, text)


    def get_locator_by_role(self,role,name,*args):
        if role=="button":
            self.page.get_by_role("button", name=name).click()
        elif role=="textbox":
            self.page.get_by_role("textbox", name=name, exact=True).click()
            self.page.get_by_role("textbox", name=name, exact=True).fill(args[0])
        elif role=="checkbox":
            self.page.get_by_role("checkbox", name=name).check()
        else:
            self.page.get_by_role(role, name=name, exact=True)

