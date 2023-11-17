"""
Serves Dash app for viewing and filtering participant (meta)data for imaging and phenotypic tasks from a given dataset.
App accepts and parses a user-uploaded bagel.csv file (assumed to be generated by mr_proc) as input.
"""

import dash_bootstrap_components as dbc
import pandas as pd
from dash import ALL, Dash, ctx, dcc, html
from dash.dependencies import Input, Output, State

from . import plotting as plot
from . import utility as util
from .layout import DEFAULT_DATASET_NAME, construct_layout, upload_buttons

EMPTY_FIGURE_PROPS = {"data": [], "layout": {}, "frames": []}

app = Dash(
    __name__, external_stylesheets=[dbc.themes.FLATLY, dbc.icons.BOOTSTRAP]
)
server = app.server

app.layout = construct_layout()


@app.callback(
    [
        Output("dataset-name-modal", "is_open"),
        Output("summary-title", "children"),
        Output("dataset-name-input", "value"),
    ],
    [
        Input("memory-overview", "data"),
        Input("submit-name", "n_clicks"),
    ],
    [
        State("dataset-name-modal", "is_open"),
        State("dataset-name-input", "value"),
    ],
    prevent_initial_call=True,
)
def toggle_dataset_name_dialog(
    parsed_data, submit_clicks, is_open, name_value
):
    """Toggles a popup window for user to enter a dataset name when the data store changes."""
    if parsed_data is not None:
        if name_value not in [None, ""]:
            return not is_open, name_value, None
        return not is_open, DEFAULT_DATASET_NAME, None

    return is_open, None, None


@app.callback(
    [
        Output("memory-filename", "data"),
        Output("memory-sessions", "data"),
        Output("memory-overview", "data"),
        Output("memory-pipelines", "data"),
        Output("upload-message", "children"),
        Output("interactive-datatable", "export_format"),
    ],
    Input({"type": "upload-data", "index": ALL, "btn_idx": ALL}, "contents"),
    State({"type": "upload-data", "index": ALL, "btn_idx": ALL}, "filename"),
    prevent_initial_call=True,
)
def process_bagel(contents, filenames):
    """
    From the contents of a correctly-formatted uploaded .csv file, parse and store (1) the pipeline overview data as a dataframe,
    and (2) pipeline-specific metadata as individual dataframes within a dict.
    Returns any errors encountered during input file processing as a user-friendly message.
    """
    filename = filenames[ctx.triggered_id.btn_idx]
    try:
        bagel, upload_error = util.parse_csv_contents(
            contents=ctx.triggered[0]["value"],
            filename=filename,
            schema=ctx.triggered_id.index,
        )
        if upload_error is None:
            session_list = bagel["session"].unique().tolist()
            overview_df = util.get_pipelines_overview(
                bagel=bagel, schema=ctx.triggered_id.index
            )
            pipelines_dict = util.extract_pipelines(
                bagel=bagel, schema=ctx.triggered_id.index
            )
    except Exception as exc:
        print(exc)  # for debugging
        upload_error = "Something went wrong while processing this file."

    if upload_error is not None:
        return (
            filename,
            None,
            None,
            None,
            f"Error: {upload_error}",
            "none",
        )

    # Change orientation of pipeline dataframe dictionary to enable storage as JSON data
    for key in pipelines_dict:
        pipelines_dict[key] = pipelines_dict[key].to_dict("records")

    return (
        filename,
        session_list,
        {
            "type": ctx.triggered_id.index,
            "data": overview_df.to_dict("records"),
        },
        pipelines_dict,
        None,
        "csv",
    )


@app.callback(
    Output("upload-buttons", "children"),
    Input("memory-filename", "data"),
    prevent_initial_call=True,
)
def reset_upload_buttons(memory_filename):
    """
    Resets upload buttons to their initial state when any new file is uploaded.

    Upload components need to be manually replaced to clear contents,
    otherwise previously uploaded imaging/pheno bagels cannot be re-uploaded
    (e.g. if a user uploads pheno_bagel.csv, then imaging_bagel.csv, then pheno_bagel.csv again)
    see https://github.com/plotly/dash-core-components/issues/816
    """
    return upload_buttons()


@app.callback(
    [
        Output("dataset-summary", "children"),
        Output("dataset-summary-card", "style"),
        Output("column-count", "children"),
    ],
    Input("memory-overview", "data"),
    prevent_initial_call=True,
)
def display_dataset_metadata(parsed_data):
    """When successfully uploaded data changes, update summary info of dataset."""
    if parsed_data is None:
        return None, {"display": "none"}, None

    overview_df = pd.DataFrame.from_dict(parsed_data.get("data"))

    return (
        util.construct_summary_str(overview_df),
        {"display": "block"},
        f"Total number of columns: {len(overview_df.columns)}",
    )


@app.callback(
    [
        Output("session-dropdown", "options"),
        Output("advanced-filter-form", "style"),
    ],
    Input("memory-overview", "data"),
    State("memory-sessions", "data"),
    prevent_initial_call=True,
)
def update_session_filter(parsed_data, session_list):
    """When uploaded data changes, update the unique session options and visibility of the session filter dropdown."""
    if parsed_data is None:
        return [], {"display": "none"}

    session_opts = [{"label": ses, "value": ses} for ses in session_list]

    return session_opts, {"display": "block"}


