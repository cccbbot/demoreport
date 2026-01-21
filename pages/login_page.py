#!/usr/bin/python
# -*- coding: UTF-8 -*-

from pages.base_page import BasePage
from playwright.sync_api import expect

class LoginPage(BasePage):
    URL = "https://www.saucedemo.com/"
    USERNAME_INPUT = "#user-name"
    PASSWORD_INPUT = "#password"
    LOGIN_BTN = "#login-button"
    ERROR_MSG = "[data-test='error']"

    def load(self):
        self.navigate(self.URL)

    def login(self, username, password):
        self.input_text(self.USERNAME_INPUT, username, "Username Input")
        self.input_text(self.PASSWORD_INPUT, password, "Password Input")
        self.click(self.LOGIN_BTN, "Login Button")

    def verify_error_message(self, expected_msg):
        expect(self.page.locator(self.ERROR_MSG)).to_contain_text(expected_msg)