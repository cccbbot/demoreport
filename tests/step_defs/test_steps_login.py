#!/usr/bin/python
# -*- coding: UTF-8 -*-

from pytest_bdd import scenarios, given, when, then, parsers
from pages.login_page import LoginPage
from playwright.sync_api import Page, expect


# 加载 Feature 文件
scenarios('../features/login.feature')

@given('I am on the login page')
def open_login_page(page: Page):
    login_page = LoginPage(page)
    login_page.load()

@when(parsers.parse('I login with user "{username}" and password "{password}"'))
def login_action(page: Page, username, password):
    login_page = LoginPage(page)
    login_page.login(username, password)

@then('I should be redirected to inventory page')
def verify_inventory(page: Page):
    expect(page).to_have_url("https://www.saucedemo.com/inventory.html")

@then(parsers.parse('I should see error message "{error_msg}"'))
def verify_error(page: Page, error_msg):
    login_page = LoginPage(page)
    login_page.verify_error_message(error_msg)