@app.callback(
    Output("pipeline-dropdown-container", "children"),
    Input("memory-pipelines", "data"),
    State("memory-overview", "data"),
    prevent_initial_call=True,
)
def create_pipeline_status_dropdowns(pipelines_dict, parsed_data):
    """
    Generates a dropdown filter with status options for each unique pipeline in the input csv,
    and disables the native datatable filter UI for the corresponding columns in the datatable.
    """
    pipeline_dropdowns = []

    if pipelines_dict is None or parsed_data.get("type") == "phenotypic":
        return pipeline_dropdowns

    for pipeline in pipelines_dict:
        new_pipeline_status_dropdown = dbc.Col(
            [
                dbc.Label(
                    pipeline,
                    className="mb-0",
                ),
                dcc.Dropdown(
                    id={
                        "type": "pipeline-status-dropdown",
                        "index": pipeline,
                    },
                    options=list(util.PIPE_COMPLETE_STATUS_SHORT_DESC.keys()),
                    placeholder="Filter by status...",
                ),
            ]
        )
        pipeline_dropdowns.append(new_pipeline_status_dropdown)

    return pipeline_dropdowns


@app.callback(
    [
        Output("interactive-datatable", "columns"),
        Output("interactive-datatable", "data"),
    ],
    [
        Input("memory-overview", "data"),
        Input("session-dropdown", "value"),
        Input("select-operator", "value"),
        Input({"type": "pipeline-status-dropdown", "index": ALL}, "value"),
        State("memory-pipelines", "data"),
    ],
)
def update_outputs(
    parsed_data,
    session_values,
    session_operator,
    status_values,
    pipelines_dict,
):
    if parsed_data is None:
        return None, None

    data = pd.DataFrame.from_dict(parsed_data.get("data"))

    if session_values or any(v is not None for v in status_values):
        # NOTE: The order in which pipeline-specific dropdowns are added to the layout is determined by the
        # order of pipelines in the pipeline-specific data store (see callback that generates the dropdowns).
        # As a result, the dropdown values passed to a callback will also follow this same pipeline order.
        pipeline_selected_filters = dict(
            zip(pipelines_dict.keys(), status_values)
        )
        data = util.filter_records(
            data=data,
            session_values=session_values,
            operator_value=session_operator,
            status_values=pipeline_selected_filters,
        )
    tbl_columns = [
        {"name": i, "id": i, "hideable": True} for i in data.columns
    ]
    tbl_data = data.to_dict("records")

    return tbl_columns, tbl_data


@app.callback(
    [
        Output("matching-participants", "children"),
        Output("matching-records", "children"),
    ],
    [
        Input("interactive-datatable", "columns"),
        Input("interactive-datatable", "derived_virtual_data"),
    ],
)
def update_matching_rows(columns, virtual_data):
    """
    If the visible data in the datatable changes, update counts of
    unique participants and records shown.

    When no filter (built-in or dropdown-based) has been applied,
    this count will be the same as the total number of participants
    in the dataset.
    """
    # calculate participant count for active table as long as datatable columns exist
    if columns is not None and columns != []:
        active_df = pd.DataFrame.from_dict(virtual_data)
        return (
            f"Participants matching filter: {util.count_unique_subjects(active_df)}",
            f"Records matching filter: {util.count_unique_records(active_df)}",
        )

    return "", ""


@app.callback(
    [
        Output("input-filename", "children"),
        Output("interactive-datatable", "filter_query"),
        Output("session-dropdown", "value"),
        Output("phenotypic-column-plotting-dropdown", "value"),
        Output("session-toggle-switch", "value"),
    ],
    Input("memory-filename", "data"),
    prevent_initial_call=True,
)
def reset_selections(filename):
    """
    If file contents change (i.e., selected new CSV for upload), reset displayed file name and selection values related to data filtering or plotting.
    Reset will occur regardless of whether there is an issue processing the selected file.
    """
    return f"Input file: {filename}", "", "", None, False


@app.callback(
    [
        Output("fig-pipeline-status-all-ses", "figure"),
        Output("fig-pipeline-status-all-ses", "style"),
        Output("processing-status-legend", "style"),
    ],
    Input("memory-overview", "data"),
    State("memory-sessions", "data"),
    prevent_initial_call=True,
)
def generate_overview_status_fig_for_participants(parsed_data, session_list):
    """
    If new dataset uploaded, generate stacked bar plot of pipeline_complete statuses per session,
    grouped by pipeline. Provides overview of the number of participants with each status in a given session,
    per processing pipeline.
    """
    if parsed_data is not None and parsed_data.get("type") != "phenotypic":
        return (
            plot.plot_pipeline_status_by_participants(
                pd.DataFrame.from_dict(parsed_data.get("data")), session_list
            ),
            {"display": "block"},
            {"display": "block"},
        )

    return EMPTY_FIGURE_PROPS, {"display": "none"}, {"display": "none"}


