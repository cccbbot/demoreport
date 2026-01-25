#@skip
Feature: 1.4. Furniture PLP Functionality
  As a user of VidaXL
  I want to filter and sort furniture products
  So that I can find the items I need efficiently

  Background:
    Given I open the VidaXL furniture page

  # 覆盖需求 1 & 附件 2: PLP页面排序类型测试
  @skip
  Scenario: 1.4.1 Sort products on PLP
    When I open the sorting dropdown
    And I select "Price low-high" sorting option
    Then the products should be sorted by price in ascending order

  # 覆盖需求 2 & 附件 3: Filter弹窗排序、类目遍历、Reset测试
  @skip
  Scenario: 1.4.2 Filter modal functionality and category traversal
    When I click the "Filters" button
    Then the filter modal should be visible
    When I expand the "Categories" section in modal
    And I traverse through categories, sub-categories, and deep-level categories
    And I select a random category filter
    And I click "Show products" button
    And I click "Clear all filters"
    Then the URL should not contain filter parameters

  # 覆盖需求 3 & 附件 4: PLP中Inline类目、Type、Price测试
  @p3
  Scenario: 1.4.3 Inline PLP filters (Category, Price, Type)
    When I interact with the inline "Categories" dropdown
    And I select a sub-category from the inline dropdown
    When I interact with the inline "Price" dropdown
    And I set a price range
    When I interact with the inline "Type" dropdown
    Then the product results should update