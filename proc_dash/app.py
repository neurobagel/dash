"""
Constructs Dash app for viewing and filtering statuses of processing pipelines for a given dataset.
App accepts and parses a user-uploaded bagel.csv file (assumed to be generated by mr_proc) as input.
"""

import dash_bootstrap_components as dbc
import pandas as pd

import proc_dash.plotting as plot
import proc_dash.utility as util
from dash import ALL, Dash, ctx, dash_table, dcc, html, no_update
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

EMPTY_FIGURE_PROPS = {"data": [], "layout": {}, "frames": []}
DEFAULT_NAME = "Dataset"

app = Dash(__name__, external_stylesheets=[dbc.themes.FLATLY])
server = app.server

# Navbar UI component
navbar = dbc.Navbar(
    dbc.Container(
        [
            dbc.Row(
                dbc.Col(
                    dbc.NavbarBrand(
                        "Neuroimaging Derivatives Status Dashboard"
                    )
                ),
                align="center",
            ),
            dbc.Row(
                dbc.Col(
                    dbc.Nav(
                        dbc.Button(
                            "View Code on GitHub",
                            outline=True,
                            color="light",
                            href="https://github.com/neurobagel/proc_dash",
                            # Turn off lowercase transformation for class .button in stylesheet
                            style={"textTransform": "none"},
                        ),
                        className="ml-auto",
                        navbar=True,
                    ),
                ),
                align="center",
            ),
        ],
        fluid=True,
    ),
    color="dark",
    dark=True,
)

upload = dcc.Upload(
    id="upload-data",
    children=dbc.Button(
        "Drag and Drop or Select .csv File", color="secondary"
    ),
    multiple=False,
)

sample_data = dbc.Button(
    "View sample input file",
    color="light",
    href="https://github.com/neurobagel/proc_dash/blob/main/tests/data/example_bagel.csv",
    target="_blank",  # open external site in new tab
)

dataset_name_dialog = dbc.Modal(
    children=[
        dbc.ModalHeader(
            dbc.ModalTitle("Enter the dataset name:"), close_button=False
        ),
        dbc.ModalBody(
            dbc.Input(
                id="dataset-name-input", placeholder=DEFAULT_NAME, type="text"
            )
        ),
        dbc.ModalFooter(
            [
                dcc.Markdown("*Tip: To skip, press Submit or ESC*"),
                dbc.Button(
                    "Submit", id="submit-name", className="ms-auto", n_clicks=0
                ),
            ]
        ),
    ],
    id="dataset-name-modal",
    is_open=False,
    backdrop="static",  # do not close dialog when user clicks elsewhere on screen
)

dataset_summary_card = dbc.Card(
    dbc.CardBody(
        [
            html.H5(
                children=DEFAULT_NAME,
                id="summary-title",
                className="card-title",
            ),
            html.P(
                id="dataset-summary",
                style={"whiteSpace": "pre"},  # preserve newlines
                className="card-text",
            ),
        ],
    ),
    id="dataset-summary-card",
    style={"display": "none"},
)

status_legend_card = dbc.Card(
    dbc.CardBody(
        [
            html.H5(
                "Processing status legend",
                className="card-title",
            ),
            html.P(
                children=util.construct_legend_str(
                    util.PIPE_COMPLETE_STATUS_SHORT_DESC
                ),
                style={"whiteSpace": "pre"},  # preserve newlines
                className="card-text",
            ),
        ]
    ),
)

overview_table = dash_table.DataTable(
    id="interactive-datatable",
    data=None,
    sort_action="native",
    sort_mode="multi",
    filter_action="native",
    page_size=50,
    # fixed_rows={"headers": True},
    style_table={"height": "300px", "overflowY": "auto"},
    style_cell={
        "fontSize": 13  # accounts for font size inflation by dbc theme
    },
    style_header={
        "position": "sticky",
        "top": 0,
    },  # Workaround to fixed_rows that does not impact column width. Could also specify widths in style_cell
    export_format="none",
)
# NOTE: Could cast columns to strings for the datatable to standardize filtering syntax,
# but this results in undesirable effects (e.g., if there is session 1 and session 11,
# a query for "1" would return both)

