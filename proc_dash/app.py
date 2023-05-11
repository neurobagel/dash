"""
Constructs Dash app for viewing and filtering statuses of processing pipelines for a given dataset.
App accepts and parses a user-uploaded bagel.csv file (assumed to be generated by mr_proc) as input.
"""

import dash_bootstrap_components as dbc
import pandas as pd
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

import proc_dash.plotting as plot
import proc_dash.utility as util
from dash import Dash, ctx, dash_table, dcc, html

EMPTY_FIGURE_PROPS = {"data": [], "layout": {}, "frames": []}

app = Dash(__name__, external_stylesheets=[dbc.themes.FLATLY])
server = app.server

# Navbar UI component
navbar = dbc.Navbar(
    dbc.Container(
        [
            dbc.Row(
                dbc.Col(dbc.NavbarBrand("Neuroimaging Derivatives Status Dashboard")),
                align="center",
            ),
            dbc.Row(
                dbc.Col(
                    dbc.Nav(
                        dbc.Button(
                            "View Code on github",
                            outline=True,
                            color="primary",
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

app.layout = html.Div(
    children=[
        navbar,
        dcc.Store(id="memory"),
        dcc.Upload(
            id="upload-data",
            children=dbc.Button(
                "Drag and Drop or Select .csv File", color="secondary"
            ),  # TODO: Constrain click responsive area of button
            style={"margin-top": "10px", "margin-bottom": "10px"},
            multiple=False,
        ),
        html.Div(
            id="output-data-upload",
            children=[
                html.H4(id="input-filename"),
                html.Div(
                    children=[
                        html.Div(id="total-participants"),
                        html.Div(
                            id="matching-participants",
                            style={"margin-left": "15px"},
                        ),
                    ],
                    style={"display": "inline-flex"},
                ),
                dash_table.DataTable(
                    id="interactive-datatable",
                    data=None,
                    sort_action="native",
                    sort_mode="multi",
                    filter_action="native",
                    page_size=50,
                    fixed_rows={"headers": True},
                    style_table={"height": "300px", "overflowY": "auto"},
                    style_cell={
                        "fontSize": 13  # accounts for font size inflation by dbc theme
                    },
                ),
                # NOTE: Could cast columns to strings for the datatable to standardize filtering syntax,
                # but this results in undesirable effects (e.g., if there is session 1 and session 11,
                # a query for "1" would return both)
            ],
            style={"margin-top": "10px", "margin-bottom": "10px"},
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Form(
                        [
                            # TODO: Put label and dropdown in same row
                            html.Div(
                                [
                                    dbc.Label(
                                        "Filter by multiple sessions:",
                                        html_for="session-dropdown",
                                        className="mb-0",
                                    ),
                                    dcc.Dropdown(
                                        id="session-dropdown",
                                        options=[],
                                        multi=True,
                                        placeholder="Select one or more available sessions to filter by",
                                        # TODO: Can set `disabled=True` here to prevent any user interaction before file is uploaded
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
                                                "title": "Show only participants with all selected sessions.",
                                            },
                                            {
                                                "label": "OR",
                                                "value": "OR",
                                                "title": "Show participants with any of the selected sessions.",
                                            },
                                        ],
                                        value="AND",
                                        clearable=False,
                                        # TODO: Can set `disabled=True` here to prevent any user interaction before file is uploaded
                                    ),
                                ],
                                className="mb-2",
                            ),
                        ],
                    )
                ),
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.H5(
                                    "Legend: Processing status",
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
                ),
            ]
        ),
        dbc.Row(
            [
                # NOTE: Legend displayed for both graphs so that user can toggle visibility of status data
                dbc.Col(dcc.Graph(id="fig-pipeline-status", style={"display": "none"})),
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
        Output("memory", "data"),
        Output("total-participants", "children"),
        Output("session-dropdown", "options"),
    ],
    [
        Input("upload-data", "contents"),
        State("upload-data", "filename"),
    ],
)
def process_bagel(contents, filename):
    """
    From the contents of a correctly-formatted uploaded .csv file, parse and store the pipeline overview
    data as a dataframe and update the session dropdown options and displayed total participants count.
    Returns any errors encountered during input file processing as a user-friendly message.
    """
    if contents is None:
        return None, "Upload a CSV file to begin.", []
    try:
        data, total_subjects, sessions, upload_error = util.parse_csv_contents(
            contents=contents, filename=filename
        )
    except Exception as exc:
        print(exc)  # for debugging
        upload_error = "Something went wrong while processing this file."

    if upload_error is not None:
        return None, f"Error: {upload_error} Please try again.", []

    report_total_subjects = f"Total number of participants: {total_subjects}"
    session_opts = [{"label": ses, "value": ses} for ses in sessions]

    return data.to_dict("records"), report_total_subjects, session_opts


@app.callback(
    [
        Output("interactive-datatable", "columns"),
        Output("interactive-datatable", "data"),
    ],
    [
        Input("memory", "data"),
        Input("session-dropdown", "value"),
        Input("select-operator", "value"),
    ],
)
def update_outputs(parsed_data, session_values, operator_value):
    if parsed_data is None:
        return None, None

    data = pd.DataFrame.from_dict(parsed_data)

    if session_values:
        data = util.filter_by_sessions(
            data=data,
            session_values=session_values,
            operator_value=operator_value,
        )
    tbl_columns = [{"name": i, "id": i} for i in data.columns]
    tbl_data = data.to_dict("records")

    return tbl_columns, tbl_data


@app.callback(
    Output("matching-participants", "children"),
    [
        Input("interactive-datatable", "columns"),
        Input("interactive-datatable", "derived_virtual_data"),
    ],
)
def update_matching_participants(columns, virtual_data):
    """
    If the visible data in the datatable changes, update count of
    unique participants shown ("Participants matching query").

    When no filter (built-in or dropdown-based) has been applied,
    this count will be the same as the total number of participants
    in the dataset.
    """
    # calculate participant count for active table as long as datatable columns exist
    if columns is not None and columns != []:
        active_df = pd.DataFrame.from_dict(virtual_data)
        return f"Participants matching query: {util.count_unique_subjects(active_df)}"

    return ""


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
    Input("memory", "data"),
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
    prevent_initial_call=True,
)
def update_overview_status_fig_for_records(data):
    """
    When visible data in the overview datatable is updated (excluding built-in frontend datatable filtering
    but including component filtering for multiple sessions), generate stacked bar plot of pipeline_complete
    statuses aggregated by pipeline. Counts of statuses in plot thus correspond to unique records (unique
    participant-session combinations).
    """
    if data is not None:
        return plot.plot_pipeline_status_by_records(pd.DataFrame.from_dict(data)), {
            "display": "block"
        }

    return EMPTY_FIGURE_PROPS, {"display": "none"}


if __name__ == "__main__":
    app.run_server(debug=True)
