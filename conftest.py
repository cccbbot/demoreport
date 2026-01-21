import os
import pytest
import time
import sys
import platform
import base64
import logging
from datetime import datetime
from jinja2 import Environment


# ===========================
# 0. Logging Capture Setup
# ===========================

class StepLogHandler(logging.Handler):
    """
    自定义日志处理器，用于临时存储单个 Step 执行期间产生的日志
    """

    def __init__(self):
        super().__init__()
        self.records = []
        # 设置默认格式
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S'))

    def emit(self, record):
        try:
            msg = self.format(record)
            self.records.append(msg)
        except Exception:
            self.handleError(record)

    def reset(self):
        self.records = []


# 初始化全局 Handler
step_log_handler = StepLogHandler()
logging.getLogger().addHandler(step_log_handler)
# 确保捕获 INFO 及以上级别 (具体取决于用户 pytest.ini 配置，这里仅作为保底)
logging.getLogger().setLevel(logging.INFO)

# ===========================
# 1. Step Execution Cache & Hooks
# ===========================
step_execution_cache = {}


def get_step_cache(nodeid):
    if nodeid not in step_execution_cache:
        step_execution_cache[nodeid] = []
    return step_execution_cache[nodeid]


# --- Pytest-BDD Hooks ---

def pytest_bdd_before_scenario(request, feature, scenario):
    step_execution_cache[request.node.nodeid] = []


def pytest_bdd_before_step(request, feature, scenario, step, step_func):
    """Step 开始前清空日志缓冲区"""
    step_log_handler.reset()


def pytest_bdd_after_step(request, feature, scenario, step, step_func, step_func_args):
    """Step 结束后读取日志并保存"""
    cache = get_step_cache(request.node.nodeid)

    # 获取本次 Step 执行期间捕获的日志
    captured_logs = list(step_log_handler.records)

    cache.append({
        "keyword": step.keyword,
        "name": step.name,
        "status": "passed",
        "duration": 0,
        "logs": captured_logs  # <--- NEW: 保存日志列表
    })


def pytest_bdd_step_error(request, feature, scenario, step, step_func, step_func_args, exception):
    cache = get_step_cache(request.node.nodeid)

    # 即使报错，也保存已捕获的日志
    captured_logs = list(step_log_handler.records)

    cache.append({
        "keyword": step.keyword,
        "name": step.name,
        "status": "failed",
        "error": str(exception),
        "logs": captured_logs  # <--- NEW
    })


# ===========================
# 2. Test Result Collection
# ===========================

class TestSessionReport:
    def __init__(self):
        self.features = {}
        self.all_markers = set()
        self.start_time = time.time()
        self.duration = 0
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.error = 0
        self.skipped = 0
        self.feature_total = 0
        self.feature_passed = 0
        self.feature_failed = 0
        self.feature_error = 0
        self.feature_skipped = 0

    def add_result(self, report, item):
        feature_name = "Unknown Feature"
        if hasattr(item, "_obj") and hasattr(item._obj, "__scenario__"):
            feature_name = item._obj.__scenario__.feature.name
        else:
            feature_name = item.nodeid.split("::")[0]

        scenario_name = item.name

        if feature_name not in self.features:
            self.features[feature_name] = {
                "name": feature_name,
                "scenarios": [],
                "stats": {"total": 0, "passed": 0, "failed": 0, "error": 0, "skipped": 0},
                "status": "passed"
            }

        # Global Log
        log_content = []
        if report.longrepr:
            log_content.append(f"=== Error Trace ===\n{report.longrepr}")
        else:
            if report.outcome == 'passed':
                log_content.append("=== Execution Result ===\nTest Passed successfully.")
            elif report.outcome == 'skipped':
                log_content.append(f"=== Skip Reason ===\n{report.longrepr if report.longrepr else 'Skipped'}")

        for section_name, content in report.sections:
            log_content.append(f"\n=== {section_name} ===\n{content}")
        full_log = "\n".join(log_content)

        status = report.outcome
        if status == "failed" and report.when != "call":
            status = "error"

        screenshot = getattr(report, "screenshot", None)
        steps = step_execution_cache.get(item.nodeid, [])

        ignored_markers = {'parametrize', 'usefixtures', 'filterwarnings', 'skip', 'skipif', 'xfail',
                           'pytest_bdd_scenario'}
        item_markers = []
        for m in item.iter_markers():
            if m.name not in ignored_markers:
                item_markers.append(m.name)
                self.all_markers.add(m.name)

        scenario_result = {
            "name": scenario_name,
            "status": status,
            "duration": round(report.duration, 4),
            "log": full_log,
            "nodeid": item.nodeid,
            "screenshot": screenshot,
            "steps": steps,
            "markers": item_markers
        }

        self.features[feature_name]["scenarios"].append(scenario_result)
        self.features[feature_name]["stats"]["total"] += 1
        self.features[feature_name]["stats"][status] += 1

        self.total += 1
        if status == "passed":
            self.passed += 1
        elif status == "failed":
            self.failed += 1
        elif status == "error":
            self.error += 1
        elif status == "skipped":
            self.skipped += 1


