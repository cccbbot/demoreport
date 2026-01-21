import os
import pytest
import time
import sys
import platform
import json
import base64
from datetime import datetime
from jinja2 import Environment

# ===========================
# 1. Test Result Collection & Data Structure
# ===========================

class TestSessionReport:
    def __init__(self):
        self.features = {}
        self.start_time = time.time()
        self.duration = 0

        # Case Stats
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.error = 0
        self.skipped = 0

        # Feature Stats
        self.feature_total = 0
        self.feature_passed = 0
        self.feature_failed = 0
        self.feature_error = 0
        self.feature_skipped = 0

    def add_result(self, report, item):
        # Get Feature Name
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
                "status": "passed"  # Default
            }

        # Log parsing
        log_content = []

        # 1. Error Trace
        if report.longrepr:
            log_content.append(f"=== Error Trace ===\n{report.longrepr}")
        else:
            if report.outcome == 'passed':
                log_content.append("=== Execution Result ===\nTest Passed successfully.")
            elif report.outcome == 'skipped':
                log_content.append(f"=== Skip Reason ===\n{report.longrepr if report.longrepr else 'Skipped'}")

        # 2. Captured Stdout/Stderr
        for section_name, content in report.sections:
            log_content.append(f"\n=== {section_name} ===\n{content}")

        full_log = "\n".join(log_content)

        # Status Logic
        status = report.outcome  # passed, failed, skipped
        if status == "failed" and report.when != "call":
            status = "error"  # Failures in Setup/Teardown are treated as Errors

        screenshot = getattr(report, "screenshot", None)

        # Build Scenario Result
        scenario_result = {
            "name": scenario_name,
            "status": status,
            "duration": round(report.duration, 4),
            "log": full_log,
            "nodeid": item.nodeid,
            "screenshot": screenshot
        }

        # Update Feature Stats
        self.features[feature_name]["scenarios"].append(scenario_result)
        self.features[feature_name]["stats"]["total"] += 1
        self.features[feature_name]["stats"][status] += 1

        # Update Global Stats
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
    """
    Attempt to capture screenshot from fixture (driver/page)
    Supports Selenium (driver) and Playwright (page)
    """
    screenshot_base64 = None
    driver = None

    # 1. Try to get from funcargs (fixtures)
    for name in ["driver", "browser", "page", "web_driver"]:
        if name in item.funcargs:
            driver = item.funcargs[name]
            break

    # 2. Try to get from class instance
    if not driver and item.instance:
        if hasattr(item.instance, "driver"):
            driver = item.instance.driver

    if driver:
        try:
            # Selenium / Appium
            if hasattr(driver, "get_screenshot_as_base64"):
                screenshot_base64 = driver.get_screenshot_as_base64()
            # Playwright
            elif hasattr(driver, "screenshot"):
                img_bytes = driver.screenshot()
                screenshot_base64 = base64.b64encode(img_bytes).decode('utf-8')
        except Exception as e:
            print(f"WARNING: Screenshot failed - {e}")

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

    # === Feature Status Logic ===
    report_data.feature_total = len(report_data.features)

    for f_name, f_data in report_data.features.items():
        stats = f_data["stats"]
        # Priority: Fail > Error > Skip (All Skipped) > Pass
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
# 3. HTML Template (English)
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
        .bg-error { background-color: #fd7e14 !important; color: white; } /* Orange for Error */
        .bg-skip { background-color: #6c757d !important; color: white; }

        .text-pass { color: #28a745; }
        .text-fail { color: #dc3545; }
        .text-error { color: #fd7e14; }
        .text-skip { color: #6c757d; }

        /* Summary Boxes */
        .summary-box { padding: 15px; border-radius: 6px; color: white; text-align: center; }
        .summary-box h3 { margin: 0; font-weight: bold; font-size: 2em; }
        .summary-box small { text-transform: uppercase; font-size: 0.8em; opacity: 0.9; }

        /* Table Styles */
        .table { margin-bottom: 0; }
        .table thead th { background-color: #343a40; color: white; border: none; font-weight: 500; }

        /* Feature Row Styles */
        .feature-row { font-weight: 600; cursor: pointer; transition: background-color 0.2s; }
        /* Feature Row Backgrounds based on status */
        .feature-row.status-passed { background-color: #e8f5e9; border-left: 5px solid #28a745; }
        .feature-row.status-failed { background-color: #fde8e8; border-left: 5px solid #dc3545; }
        .feature-row.status-error { background-color: #fff3cd; border-left: 5px solid #fd7e14; }
        .feature-row.status-skipped { background-color: #f8f9fa; border-left: 5px solid #6c757d; }

        .status-badge { padding: 4px 8px; border-radius: 4px; font-size: 0.75em; font-weight: bold; min-width: 60px; display: inline-block; text-align: center; color: white;}

        /* Log Box */
        .log-box { background: #2b2b2b; color: #f1f1f1; padding: 15px; border-radius: 4px; font-family: Consolas, monospace; white-space: pre-wrap; font-size: 0.9em; max-height: 500px; overflow-y: auto; display: none; margin: 10px 40px; border: 1px solid #444; }

        .screenshot-box { margin-top: 15px; border-top: 1px dashed #555; padding-top: 10px; }
        .screenshot-placeholder { background: #333; color: #aaa; padding: 20px; text-align: center; border: 1px dashed #666; border-radius: 4px; }

        .chart-container { height: 350px; }

        /* Filter Buttons */
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
        <!-- Feature Stats -->
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

        <!-- Case Stats -->
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
        <div class="card-header d-flex justify-content-between align-items-center">
            <span>Test Details</span>
            <!-- Filter Buttons -->
            <div class="btn-group" role="group">
                <button type="button" class="btn btn-outline-secondary btn-filter active" onclick="filterTable('all')">TOTAL</button>
                <button type="button" class="btn btn-outline-success btn-filter" onclick="filterTable('passed')">PASSED</button>
                <button type="button" class="btn btn-outline-danger btn-filter" onclick="filterTable('failed')">FAILED</button>
                <button type="button" class="btn btn-outline-warning btn-filter" onclick="filterTable('error')">ERROR</button>
                <button type="button" class="btn btn-outline-secondary btn-filter" onclick="filterTable('skipped')">SKIPPED</button>
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
                    <!-- Feature Row (Clickable for collapse) -->
                    <tr class="feature-row status-{{ feature.status }}" 
                        data-bs-toggle="collapse" data-bs-target="#collapse-{{ loop.index }}">
                        <td>
                            <strong>{{ feature_name }}</strong>
                        </td>
                        <td>
                            <!-- Feature Summary Badge -->
                            {% if feature.status == 'passed' %} <span class="badge bg-pass">ALL PASS</span>
                            {% elif feature.status == 'skipped' %} <span class="badge bg-skip">SKIPPED</span>
                            {% else %}
                                <span class="badge bg-danger">
                                    P:{{ feature.stats.passed }} F:{{ feature.stats.failed }} E:{{ feature.stats.error }} S:{{ feature.stats.skipped }}
                                </span>
                            {% endif %}
                        </td>
                        <td>-</td>
                        <td><small class="text-muted">Click to expand/collapse</small></td>
                    </tr>

                    <!-- Scenarios Container -->
                    <tr class="collapse show" id="collapse-{{ loop.index }}">
                        <td colspan="4" class="p-0">
                            <table class="table mb-0 table-borderless bg-white">
                                {% for scenario in feature.scenarios %}
                                <!-- Scenario Row -->
                                <tr class="scenario-row status-{{ scenario.status }}">
                                    <td style="width: 50%; padding-left: 40px;">
                                        {{ scenario.name }}
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
                                                onclick="toggleLog('log-{{ loop.index }}-{{ scenario.nodeid|hash }}')">
                                            Details
                                        </button>
                                    </td>
                                </tr>
                                <!-- Log Row (Hidden by default) -->
                                <tr class="scenario-row status-{{ scenario.status }}" style="border-top: none;">
                                    <td colspan="4" class="p-0">
                                        <div id="log-{{ loop.index }}-{{ scenario.nodeid|hash }}" class="log-box">
                                            <div>{{ scenario.log | e }}</div>

                                            <!-- Screenshot Area -->
                                            {% if scenario.status in ['failed', 'error'] %}
                                            <div class="screenshot-box">
                                                <h6>Failure Screenshot</h6>
                                                {% if scenario.screenshot %}
                                                    <div class="mt-2">
                                                        <a href="data:image/png;base64,{{ scenario.screenshot }}" target="_blank" title="Click to view original image in new window">
                                                            <img src="data:image/png;base64,{{ scenario.screenshot }}" 
                                                                 class="img-fluid border rounded" 
                                                                 style="max-width: 600px; max-height: 400px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);" />
                                                        </a>
                                                        <div class="small text-muted mt-1">Click image to enlarge</div>
                                                    </div>
                                                {% else %}
                                                    <div class="alert alert-light border border-warning text-warning mt-2" role="alert">
                                                        <small>
                                                            <strong>No screenshot captured.</strong><br>
                                                            Possible reasons:<br>
                                                            1. Fixture name is not <code>driver</code>, <code>page</code>, or <code>browser</code>.<br>
                                                            2. Browser instance is closed.<br>
                                                            3. Error occurred during setup/teardown.
                                                        </small>
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
    // 1. Chart - Features
    var chartFeatures = echarts.init(document.getElementById('chart-features'));
    var optionFeatures = {
        tooltip: { trigger: 'item' },
        legend: { bottom: '0%' },
        color: ['#28a745', '#dc3545', '#fd7e14', '#6c757d'], // Pass, Fail, Error, Skip
        series: [
            {
                name: 'Feature Status',
                type: 'pie',
                radius: ['40%', '70%'],
                avoidLabelOverlap: false,
                itemStyle: { borderRadius: 5, borderColor: '#fff', borderWidth: 2 },
                label: { show: false, position: 'center' },
                emphasis: { label: { show: true, fontSize: '20', fontWeight: 'bold' } },
                data: [
                    { value: {{ stats.feature_passed }}, name: 'Passed' },
                    { value: {{ stats.feature_failed }}, name: 'Failed' },
                    { value: {{ stats.feature_error }}, name: 'Error' },
                    { value: {{ stats.feature_skipped }}, name: 'Skipped' }
                ]
            }
        ]
    };
    chartFeatures.setOption(optionFeatures);

    // 2. Chart - Cases
    var chartCases = echarts.init(document.getElementById('chart-cases'));
    var optionCases = {
        tooltip: { trigger: 'item' },
        legend: { bottom: '0%' },
        color: ['#28a745', '#dc3545', '#fd7e14', '#6c757d'],
        series: [
            {
                name: 'Case Status',
                type: 'pie',
                radius: ['40%', '70%'],
                itemStyle: { borderRadius: 5, borderColor: '#fff', borderWidth: 2 },
                data: [
                    { value: {{ stats.passed }}, name: 'Passed' },
                    { value: {{ stats.failed }}, name: 'Failed' },
                    { value: {{ stats.error }}, name: 'Error' },
                    { value: {{ stats.skipped }}, name: 'Skipped' }
                ]
            }
        ]
    };
    chartCases.setOption(optionCases);

    // 3. Filter Logic
    function filterTable(status) {
        // Toggle Active Button
        document.querySelectorAll('.btn-filter').forEach(b => b.classList.remove('active'));
        event.target.classList.add('active');

        const rows = document.querySelectorAll('.scenario-row');
        rows.forEach(row => {
            const isLogRow = row.querySelector('.log-box') !== null;
            const logBox = row.querySelector('.log-box');

            let shouldShow = false;
            if (status === 'all') {
                shouldShow = true;
            } else {
                shouldShow = row.classList.contains('status-' + status);
            }

            if (shouldShow) {
                if (!isLogRow) {
                    row.style.display = ''; 
                } else {
                    if(logBox) logBox.style.display = 'none';
                    row.style.display = '';
                }
            } else {
                row.style.display = 'none';
            }
        });
    }

    function toggleLog(id) {
        var x = document.getElementById(id);
        if (x.style.display === "none" || x.style.display === "") {
            x.style.display = "block";
        } else {
            x.style.display = "none";
        }
    }

    window.addEventListener('resize', function() {
        chartFeatures.resize();
        chartCases.resize();
    });
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

    # Define filter
    def hash_filter(value):
        return abs(hash(value))

    # --- Core Logic ---
    # 1. Create Jinja2 Environment
    env = Environment()

    # 2. Register Filter
    env.filters['hash'] = hash_filter

    # 3. Load Template
    template = env.from_string(HTML_TEMPLATE)
    # ----------------

    html_content = template.render(
        features=report_data.features,
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