session_filter_form = dbc.Form(
    [
        # TODO: Put label and dropdown in same row
        html.Div(
            [
                dbc.Label(
                    "Filter by session(s):",
                    html_for="session-dropdown",
                    className="mb-0",
                ),
                dcc.Dropdown(
                    id="session-dropdown",
                    options=[],
                    multi=True,
                    placeholder="Select one or more available sessions to filter by",
                ),
            ],
            className="mb-2",  # Add margin to keep dropdowns spaced apart
        ),
        html.Div(
            [
                dbc.Label(
                    "Selection operator:",
                    html_for="select-operator",
                    className="mb-0",
                ),
                dcc.Dropdown(
                    id="select-operator",
                    options=[
                        {
                            "label": "AND",
                            "value": "AND",
                            "title": "All selected sessions are present and match the pipeline-level filter.",
                        },
                        {
                            "label": "OR",
                            "value": "OR",
                            "title": "Any selected session is present and matches the pipeline-level filter.",
                        },
                    ],
                    value="AND",
                    clearable=False,
                ),
            ],
            className="mb-2",
        ),
    ],
    id="session-filter-form",
    style={"display": "none"},
)

app.layout = html.Div(
    children=[
        navbar,
        dcc.Store(id="memory-overview"),
        dcc.Store(id="memory-pipelines"),
        html.Div(
            children=[upload, sample_data],
            style={"margin-top": "10px", "margin-bottom": "10px"},
            className="hstack gap-3",
        ),
        dataset_name_dialog,
        html.Div(
            id="output-data-upload",
            children=[
                html.H4(id="input-filename"),
                dbc.Row(
                    [
                        dbc.Col(
                            html.Div(
                                children=[
                                    html.Div(
                                        id="upload-message",  # NOTE: Temporary placeholder, to be removed once error alert elements are implemented
                                    ),
                                    html.Div(
                                        id="matching-participants",
                                    ),
                                    html.Div(
                                        id="matching-records",
                                        style={"margin-left": "15px"},
                                    ),
                                ],
                                style={"display": "inline-flex"},
                            ),
                            align="end",
                        ),
                        dbc.Col(
                            dataset_summary_card,
                        ),
                    ]
                ),
                overview_table,
            ],
            style={"margin-top": "10px", "margin-bottom": "10px"},
        ),
        dbc.Row(
            [
                dbc.Col(
                    session_filter_form,
                    width=3,
                ),
                dbc.Col(
                    dbc.Row(
                        id="pipeline-dropdown-container",
                        children=[],
                    )
                ),
            ]
        ),
        status_legend_card,
        dbc.Row(
            [
                # NOTE: Legend displayed for both graphs so that user can toggle visibility of status data
                dbc.Col(
                    dcc.Graph(
                        id="fig-pipeline-status", style={"display": "none"}
                    )
                ),
                dbc.Col(
                    dcc.Graph(
                        id="fig-pipeline-status-all-ses",
                        style={"display": "none"},
                    )
                ),
            ],
        ),
    ],
    style={"padding": "10px 10px 10px 10px"},
)


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
        return not is_open, DEFAULT_NAME, None

    return is_open, None, None


# TODO: Refactor session related operations into separate callback that relies on memory-overview component
@app.callback(
    [
        Output("memory-overview", "data"),
        Output("memory-pipelines", "data"),
        Output("upload-message", "children"),
        Output("session-dropdown", "options"),
        Output("session-filter-form", "style"),
        Output("interactive-datatable", "export_format"),
        Output("dataset-summary", "children"),
        Output("dataset-summary-card", "style"),
    ],
    [
        Input("upload-data", "contents"),
        State("upload-data", "filename"),
    ],
)
def process_bagel(contents, filename):
    """
    From the contents of a correctly-formatted uploaded .csv file, parse and store the pipeline overview
    data as a dataframe and update the session dropdown options.
    Returns any errors encountered during input file processing as a user-friendly message.
    """
    if contents is None:
        return (
            None,
            None,
            "Upload a CSV file to begin.",
            [],
            no_update,
            no_update,
            no_update,
            no_update,
        )
    try:
        (
            overview_df,
            sessions,
            pipelines_dict,
            upload_error,
        ) = util.parse_csv_contents(contents=contents, filename=filename)
    except Exception as exc:
        print(exc)  # for debugging
        upload_error = "Something went wrong while processing this file."

    if upload_error is not None:
        return (
            None,
            None,
            f"Error: {upload_error} Please try again.",
            [],
            {"display": "none"},
            "none",
            None,
            {"display": "none"},
        )

    # Change orientation of pipeline dataframe dictionary to enable storage as JSON data
    for key in pipelines_dict:
        pipelines_dict[key] = pipelines_dict[key].to_dict("records")

    session_opts = [{"label": ses, "value": ses} for ses in sessions]
    dataset_summary = util.construct_summary_str(overview_df)

    return (
        overview_df.to_dict("records"),
        pipelines_dict,
        None,
        session_opts,
        {"display": "block"},
        "csv",
        dataset_summary,
        {"display": "block"},
    )