def _capture_screenshot(item):
    screenshot_base64 = None
    driver = None
    for name in ["driver", "browser", "page", "web_driver"]:
        if name in item.funcargs:
            driver = item.funcargs[name]
            break
    if not driver and item.instance:
        if hasattr(item.instance, "driver"):
            driver = item.instance.driver
    if driver:
        try:
            if hasattr(driver, "get_screenshot_as_base64"):
                screenshot_base64 = driver.get_screenshot_as_base64()
            elif hasattr(driver, "screenshot"):
                import base64
                img_bytes = driver.screenshot()
                screenshot_base64 = base64.b64encode(img_bytes).decode('utf-8')
        except Exception:
            pass
    return screenshot_base64


report_data = TestSessionReport()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" or (report.when in ["setup", "teardown"] and report.outcome != "passed"):
        if report.outcome in ["failed", "skipped"] and report.when == "call":
            report.screenshot = _capture_screenshot(item)
        else:
            report.screenshot = None
        report_data.add_result(report, item)


def pytest_sessionfinish(session, exitstatus):
    report_data.duration = round(time.time() - report_data.start_time, 2)
    report_data.feature_total = len(report_data.features)
    for f_name, f_data in report_data.features.items():
        stats = f_data["stats"]
        if stats["failed"] > 0:
            f_data["status"] = "failed"
            report_data.feature_failed += 1
        elif stats["error"] > 0:
            f_data["status"] = "error"
            report_data.feature_error += 1
        elif stats["skipped"] == stats["total"] and stats["total"] > 0:
            f_data["status"] = "skipped"
            report_data.feature_skipped += 1
        else:
            f_data["status"] = "passed"
            report_data.feature_passed += 1
    generate_html_report()


