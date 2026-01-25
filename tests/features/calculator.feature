Feature: 1.3 计算器功能
  验证计算器的基本加减法功能

  @smoke
  Scenario: 1.3.3 两个数相加
    Given 我有两个数字 10 和 20
    When 我执行加法
    Then 结果应该是 30

  @smoke
  Scenario: 1.3.2 两个数相减 (故意失败演示)
    Given 我有两个数字 50 和 20
    When 我执行减法
    Then 结果应该是 10