@app.callback(
    [
        Output("fig-pipeline-status", "figure"),
        Output("fig-pipeline-status", "style"),
    ],
    Input(
        "interactive-datatable", "data"
    ),  # Input not triggered by datatable frontend filtering
    State("memory-pipelines", "data"),
    State("memory-overview", "data"),
    prevent_initial_call=True,
)
def update_overview_status_fig_for_records(data, pipelines_dict, parsed_data):
    """
    When visible data in the overview datatable is updated (excluding built-in frontend datatable filtering
    but including custom component filtering), generate stacked bar plot of pipeline_complete statuses aggregated
    by pipeline. Counts of statuses in plot thus correspond to unique records (unique participant-session
    combinations).
    """
    if data is None or parsed_data.get("type") == "phenotypic":
        return EMPTY_FIGURE_PROPS, {"display": "none"}

    data_df = pd.DataFrame.from_dict(data)

    if not data_df.empty:
        status_counts = (
            plot.transform_active_data_to_long(data_df)
            .groupby(["pipeline_name", "pipeline_complete"])
            .size()
            .reset_index(name="records")
        )
    else:
        status_counts = plot.populate_empty_records_pipeline_status_plot(
            pipelines=pipelines_dict.keys(),
            statuses=util.PIPE_COMPLETE_STATUS_SHORT_DESC.keys(),
        )

    return plot.plot_pipeline_status_by_records(status_counts), {
        "display": "block"
    }


@app.callback(
    [
        Output("phenotypic-plotting-form", "style"),
        Output("phenotypic-column-plotting-dropdown", "options"),
    ],
    Input("memory-overview", "data"),
    prevent_initial_call=True,
)
def display_phenotypic_column_dropdown(parsed_data):
    """When phenotypic data is uploaded, display and populate dropdown to select column to plot."""
    if parsed_data is None or parsed_data.get("type") != "phenotypic":
        return {"display": "none"}, []

    column_options = []
    for column in pd.DataFrame.from_dict(parsed_data.get("data")):
        # exclude unique participant identifier columns from visualization
        if column not in [
            "participant_id",
            "bids_id",
        ]:  # TODO: Consider storing these column names in a constant
            column_options.append({"label": column, "value": column})

    return {"display": "block"}, column_options


@app.callback(
    [
        Output("fig-column-histogram", "figure"),
        Output("fig-column-histogram", "style"),
    ],
    [
        Input("phenotypic-column-plotting-dropdown", "value"),
        Input("interactive-datatable", "derived_virtual_data"),
        Input("session-toggle-switch", "value"),
    ],
    State("memory-overview", "data"),
    prevent_initial_call=True,
)
def plot_phenotypic_column(
    selected_column: str,
    virtual_data: list,
    session_switch_value: bool,
    parsed_data: dict,
):
    """When a column is selected from the dropdown, generate a histogram of the column values."""
    if selected_column is None or parsed_data.get("type") != "phenotypic":
        return EMPTY_FIGURE_PROPS, {"display": "none"}

    # If no data is visible in the datatable (i.e., zero matches), create an empty version of the dataframe (preserving the column names)
    # to supply to the plotting function. This ensures that an empty plot will be generated with the correct x-axis title.
    if not virtual_data:
        data_to_plot = pd.DataFrame.from_dict(parsed_data.get("data")).iloc[
            0:0
        ]
    else:
        data_to_plot = virtual_data

    if session_switch_value:
        color = "session"
    else:
        color = None

    return plot.plot_phenotypic_column_histogram(
        pd.DataFrame.from_dict(data_to_plot), selected_column, color
    ), {"display": "block"}


@app.callback(
    [
        Output("column-summary-title", "children"),
        Output("column-summary", "children"),
        Output("column-summary-card", "style"),
    ],
    [
        Input("phenotypic-column-plotting-dropdown", "value"),
        Input("interactive-datatable", "derived_virtual_data"),
    ],
    State("memory-overview", "data"),
    prevent_initial_call=True,
)
def generate_column_summary(
    selected_column: str, virtual_data: list, parsed_data: dict
):
    """When a column is selected from the dropdown, generate summary stats of the column values."""
    if selected_column is None or parsed_data.get("type") != "phenotypic":
        return None, None, {"display": "none"}

    # If no data is visible in the datatable (i.e., zero matches), return an informative message
    if not virtual_data:
        return (
            selected_column,
            html.I("No matching records available to compute value summary"),
            {"display": "block"},
        )

    column_data = pd.DataFrame.from_dict(virtual_data)[selected_column]
    return (
        selected_column,
        util.generate_column_summary_str(column_data),
        {"display": "block"},
    )


@app.callback(
    Output("session-toggle-switch", "style"),
    Input("phenotypic-column-plotting-dropdown", "value"),
    prevent_initial_call=True,
)
def display_session_switch(selected_column: str):
    """When a column is selected from the dropdown, display switch to enable/disable stratifying the plot by session."""
    if selected_column is None:
        return {"display": "none"}

    return {"display": "block"}


if __name__ == "__main__":
    app.run_server(debug=True)