# ===========================
# 3. HTML Template
# ===========================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Automation Test Report</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        body { background-color: #f4f6f9; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .container-fluid { padding: 20px; max-width: 1600px; }
        .card { border: none; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; border-radius: 6px; }
        .card-header { background-color: #fff; border-bottom: 1px solid #eee; font-weight: 600; padding: 12px 20px; }

        /* Status Colors */
        .bg-pass { background-color: #28a745 !important; color: white; }
        .bg-fail { background-color: #dc3545 !important; color: white; }
        .bg-error { background-color: #fd7e14 !important; color: white; }
        .bg-skip { background-color: #6c757d !important; color: white; }

        .text-pass { color: #28a745; }
        .text-fail { color: #dc3545; }
        .text-error { color: #fd7e14; }
        .text-skip { color: #6c757d; }

        .summary-box { padding: 15px; border-radius: 6px; color: white; text-align: center; }
        .summary-box h3 { margin: 0; font-weight: bold; font-size: 2em; }
        .summary-box small { text-transform: uppercase; font-size: 0.8em; opacity: 0.9; }

        .table { margin-bottom: 0; }
        .table thead th { background-color: #343a40; color: white; border: none; font-weight: 500; }

        .feature-row { font-weight: 600; cursor: pointer; transition: background-color 0.2s; }
        .feature-row.status-passed { background-color: #e8f5e9; border-left: 5px solid #28a745; }
        .feature-row.status-failed { background-color: #fde8e8; border-left: 5px solid #dc3545; }
        .feature-row.status-error { background-color: #fff3cd; border-left: 5px solid #fd7e14; }
        .feature-row.status-skipped { background-color: #f8f9fa; border-left: 5px solid #6c757d; }

        .status-badge { padding: 4px 8px; border-radius: 4px; font-size: 0.75em; font-weight: bold; min-width: 60px; display: inline-block; text-align: center; color: white;}
        .marker-badge { font-size: 0.7em; margin-left: 5px; opacity: 0.8; }

        /* Log & Steps Styles */
        .log-box { background: #2b2b2b; color: #f1f1f1; padding: 15px; border-radius: 4px; font-family: Consolas, monospace; white-space: pre-wrap; font-size: 0.9em; max-height: 500px; overflow-y: auto; display: none; margin: 10px 40px; border: 1px solid #444; }

        .step-container { margin: 10px 40px; background: #fff; padding: 15px; border-radius: 6px; border: 1px solid #eee; display: none; }
        .step-item { padding: 12px 0; border-bottom: 1px solid #f0f0f0; display: flex; align-items: start; }
        .step-item:last-child { border-bottom: none; }

        .step-keyword { font-weight: bold; margin-right: 12px; min-width: 60px; text-align: right; color: #0d6efd; padding-top: 0px; }
        .step-content { flex-grow: 1; }
        .step-name { color: #333; font-weight: 500; }
        .step-status { margin-left: 10px; font-size: 0.8em; padding-top: 0px; }

        /* NEW: Step Logs Styles */
        .step-logs { 
            margin-top: 6px; 
            background-color: #f8f9fa; 
            border-left: 3px solid #dee2e6;
            padding: 5px 10px;
            font-family: Consolas, 'Courier New', monospace;
            font-size: 0.85em;
            color: #555;
            border-radius: 2px;
        }
        .log-line { display: block; white-space: pre-wrap; line-height: 1.4; }

        .screenshot-box { margin-top: 15px; border-top: 1px dashed #555; padding-top: 10px; }
        .chart-container { height: 350px; }
        .btn-filter.active { box-shadow: inset 0 3px 5px rgba(0,0,0,0.125); }
    </style>
</head>
<body>

<div class="container-fluid">
    <!-- Environment Info -->
    <div class="card">
        <div class="card-body py-2">
            <div class="row align-items-center text-secondary small">
                <div class="col-auto"><strong>Python:</strong> {{ env.python_version }}</div>
                <div class="col-auto"><strong>Platform:</strong> {{ env.platform }}</div>
                <div class="col-auto"><strong>Start:</strong> {{ env.start_time }}</div>
                <div class="col-auto"><strong>Duration:</strong> {{ env.duration }}s</div>
            </div>
        </div>
    </div>

    <!-- Dashboard Stats Area -->
    <div class="row">
        <div class="col-md-6">
            <div class="card h-100">
                <div class="card-header">Feature Statistics</div>
                <div class="card-body">
                    <div class="row g-2 mb-3">
                        <div class="col"><div class="summary-box bg-primary"><h3>{{ stats.feature_total }}</h3><small>Total</small></div></div>
                        <div class="col"><div class="summary-box bg-pass"><h3>{{ stats.feature_passed }}</h3><small>Pass</small></div></div>
                        <div class="col"><div class="summary-box bg-fail"><h3>{{ stats.feature_failed }}</h3><small>Fail</small></div></div>
                        <div class="col"><div class="summary-box bg-error"><h3>{{ stats.feature_error }}</h3><small>Error</small></div></div>
                        <div class="col"><div class="summary-box bg-skip"><h3>{{ stats.feature_skipped }}</h3><small>Skip</small></div></div>
                    </div>
                    <div id="chart-features" class="chart-container"></div>
                </div>
            </div>
        </div>
        <div class="col-md-6">
            <div class="card h-100">
                <div class="card-header">Test Case Statistics</div>
                <div class="card-body">
                    <div class="row g-2 mb-3">
                        <div class="col"><div class="summary-box bg-primary"><h3>{{ stats.total }}</h3><small>Total</small></div></div>
                        <div class="col"><div class="summary-box bg-pass"><h3>{{ stats.passed }}</h3><small>Pass</small></div></div>
                        <div class="col"><div class="summary-box bg-fail"><h3>{{ stats.failed }}</h3><small>Fail</small></div></div>
                        <div class="col"><div class="summary-box bg-error"><h3>{{ stats.error }}</h3><small>Error</small></div></div>
                        <div class="col"><div class="summary-box bg-skip"><h3>{{ stats.skipped }}</h3><small>Skip</small></div></div>
                    </div>
                    <div id="chart-cases" class="chart-container"></div>
                </div>
            </div>
        </div>
    </div>

    <!-- Detailed Report -->
    <div class="card">
        <div class="card-header d-flex flex-wrap justify-content-between align-items-center">
            <span class="mb-2 mb-md-0">Test Details</span>

            <div class="d-flex gap-2 align-items-center">
                <!-- 1. Marker Filter -->
                <select id="markerFilter" class="form-select form-select-sm" style="width: 150px;" onchange="applyFilter()">
                    <option value="all">All Markers</option>
                    {% for m in all_markers %}
                    <option value="{{ m }}">{{ m }}</option>
                    {% endfor %}
                </select>

                <!-- 2. Search Box -->
                <div class="input-group input-group-sm" style="width: 250px;">
                    <span class="input-group-text bg-white fw-bold">Search</span>
                    <input type="text" id="searchInput" class="form-control" placeholder="Name..." onkeyup="applyFilter()">
                </div>

                <!-- 3. Status Buttons -->
                <div class="btn-group btn-group-sm" role="group">
                    <button type="button" class="btn btn-outline-secondary btn-filter active" onclick="setFilterStatus('all')">TOTAL</button>
                    <button type="button" class="btn btn-outline-success btn-filter" onclick="setFilterStatus('passed')">PASSED</button>
                    <button type="button" class="btn btn-outline-danger btn-filter" onclick="setFilterStatus('failed')">FAILED</button>
                    <button type="button" class="btn btn-outline-warning btn-filter" onclick="setFilterStatus('error')">ERROR</button>
                    <button type="button" class="btn btn-outline-secondary btn-filter" onclick="setFilterStatus('skipped')">SKIPPED</button>
                </div>
            </div>
        </div>

        <div class="card-body p-0">
            <table class="table table-hover mb-0" id="result-table">
                <thead>
                    <tr>
                        <th style="width: 50%">Feature / Scenario</th>
                        <th style="width: 15%">Status</th>
                        <th style="width: 15%">Duration (s)</th>
                        <th style="width: 20%">Action</th>
                    </tr>
                </thead>
                <tbody>
                    {% for feature_name, feature in features.items() %}
                    <!-- Feature Row -->
                    <tr class="feature-row status-{{ feature.status }}" 
                        data-feature-name="{{ feature_name | lower }}"
                        data-bs-toggle="collapse" data-bs-target="#collapse-{{ loop.index }}">
                        <td><strong>{{ feature_name }}</strong></td>
                        <td>
                            {% if feature.status == 'passed' %} <span class="badge bg-pass">ALL PASS</span>
                            {% elif feature.status == 'skipped' %} <span class="badge bg-skip">SKIPPED</span>
                            {% else %}
                                <span class="badge bg-danger">
                                    P:{{ feature.stats.passed }} F:{{ feature.stats.failed }} E:{{ feature.stats.error }} S:{{ feature.stats.skipped }}
                                </span>
                            {% endif %}
                        </td>
                        <td>-</td>
                        <td><small class="text-muted">Expand/Collapse</small></td>
                    </tr>

                    <!-- Scenarios Container -->
                    <tr class="collapse show" id="collapse-{{ loop.index }}">
                        <td colspan="4" class="p-0">
                            <table class="table mb-0 table-borderless bg-white">
                                {% for scenario in feature.scenarios %}
                                <!-- Scenario Row -->
                                <tr class="scenario-row status-{{ scenario.status }}" 
                                    data-scenario-name="{{ scenario.name | lower }}"
                                    data-feature-parent="{{ feature_name | lower }}"
                                    data-markers="{{ scenario.markers | join(' ') }}">

                                    <td style="width: 50%; padding-left: 40px;">
                                        {{ scenario.name }}
                                        {% for m in scenario.markers %}
                                            <span class="badge bg-secondary marker-badge">{{ m }}</span>
                                        {% endfor %}
                                        <div class="text-muted small" style="font-size: 0.8em;">{{ scenario.nodeid }}</div>
                                    </td>
                                    <td style="width: 15%">
                                        <span class="status-badge 
                                            {% if scenario.status == 'passed' %}bg-pass
                                            {% elif scenario.status == 'failed' %}bg-fail
                                            {% elif scenario.status == 'error' %}bg-error
                                            {% else %}bg-skip{% endif %}">
                                            {{ scenario.status|upper }}
                                        </span>
                                    </td>
                                    <td style="width: 15%">{{ scenario.duration }}s</td>
                                    <td style="width: 20%">
                                        <button class="btn btn-sm btn-outline-secondary" style="font-size: 0.8em;" 
                                                onclick="toggleDetails('{{ loop.index }}-{{ scenario.nodeid|hash }}')">
                                            Details
                                        </button>
                                    </td>
                                </tr>

                                <!-- Steps & Logs Row -->
                                <tr class="details-row" id="details-row-{{ loop.index }}-{{ scenario.nodeid|hash }}" style="display:none; border-top: none;">
                                    <td colspan="4" class="p-0">

                                        <!-- 1. BDD Steps Visualization -->
                                        {% if scenario.steps %}
                                        <div class="step-container" style="display: block;">
                                            <h6 class="border-bottom pb-2">Execution Steps</h6>
                                            {% for step in scenario.steps %}
                                            <div class="step-item">
                                                <div class="step-keyword">{{ step.keyword }}</div>

                                                <div class="step-content">
                                                    <div class="step-name">{{ step.name }}</div>

                                                    <!-- NEW: Per-Step Logs -->
                                                    {% if step.logs %}
                                                    <div class="step-logs">
                                                        {% for log in step.logs %}
                                                        <span class="log-line">{{ log }}</span>
                                                        {% endfor %}
                                                    </div>
                                                    {% endif %}
                                                </div>

                                                <div class="step-status">
                                                    {% if step.status == 'passed' %}
                                                        <span class="badge bg-pass">PASS</span>
                                                    {% elif step.status == 'failed' %}
                                                        <span class="badge bg-fail">FAIL</span>
                                                        <div class="text-danger small mt-1">{{ step.error }}</div>
                                                    {% endif %}
                                                </div>
                                            </div>
                                            {% endfor %}
                                        </div>
                                        {% endif %}

                                        <!-- 2. Logs & Screenshots -->
                                        <div class="log-box" style="display: block;">
                                            <div>{{ scenario.log | e }}</div>

                                            {% if scenario.status in ['failed', 'error'] %}
                                            <div class="screenshot-box">
                                                <h6>Failure Screenshot</h6>
                                                {% if scenario.screenshot %}
                                                    <div class="mt-2">
                                                        <a href="data:image/png;base64,{{ scenario.screenshot }}" target="_blank">
                                                            <img src="data:image/png;base64,{{ scenario.screenshot }}" 
                                                                 class="img-fluid border rounded" 
                                                                 style="max-width: 600px; max-height: 400px;" />
                                                        </a>
                                                        <div class="small text-muted mt-1">Click to enlarge</div>
                                                    </div>
                                                {% else %}
                                                    <div class="alert alert-light border border-warning text-warning mt-2">
                                                        <small>No screenshot captured (Check 'driver' fixture).</small>
                                                    </div>
                                                {% endif %}
                                            </div>
                                            {% endif %}
                                        </div>
                                    </td>
                                </tr>
                                {% endfor %}
                            </table>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
    // ECharts Initialization
    var chartFeatures = echarts.init(document.getElementById('chart-features'));
    var optionFeatures = {
        tooltip: { trigger: 'item' },
        legend: { bottom: '0%' },
        color: ['#28a745', '#dc3545', '#fd7e14', '#6c757d'],
        series: [{
            name: 'Feature Status', type: 'pie', radius: ['40%', '70%'],
            avoidLabelOverlap: false, itemStyle: { borderRadius: 5, borderColor: '#fff', borderWidth: 2 },
            label: { show: false, position: 'center' },
            emphasis: { label: { show: true, fontSize: '20', fontWeight: 'bold' } },
            data: [
                { value: {{ stats.feature_passed }}, name: 'Passed' },
                { value: {{ stats.feature_failed }}, name: 'Failed' },
                { value: {{ stats.feature_error }}, name: 'Error' },
                { value: {{ stats.feature_skipped }}, name: 'Skipped' }
            ]
        }]
    };
    chartFeatures.setOption(optionFeatures);

    var chartCases = echarts.init(document.getElementById('chart-cases'));
    var optionCases = {
        tooltip: { trigger: 'item' },
        legend: { bottom: '0%' },
        color: ['#28a745', '#dc3545', '#fd7e14', '#6c757d'],
        series: [{
            name: 'Case Status', type: 'pie', radius: ['40%', '70%'],
            itemStyle: { borderRadius: 5, borderColor: '#fff', borderWidth: 2 },
            data: [
                { value: {{ stats.passed }}, name: 'Passed' },
                { value: {{ stats.failed }}, name: 'Failed' },
                { value: {{ stats.error }}, name: 'Error' },
                { value: {{ stats.skipped }}, name: 'Skipped' }
            ]
        }]
    };
    chartCases.setOption(optionCases);

    window.addEventListener('resize', function() {
        chartFeatures.resize();
        chartCases.resize();
    });

    // === COMBINED FILTER LOGIC ===
    var currentStatusFilter = 'all';

    function setFilterStatus(status) {
        currentStatusFilter = status;
        document.querySelectorAll('.btn-filter').forEach(b => b.classList.remove('active'));
        event.target.classList.add('active');
        applyFilter();
    }

    function applyFilter() {
        var searchTerm = document.getElementById('searchInput').value.toLowerCase();
        var selectedMarker = document.getElementById('markerFilter').value;
        var status = currentStatusFilter;

        const featureRows = document.querySelectorAll('.feature-row');
        const scenarioRows = document.querySelectorAll('.scenario-row');

        scenarioRows.forEach(row => {
            var sName = row.getAttribute('data-scenario-name');
            var fName = row.getAttribute('data-feature-parent');
            var sMarkers = row.getAttribute('data-markers') || "";

            var rowStatus = '';
            if (row.classList.contains('status-passed')) rowStatus = 'passed';
            else if (row.classList.contains('status-failed')) rowStatus = 'failed';
            else if (row.classList.contains('status-error')) rowStatus = 'error';
            else rowStatus = 'skipped';

            var statusMatch = (status === 'all') || (status === rowStatus);
            if (status === 'failed') statusMatch = (rowStatus === 'failed'); 
            else if (status === 'error') statusMatch = (rowStatus === 'error');

            var textMatch = (sName.includes(searchTerm) || fName.includes(searchTerm));
            var markerMatch = (selectedMarker === 'all') || sMarkers.includes(selectedMarker);

            if (statusMatch && textMatch && markerMatch) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
                var nextRow = row.nextElementSibling;
                if(nextRow && nextRow.classList.contains('details-row')) {
                    nextRow.style.display = 'none'; 
                }
            }
        });

        featureRows.forEach(fRow => {
            var featureName = fRow.getAttribute('data-feature-name');
            var visibleSiblings = document.querySelectorAll(`.scenario-row[data-feature-parent="${featureName}"]`);
            var hasVisibleChildren = false;
            visibleSiblings.forEach(s => {
                if(s.style.display !== 'none') hasVisibleChildren = true;
            });

            if (hasVisibleChildren) {
                fRow.style.display = '';
            } else {
                fRow.style.display = 'none';
            }
        });
    }

    function toggleDetails(idSuffix) {
        var rowId = 'details-row-' + idSuffix;
        var row = document.getElementById(rowId);
        if (row.style.display === "none" || row.style.display === "") {
            row.style.display = "table-row";
        } else {
            row.style.display = "none";
        }
    }
</script>
</body>
</html>
"""


def generate_html_report():
    env_info = {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "start_time": datetime.fromtimestamp(report_data.start_time).strftime('%Y-%m-%d %H:%M:%S'),
        "duration": report_data.duration
    }

    def hash_filter(value):
        return abs(hash(value))

    env = Environment()
    env.filters['hash'] = hash_filter
    template = env.from_string(HTML_TEMPLATE)

    html_content = template.render(
        features=report_data.features,
        all_markers=sorted(list(report_data.all_markers)),
        stats={
            "total": report_data.total,
            "passed": report_data.passed,
            "failed": report_data.failed,
            "error": report_data.error,
            "skipped": report_data.skipped,
            "feature_total": report_data.feature_total,
            "feature_passed": report_data.feature_passed,
            "feature_failed": report_data.feature_failed,
            "feature_error": report_data.feature_error,
            "feature_skipped": report_data.feature_skipped
        },
        env=env_info
    )

    with open("report.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\nReport Generated: {os.path.abspath('report.html')}")