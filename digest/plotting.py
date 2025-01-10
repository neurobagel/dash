from itertools import product
from textwrap import wrap

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from . import utility as util
from .utility import PRIMARY_SESSION_COL

CMAP = px.colors.qualitative.Bold
STATUS_COLORS = {
    "SUCCESS": CMAP[5],
    "FAIL": CMAP[9],
    "INCOMPLETE": CMAP[3],
    "UNAVAILABLE": CMAP[10],
}
CMAP_PHENO = px.colors.qualitative.Vivid

# Define margins and title position for plots
LAYOUTS = {
    "margin": {"l": 30, "r": 30, "t": 60, "b": 30},  # margins of chart
    "title": {  # figure title position properties, see https://plotly.com/python/reference/layout/#layout-title
        "yref": "container",
        "xref": "paper",
        "x": 0.5,
        "y": 1,
        "xanchor": "center",
        "yanchor": "top",
        "pad": {"t": 20},
    },
}


def transform_active_data_to_long(data: pd.DataFrame) -> pd.DataFrame:
    return pd.melt(
        data,
        id_vars=util.get_id_columns(data),
        var_name="pipeline_name",
        value_name="status",
    )


def wrap_df_column_values(
    df: pd.DataFrame, column: str, width: int
) -> pd.DataFrame:
    """Wraps string values of a column which are longer than the specified character length."""
    if df[column].dtype == "object":
        df[column] = df[column].map(
            lambda value: "<br>".join(
                wrap(text=value, width=width, break_long_words=False)
            ),
            na_action="ignore",
        )
    return df


def plot_pipeline_status_by_participants(
    data: pd.DataFrame, session_list: list
) -> go.Figure:
    status_counts = (
        transform_active_data_to_long(data)
        .groupby(["pipeline_name", "status", PRIMARY_SESSION_COL])
        .size()
        .reset_index(name="participants")
    )

    fig = px.bar(
        status_counts,
        x=PRIMARY_SESSION_COL,
        y="participants",
        color="status",
        text_auto=True,
        facet_col="pipeline_name",
        category_orders={
            "status": util.PIPE_COMPLETE_STATUS_SHORT_DESC.keys(),
            PRIMARY_SESSION_COL: session_list,
        },
        color_discrete_map=STATUS_COLORS,
        labels={
            "pipeline_name": "Pipeline",
            "participants": "Participants (n)",
            "status": "Processing status",
            PRIMARY_SESSION_COL: "Session",
        },
        title="All participant pipeline statuses by session",
    )
    # Treat session labels as categorical in plot to avoid a continuous x-axis
    fig.update_xaxes(type="category")
    fig.update_layout(margin=LAYOUTS["margin"], title=LAYOUTS["title"])

    return fig


def plot_pipeline_status_by_records(status_counts: pd.DataFrame) -> go.Figure:
    fig = px.bar(
        status_counts,
        x="pipeline_name",
        y="records",
        color="status",
        text_auto=True,
        category_orders={
            "status": util.PIPE_COMPLETE_STATUS_SHORT_DESC.keys(),
            "pipeline_name": status_counts["pipeline_name"]
            .drop_duplicates()
            .sort_values(),
        },
        color_discrete_map=STATUS_COLORS,
        labels={
            "pipeline_name": "Pipeline",
            "records": "Records (n)",
            "status": "Processing status",
        },
        title="Pipeline statuses of records matching filter (default: all)",
    )
    fig.update_layout(margin=LAYOUTS["margin"], title=LAYOUTS["title"])

    return fig


def populate_empty_records_pipeline_status_plot(
    pipelines: list, statuses: list
) -> pd.DataFrame:
    """Returns dataframe of counts representing 0 matching records in the datatable, i.e., 0 records with each pipeline status."""
    status_counts = pd.DataFrame(
        list(product(pipelines, statuses)),
        columns=["pipeline_name", "status"],
    )
    status_counts["records"] = 0

    return status_counts


def plot_phenotypic_column_histogram(
    data: pd.DataFrame, column: str, color: str = None
) -> go.Figure:
    """
    Returns a histogram of the values of the given column across records in the active datatable.
    If the column data are continuous, a box plot of the distribution is also plotted as a subplot.
    """
    axis_title_gap = 8  # reduce gap between axis title and axis tick labels
    title_fsize = 18
    if np.issubdtype(data[column].dtype, np.number):
        # NOTE: The default box plot on-hover labels mean/q1/q3 etc. are a bit verbose, but there's no way to customize how they are displayed yet
        # (See https://github.com/plotly/plotly.js/pull/3685)
        marginal = "box"
    else:
        marginal = None

    fig = px.histogram(
        wrap_df_column_values(df=data, column=column, width=30),
        x=column,
        color=color,
        color_discrete_sequence=CMAP_PHENO,
        marginal=marginal,
    )
    # Customize box plot appearance and on-hover labels for data points (display participant_id as well as the column value (x))
    fig.update_traces(
        boxmean=True,
        notched=False,
        jitter=1,
        customdata=data["participant_id"],
        meta=column,
        hovertemplate="participant_id: %{customdata}<br>%{meta}=%{x}",
        selector={"type": "box"},
    )
    fig.update_layout(
        margin=LAYOUTS["margin"],
        title={
            "text": f'Count distribution of "{column}" across records matching filter (default: all)',
            "font": {"size": title_fsize},
            **LAYOUTS["title"],
        },
        bargap=0.1,
        barmode="group",
        boxgap=0.1,
        # Reduce gap between legend and plot area
        # (https://plotly.com/python-api-reference/generated/plotly.graph_objects.Layout.html#plotly.graph_objects.layout.Legend.x)
        legend={"x": 1.01},
    )
    fig.update_xaxes(title_standoff=axis_title_gap)
    fig.update_yaxes(title_standoff=axis_title_gap)

    return fig
