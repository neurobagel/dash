import os

import pytest
from dash.testing.application_runners import import_app


@pytest.fixture(scope="function")
def test_server(dash_duo):
    app = import_app("digest.app")
    dash_duo.start_server(app)

    yield dash_duo


@pytest.mark.parametrize(
    # NOTE: parameterization necessary here to use a fresh server instance per upload test
    # (otherwise, time to clear output elements from previous uploads may cause erroneous test passing)
    "valid_bagel,bagel_type,expected_elements,unexpected_elements",
    [
        (
            "example_imaging.tsv",
            "imaging",
            ["#fig-pipeline-status-all-ses"],
            ["#phenotypic-plotting-form"],
        ),
        (
            "example_phenotypic.tsv",
            "phenotypic",
            # TODO: Check specifically for a session filter form instead of #advanced-filter-form,
            # since latter is a larger container that also contains pipeline-specific dropdowns for imaging data
            ["#advanced-filter-form", "#phenotypic-plotting-form"],
            ["#fig-pipeline-status-all-ses"],
        ),
    ],
)
def test_001_upload_valid_bagel(
    test_server,
    bagels_path,
    valid_bagel,
    bagel_type,
    expected_elements,
    unexpected_elements,
):
    """
    Smoke test (e2e) for uploading a valid bagel input.
    Tests that after bagel upload, the input filename and a set of UI elements expected for the uploaded data type are displayed,
    and also that a set of elements not expected for the uploaded data type are not displayed.
    """
    # Find element that contains input link. Utilize the web driver to get the element.
    upload = test_server.driver.find_element(
        "xpath",
        f"""//*[contains(@id,'"index":"{bagel_type}","type":"upload-data"')]/div/input""",
    )

    upload.send_keys(os.path.realpath(os.path.join(bagels_path, valid_bagel)))
    test_server.wait_for_contains_text(
        "#input-filename", valid_bagel, timeout=4
    )

    for expected_element in expected_elements:
        test_server.wait_for_style_to_equal(
            expected_element, "display", "block", timeout=4
        )

    for unexpected_element in unexpected_elements:
        test_server.wait_for_style_to_equal(
            unexpected_element, "display", "none", timeout=4
        )

    assert "Error" not in test_server.find_element("#output-data-upload").text
    assert (
        test_server.get_logs() == []
    ), "browser console should contain no error"


def test_002_upload_invalid_imaging_bagel(test_server, bagels_path):
    """
    Given an invalid uploaded imaging bagel, displays an informative error message and updates the filename.
    NOTE: Different example files are iterated over instead of parameterized for efficiency,
    to reuse the same (function scoped) server instance.
    """
    invalid_input_output = {
        "example_imaging_missing-col.tsv": "missing the following required imaging metadata columns: {'pipeline_step'}",
        "example_phenotypic.tsv": "missing the following required imaging metadata columns",
    }

    upload = test_server.driver.find_element(
        "xpath",
        """//*[contains(@id,'"index":"imaging","type":"upload-data"')]/div/input""",
    )

    for invalid_bagel, err in invalid_input_output.items():
        upload.send_keys(
            os.path.realpath(os.path.join(bagels_path, invalid_bagel))
        )
        test_server.wait_for_contains_text(
            "#input-filename", invalid_bagel, timeout=4
        )
        test_server.wait_for_contains_text(
            "#output-data-upload", err, timeout=4
        )
        assert err in test_server.find_element("#output-data-upload").text

    assert (
        test_server.get_logs() == []
    ), "browser console should contain no error"


def test_003_upload_invalid_phenotypic_bagel(test_server, bagels_path):
    """Given an invalid uploaded phenotypic bagel, displays an informative error message."""
    err = "missing the following required phenotypic metadata columns"
    upload = test_server.driver.find_element(
        "xpath",
        """//*[contains(@id,'"index":"phenotypic","type":"upload-data"')]/div/input""",
    )

    upload.send_keys(
        os.path.realpath(os.path.join(bagels_path, "example_imaging.tsv"))
    )
    test_server.wait_for_contains_text("#output-data-upload", err, timeout=4)
    assert err in test_server.find_element("#output-data-upload").text

    assert (
        test_server.get_logs() == []
    ), "browser console should contain no error"


def test_004_phenotypic_col_selection_generates_visualization(
    test_server, bagels_path
):
    """
    Given a valid phenotypic bagel, displays a dropdown that, in response to a column option selection,
    displays a histogram and a value summary card for that column without errors.
    """
    upload = test_server.driver.find_element(
        "xpath",
        """//*[contains(@id,'"index":"phenotypic","type":"upload-data"')]/div/input""",
    )
    upload.send_keys(
        os.path.realpath(os.path.join(bagels_path, "example_phenotypic.tsv"))
    )

    # Wait for dropdown container
    test_server.wait_for_style_to_equal(
        "#phenotypic-plotting-form", "display", "block", timeout=4
    )

    # Dismiss the dataset name modal first
    test_server.find_element("#submit-name").click()

    # Select the dropdown option using a neat but somehow undocumented method - see https://github.com/plotly/dash/issues/858
    test_server.select_dcc_dropdown(
        "#phenotypic-column-plotting-dropdown", value="moca_total"
    )

    test_server.wait_for_style_to_equal(
        "#fig-column-histogram", "display", "block", timeout=4
    )
    test_server.wait_for_style_to_equal(
        "#column-summary-card", "display", "block", timeout=4
    )
    assert (
        "moca_total" in test_server.find_element("#fig-column-histogram").text
    )
    assert (
        "moca_total" in test_server.find_element("#column-summary-card").text
    )

    assert (
        test_server.get_logs() == []
    ), "browser console should contain no error"