@app.callback(
    [
        Output("pipeline-dropdown-container", "children"),
        Output("interactive-datatable", "style_filter_conditional"),
    ],
    Input("memory-pipelines", "data"),
    prevent_initial_call=True,
)
def create_pipeline_status_dropdowns(pipelines_dict):
    """
    Generates a dropdown filter with status options for each unique pipeline in the input csv,
    and disables the native datatable filter UI for the corresponding columns in the datatable.
    """
    pipeline_dropdowns = []

    if pipelines_dict is not None:
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
                        options=list(
                            util.PIPE_COMPLETE_STATUS_SHORT_DESC.keys()
                        ),
                        placeholder="Select status to filter for",
                    ),
                ]
            )
            pipeline_dropdowns.append(new_pipeline_status_dropdown)

        # "session" column filter is also disabled due to implemented dropdown filters for session
        style_disabled_filters = [
            {
                "if": {"column_id": c},
                "pointer-events": "None",
            }
            for c in list(pipelines_dict.keys()) + ["session"]
        ]

        return pipeline_dropdowns, style_disabled_filters

    return pipeline_dropdowns, None


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

    data = pd.DataFrame.from_dict(parsed_data)

    if session_values or not all(v is None for v in status_values):
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
    ],
    Input("upload-data", "contents"),
    State("upload-data", "filename"),
    prevent_initial_call=True,
)
def reset_selections(contents, filename):
    """
    If file contents change (i.e., selected new CSV for upload), reset displayed file name and dropdown filter
    selection values. Reset will occur regardless of whether there is an issue processing the selected file.
    """
    if ctx.triggered_id == "upload-data":
        return f"Input file: {filename}", "", ""

    raise PreventUpdate


@app.callback(
    [
        Output("fig-pipeline-status-all-ses", "figure"),
        Output("fig-pipeline-status-all-ses", "style"),
    ],
    Input("memory-overview", "data"),
    prevent_initial_call=True,
)
def generate_overview_status_fig_for_participants(parsed_data):
    """
    If new dataset uploaded, generate stacked bar plot of pipeline_complete statuses per session,
    grouped by pipeline. Provides overview of the number of participants with each status in a given session,
    per processing pipeline.
    """
    if parsed_data is None:
        return EMPTY_FIGURE_PROPS, {"display": "none"}

    return plot.plot_pipeline_status_by_participants(
        pd.DataFrame.from_dict(parsed_data)
    ), {"display": "block"}


@app.callback(
    [
        Output("fig-pipeline-status", "figure"),
        Output("fig-pipeline-status", "style"),
    ],
    Input(
        "interactive-datatable", "data"
    ),  # Input not triggered by datatable frontend filtering
    State("memory-pipelines", "data"),
    prevent_initial_call=True,
)
def update_overview_status_fig_for_records(data, pipelines_dict):
    """
    When visible data in the overview datatable is updated (excluding built-in frontend datatable filtering
    but including custom component filtering), generate stacked bar plot of pipeline_complete statuses aggregated
    by pipeline. Counts of statuses in plot thus correspond to unique records (unique participant-session
    combinations).
    """
    if data is not None:
        data_df = pd.DataFrame.from_dict(data)
        if not data_df.empty:
            return plot.plot_pipeline_status_by_records(data_df), {
                "display": "block"
            }
        return plot.plot_empty_pipeline_status_by_records(
            pipelines=pipelines_dict.keys(),
            statuses=util.PIPE_COMPLETE_STATUS_SHORT_DESC.keys(),
        ), {"display": "block"}

    return EMPTY_FIGURE_PROPS, {"display": "none"}


if __name__ == "__main__":
    app.run_server(debug=True)
