import base64
import io
import json
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

SCHEMAS_PATH = Path(__file__).absolute().parents[1] / "schemas"
PIPE_COMPLETE_STATUS_SHORT_DESC = {
    "SUCCESS": "All stages of pipeline finished successfully (all expected output files present).",
    "FAIL": "At least one stage of the pipeline failed.",
    "UNAVAILABLE": "Pipeline has not yet been run (output directory not available).",
}


def construct_legend_str(status_desc: dict) -> str:
    """From a dictionary, constructs a legend-style string with multiple lines in the format of key: value."""
    return "\n".join(
        [f"{status}: {desc}" for status, desc in status_desc.items()]
    )


def construct_summary_str(data: pd.DataFrame) -> str:
    """Creates summary of key counts for dataset."""
    return f"""Total number of participants: {count_unique_subjects(data)}
Total number of unique records (participant-session pairs): {count_unique_records(data)}
Total number of unique sessions: {data["session"].nunique()}"""


def get_required_bagel_columns() -> list:
    """Returns names of required columns from the bagel schema."""
    with open(SCHEMAS_PATH / "bagel_schema.json", "r") as file:
        schema = json.load(file)

    required_columns = []
    for col_category, cols in schema.items():
        for col, props in cols.items():
            if props["IsRequired"]:
                required_columns.append(col)

    return required_columns


# TODO: When possible values per column have been finalized (waiting on mr_proc),
# validate that each column only has acceptable values
def get_missing_required_columns(bagel: pd.DataFrame) -> set:
    """Identifies any missing required columns in bagel schema."""
    missing_req_columns = set(get_required_bagel_columns()).difference(
        bagel.columns
    )

    return missing_req_columns


def extract_pipelines(bagel: pd.DataFrame) -> dict:
    """Get data for each unique pipeline in the aggregate input as an individual labelled dataframe."""
    pipelines_dict = {}

    pipelines = bagel.groupby(["pipeline_name", "pipeline_version"])
    for (name, version), pipeline in pipelines:
        label = f"{name}-{version}"
        # per pipeline, rows are sorted in case participants/sessions are out of order
        pipelines_dict[label] = (
            pipeline.sort_values(["participant_id", "session"])
            .drop(["pipeline_name", "pipeline_version"], axis=1)
            .reset_index(drop=True)
        )

    return pipelines_dict


def get_id_columns(data: pd.DataFrame) -> list:
    """Returns names of columns which identify a given participant record"""
    return (
        ["participant_id", "bids_id", "session"]
        if "bids_id" in data.columns
        else ["participant_id", "session"]
    )


def are_subjects_same_across_pipelines(bagel: pd.DataFrame) -> bool:
    """Checks if subjects and sessions are the same across pipelines in the input."""
    pipelines_dict = extract_pipelines(bagel)

    pipeline_subject_sessions = [
        df.loc[:, get_id_columns(bagel)] for df in pipelines_dict.values()
    ]

    return all(
        pipeline.equals(pipeline_subject_sessions[0])
        for pipeline in pipeline_subject_sessions
    )


def count_unique_subjects(data: pd.DataFrame) -> int:
    return (
        data["participant_id"].nunique()
        if "participant_id" in data.columns
        else 0
    )


def count_unique_records(data: pd.DataFrame) -> int:
    """Returns number of unique participant-session pairs."""
    if set(["participant_id", "session"]).issubset(data.columns):
        return data[["participant_id", "session"]].drop_duplicates().shape[0]
    return 0


def get_pipelines_overview(bagel: pd.DataFrame) -> pd.DataFrame:
    """
    Constructs a dataframe containing global statuses of pipelines in bagel.csv
    (based on "pipeline_complete" column) for each participant and session.
    """
    pipeline_complete_df = bagel.pivot(
        index=get_id_columns(bagel),
        columns=["pipeline_name", "pipeline_version"],
        values="pipeline_complete",
    )
    pipeline_complete_df.columns = [
        # for neatness, rename pipeline-specific columns from "(name, version)" to "{name}-{version}"
        "-".join(tup)
        for tup in pipeline_complete_df.columns.to_flat_index()
    ]
    pipeline_complete_df = pipeline_complete_df.reindex(
        sorted(pipeline_complete_df.columns), axis=1
    )
    pipeline_complete_df.reset_index(inplace=True)

    return pipeline_complete_df


# TODO: Refactor csv parsing into its own function separate from the overview dataframe generation
def parse_csv_contents(
    contents, filename
) -> Tuple[Optional[pd.DataFrame], Optional[dict], Optional[str]]:
    """
    Returns
    -------
    pd.DataFrame or None
        Dataframe containing global statuses of pipelines for each participant-session.
    dict or None
        Dictionary containing labels and dataframes for each pipeline.
    str or None
        Error raised during parsing of the input, if applicable.
    """
    content_type, content_string = contents.split(",")
    decoded = base64.b64decode(content_string)

    error_msg = None
    if ".csv" in filename:
        bagel = pd.read_csv(io.StringIO(decoded.decode("utf-8")))
        if len(missing_req_cols := get_missing_required_columns(bagel)) > 0:
            error_msg = f"The selected .csv is missing the following required metadata columns: {missing_req_cols}."
        elif not are_subjects_same_across_pipelines(bagel):
            error_msg = "The pipelines in bagel.csv do not have the same number of subjects and sessions."
        else:
            overview_df = get_pipelines_overview(bagel=bagel)
            pipelines_dict = extract_pipelines(bagel=bagel)
    else:
        error_msg = "Input file is not a .csv file."

    if error_msg is not None:
        return None, None, error_msg

    return overview_df, pipelines_dict, None


def filter_records(
    data: pd.DataFrame,
    session_values: list,
    operator_value: str,
    status_values: dict,
) -> pd.DataFrame:
    """
    Returns dataframe filtered for data corresponding to the specified sessions
    and pipeline statuses. The selected operator value only has effect when >=1 session
    has been selected, and determines whether the filter should be applied at the subject level
    (all; all selected sessions should be present, with pipeline statuses of each matching the filter)
    or at the session level (any; any selected session with pipeline statuses matching the filter).

    Note: This functionality is meant to complement the datatable's built-in
    column-wise filtering UI, since the filtering syntax does not readily support
    intuitive queries for multiple specific values in a column, or multi-column queries.
    """
    pipeline_queries = [
        f"`{pipeline}` == {repr(status_value)}"
        for pipeline, status_value in status_values.items()
        if status_value is not None
    ]

    if not session_values:
        query = " and ".join(pipeline_queries)
    elif operator_value == "AND":
        matching_subs = []
        for sub_id, sub in data.groupby("participant_id"):
            if all(
                session in sub["session"].unique()
                for session in session_values
            ):
                if all(
                    not sub.query(
                        " and ".join(
                            [f"session == {session}"] + pipeline_queries
                        )
                    ).empty
                    for session in session_values
                ):
                    matching_subs.append(sub_id)
        query = f"participant_id in {matching_subs} and session in {session_values}"
    else:
        if operator_value == "OR":
            query = " and ".join(
                [f"session in {session_values}"] + pipeline_queries
            )

    data = data.query(query)

    return data
