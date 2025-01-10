import numpy as np
import pandas as pd
import pytest

import digest.plotting as plot
import digest.utility as util
from digest.utility import PRIMARY_SESSION_COL


@pytest.mark.parametrize(
    "filename",
    ["imagingbagel.csv", "imagingbagel.txt", "imagingbagel.tsv.csv"],
)
def test_invalid_filetype_returns_informative_error(filename):
    toy_upload_contents = "stand-in for a base64 encoded file contents string"
    bagel, upload_error = util.load_file_from_contents(
        filename, toy_upload_contents
    )

    assert bagel is None
    assert "Invalid file type" in upload_error


@pytest.mark.parametrize(
    "original_df,duplicates_df",
    [
        (
            pd.DataFrame(
                {
                    "participant_id": ["sub-1", "sub-1", "sub-2", "sub-2"],
                    "session_id": [1, 2, 1, 2],
                    "assessment_name": ["moca", "moca", "moca", "moca"],
                    "assessment_score": [21.0, 24.0, np.nan, 24.0],
                }
            ),
            # Have to specify column dtypes as well because the df will otherwise not evaluate as equal to an empty subset of above df
            pd.DataFrame(
                {
                    "participant_id": pd.Series([], dtype="object"),
                    "session_id": pd.Series([], dtype="int64"),
                    "assessment_name": pd.Series([], dtype="object"),
                    "assessment_score": pd.Series([], dtype="float64"),
                }
            ),
        ),
        (
            pd.DataFrame(
                {
                    "participant_id": ["sub-1", "sub-1", "sub-2", "sub-2"],
                    "session_id": [1, 1, 1, 2],
                    "assessment_name": ["moca", "moca", "moca", "moca"],
                    "assessment_score": [21.0, 24.0, np.nan, 24.0],
                }
            ),
            pd.DataFrame(
                {
                    "participant_id": ["sub-1", "sub-1"],
                    "session_id": [1, 1],
                    "assessment_name": ["moca", "moca"],
                    "assessment_score": [21.0, 24.0],
                }
            ),
        ),
        (
            pd.DataFrame(
                {
                    "participant_id": ["sub-1", "sub-1", "sub-2", "sub-2"],
                    "session_id": [np.nan, np.nan, 1, 2],
                    "assessment_name": ["moca", "moca", "moca", "moca"],
                    "assessment_score": [21.0, 24.0, np.nan, 24.0],
                }
            ),
            pd.DataFrame(
                {
                    "participant_id": ["sub-1", "sub-1"],
                    "session_id": [np.nan, np.nan],
                    "assessment_name": ["moca", "moca"],
                    "assessment_score": [21.0, 24.0],
                }
            ),
        ),
        # TODO: Revisit this example when we want to handle NaN values in identifier columns differently (e.g., see https://github.com/neurobagel/digest/issues/20)
        (
            pd.DataFrame(
                {
                    "participant_id": ["sub-1", "sub-1", "sub-2", "sub-2"],
                    "session_id": [1, np.nan, 1, 2],
                    "assessment_name": ["moca", "moca", "moca", "moca"],
                    "assessment_score": [21.0, 24.0, np.nan, 24.0],
                }
            ),
            pd.DataFrame(
                {
                    "participant_id": pd.Series([], dtype="object"),
                    "session_id": pd.Series([], dtype="float64"),
                    "assessment_name": pd.Series([], dtype="object"),
                    "assessment_score": pd.Series([], dtype="float64"),
                }
            ),
        ),
    ],
)
def test_get_duplicate_entries(original_df, duplicates_df):
    """Test that get_duplicate_entries() returns a dataframe containing the duplicate entries in a given dataframe."""

    unique_value_id_columns = [
        "participant_id",
        "session_id",
        "assessment_name",
    ]
    assert util.get_duplicate_entries(
        data=original_df, subset=unique_value_id_columns
    ).equals(duplicates_df)


@pytest.mark.parametrize(
    "bagel_path,schema,expected_columns,expected_n_records",
    [
        (
            "example_imaging_diff-pipeline-subjects.tsv",
            "imaging",
            [
                "participant_id",
                "session_id",
                "fmriprep-20.2.7-default",
                "freesurfer-6.0.1-default",
                "freesurfer-7.3.2-default",
            ],
            6,
        ),
        (
            "example_imaging.tsv",
            "imaging",
            [
                "participant_id",
                "bids_participant_id",
                "session_id",
                "bids_session_id",
                "fmriprep-20.2.7-step1",
                "fmriprep-20.2.7-step2",
                "fmriprep-23.1.3-default",
                "freesurfer-7.3.2-default",
            ],
            4,
        ),
        (
            "example_phenotypic.tsv",
            "phenotypic",
            [
                "participant_id",
                "bids_participant_id",
                "session_id",
                "group",
                "moca_total",
                "updrs_3_total",
            ],
            7,
        ),
    ],
)
def test_get_pipelines_overview(
    bagels_path, bagel_path, schema, expected_columns, expected_n_records
):
    """
    Smoke test that get_pipelines_overview() returns a dataframe with the expected columns and number of participant-session rows
    after reshaping data into a wide format.
    """
    bagel = pd.read_csv(bagels_path / bagel_path, sep="\t")
    bagel[PRIMARY_SESSION_COL] = bagel[PRIMARY_SESSION_COL].astype(str)
    overview_df = util.get_pipelines_overview(bagel=bagel, schema=schema)

    assert overview_df.columns.tolist() == expected_columns
    assert len(overview_df) == expected_n_records


