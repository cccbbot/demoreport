@p0 @smoke
Feature: Login Functionality
    As a user, I want to login to Swag Labs so that I can buy products.

    Scenario: Successful Login with standard user
        Given I am on the login page
        When I login with user "standard_user" and password "secret_sauce"
        Then I should be redirected to inventory page

    @p1 @regression
    Scenario Outline: Failed Login attempts
        Given I am on the login page
        When I login with user "<username>" and password "<password>"
        Then I should see error message "<error_msg>"

        Examples:
        | username        | password     | error_msg                                 |
        | locked_out_user | secret_sauce | Sorry, this user has been locked out.     |
        | invalid_user    | wrong_pass   | Username and password do not match any user in this service |