@pytest.mark.parametrize(
    "bagel,expected_overview_df",
    [
        (
            # TODO: Update once https://github.com/neurobagel/digest/issues/20 is addressed
            pd.DataFrame(
                {
                    "participant_id": ["sub-1", "sub-1", "sub-2", "sub-2"],
                    "session_id": [1, np.nan, 1, 2],
                    "assessment_name": ["moca", "moca", "moca", "moca"],
                    "assessment_score": [21.0, 24.0, np.nan, 24.0],
                }
            ),
            pd.DataFrame(
                {
                    "participant_id": ["sub-1", "sub-1", "sub-2", "sub-2"],
                    "session_id": ["1.0", "nan", "1.0", "2.0"],
                    "moca": [21.0, 24.0, np.nan, 24.0],
                }
            ),
        ),
        (
            # This example also provides a test that original session order is preserved
            pd.DataFrame(
                {
                    "participant_id": [
                        "sub-1",
                        "sub-1",
                        "sub-1",
                        "sub-1",
                        "sub-1",
                    ],
                    "session_id": [
                        "intake",
                        "baseline",
                        "follow-up",
                        "intake",
                        "baseline",
                    ],
                    "assessment_name": [
                        "moca",
                        "moca",
                        "moca",
                        "updrs",
                        "updrs",
                    ],
                    "assessment_score": [np.nan, 24.0, np.nan, 12, 12],
                }
            ),
            pd.DataFrame(
                {
                    "participant_id": ["sub-1", "sub-1", "sub-1"],
                    "session_id": ["intake", "baseline", "follow-up"],
                    "moca": [np.nan, 24.0, np.nan],
                    "updrs": [12.0, 12.0, np.nan],
                }
            ),
        ),
    ],
)
def test_get_pipelines_overview_handles_nan_correctly(
    bagel, expected_overview_df
):
    """Test that get_pipelines_overview() handles NaN values in the original long-format data as expected."""
    bagel[PRIMARY_SESSION_COL] = bagel[PRIMARY_SESSION_COL].astype(str)
    overview_df = util.get_pipelines_overview(bagel=bagel, schema="phenotypic")

    assert overview_df.equals(expected_overview_df), overview_df


def test_reset_column_dtypes():
    """
    Test that reset_column_dtypes() infers more appropriate dtypes for columns whose values were erroneously stored as strings,
    and that the 'session' column is always converted to strings (object dtype).
    """
    pheno_overview_df = pd.DataFrame(
        {
            "participant_id": ["sub-1", "sub-2", "sub-3"],
            "session_id": [1, 1, 1],
            "group": ["PD", "PD", "PD"],
            "moca_total": ["21", "24", np.nan],
            "moca_total_status": ["true", "true", "false"],
        }
    )

    pheno_overview_df_retyped = util.reset_column_dtypes(pheno_overview_df)

    assert pheno_overview_df_retyped["participant_id"].dtype == "object"
    assert pheno_overview_df_retyped["session_id"].dtype == "object"
    assert pheno_overview_df_retyped["group"].dtype == "object"
    assert pheno_overview_df_retyped["moca_total"].dtype == "float64"
    assert pheno_overview_df_retyped["moca_total_status"].dtype == "bool"


def test_wrap_df_column_values():
    """Test that wrap_df_column_values() wraps values of a column which are longer than the specified length."""
    df = pd.DataFrame(
        {
            "updrs_p3_hy": [
                "Stage 0: Asymptomatic",
                "Stage 1: Unilateral involvement only",
                "Stage 2: Bilateral involvement without impairment of balance",
            ]
        }
    )
    wrapped_df = plot.wrap_df_column_values(df, "updrs_p3_hy", 30)
    assert all("<br>" in value for value in wrapped_df["updrs_p3_hy"][1:3])
    assert "<br>" not in wrapped_df["updrs_p3_hy"][0]


@pytest.mark.parametrize(
    "column,nonmissing,missing,stats",
    [
        ("group", "3/3", "0/3", ["unique values", "most common value"]),
        ("moca_total", "2/3", "1/3", ["mean", "std", "min", "median", "max"]),
        (
            "moca_total_status",
            "3/3",
            "0/3",
            ["mean", "std", "min", "median", "max"],
        ),
    ],
)
def test_generate_column_summary_str(column, nonmissing, missing, stats):
    """Test that generate_column_summary_str() returns a string with the correct summary statistics for a given column."""
    pheno_overview_df = pd.DataFrame(
        {
            "participant_id": ["sub-1", "sub-2", "sub-3"],
            "session_id": [
                "1",
                "1",
                "1",
            ],  # the session column is always converted to strings for the dashboard
            "group": ["PD", "PD", "PD"],
            "moca_total": [21, 24, np.nan],
            "moca_total_status": [True, True, False],
        }
    )
    column_summary = util.generate_column_summary_str(
        pheno_overview_df[column]
    )

    assert [stat in column_summary for stat in stats]
    assert f"non-missing values: {nonmissing}" in column_summary
    assert f"missing values: {missing}" in column_summary
