# Constants used to plot with latex font

import seaborn as sn

#COLORS = ["#d7191c", "#fdae61", "#2b83ba", "#abd9e9", "#abdda4", "#999999"]
COLORS="tab10"
COLORS_GREY = ["dimgray", "silver", "white"]
COLORS_BLACK_WHITE = ["black", "dimgray", "silver", "white"]
COLORS_SEQUENTIAL_5 = ["#253494", "#2c7fb8", "#41b6c4", "#a1dab4", "#ffffcc"]
COLORS_SEQUENTIAL_4 = ["#253494", "#2c7fb8", "#a1dab4", "#ffffcc"]
COLORS_SEQUENTIAL_3 = ["#253494", "#41b6c4", "#ffffcc"]
COLORS_SEQUENTIAL_2 = ["#2c7fb8", "#ffffcc"]
MARKERS = ["d", "s", "D", "v", "P", "*", "^"]
LINESTYLES = ["solid", (0, (1, 1)), "dashed", "dashdot", (5, (10, 3)), (0, (3, 1, 1, 1))]
LINEWIDTH = 3
MARKERSIZE = 8
HANDLETEXTPAD = 0.2
HANDLELENGTH = 2.5
FIG_HEIGHT = 3.5
TICKS_FONT_SIZE = 10
LABEL_FONT_SIZE = 10
LEGEND_FONT_SIZE = 10

def latexify(
    fig_width=None,
    fig_height=None,
    columns=2,
    nb_subplots_line=1,
    legend_font_size=LEGEND_FONT_SIZE,
    label_font_size=LABEL_FONT_SIZE,
    ticks_font_size=TICKS_FONT_SIZE
):
    """Set up matplotlib's RC params for LaTeX plotting.
    Call this before plotting a figure.
    Parameters
    ----------
    fig_width : float, optional, inches
    fig_height : float,  optional, inches
    columns : {1, 2}
    """

    # code adapted from http://www.scipy.org/Cookbook/Matplotlib/LaTeX_Examples
    # also adapted from http://bkanuka.com/posts/native-latex-plots/

    # Width and max height in inches for IEEE journals taken from
    # computer.org/cms/Computer.org/Journal%20templates/transactions_art_guide.pdf

    from math import sqrt
    import matplotlib

    assert(columns in [1, 2])

    if fig_width is None:
        # Get this from LaTeX using \the\textwidth
        #fig_width_pt = 418.25368
        fig_width_pt = 506.295
        inches_per_pt = 1.0 / 72.27                      # Convert pt to inch
        scale = 3.39 / 6.9 if columns == 1 else 1
        fig_width = fig_width_pt * inches_per_pt * scale  # width in inches
        # fig_width = 3.39 if columns==1 else 6.9 # width in inches

    if fig_height is None:
        golden_mean = (sqrt(5)-1.0)/2.0    # Aesthetic ratio
        fig_height = fig_width*golden_mean  # height in inches

    fig_width *= nb_subplots_line

    MAX_HEIGHT_INCHES = 8.0
    if fig_height > MAX_HEIGHT_INCHES:
        print("WARNING: fig_height too large {}: so will reduce to {} inches.".format(
            fig_height, MAX_HEIGHT_INCHES))
        fig_height = MAX_HEIGHT_INCHES
    print(fig_width, fig_height)
    params = {'backend': 'ps',
              'text.latex.preamble': r'\usepackage[T1]{fontenc} \usepackage{gensymb}',
              'axes.labelsize': label_font_size,
              'axes.titlesize': label_font_size,
              'font.size': label_font_size,
              'legend.fontsize': legend_font_size,
              'xtick.labelsize': ticks_font_size,
              'ytick.labelsize': ticks_font_size,
              'text.usetex': True,
              'figure.figsize': [fig_width, fig_height],
              'pgf.texsystem': 'pdflatex',
              'grid.alpha': 0.25,
              'mathtext.default': 'regular',  # Don't italize math text
              'font.family': 'serif'
              }

    matplotlib.rcParams.update(params)

def start_zero(ax):
    _, max = ax.get_ylim()
    ax.set_ylim(bottom=-max/20, top=max*1.1)

def legend(ax, title=None, position=None, cols=1, frame=True, padding_bottom=0, sort=True):
    if not ax.legend_:
        return
    if sort:
        # https://stackoverflow.com/questions/22263807/how-is-order-of-items-in-matplotlib-legend-determined
        handles, labels = ax.legend_.legend_handles, ax.legend_.texts
        labels = [label.get_text() for label in labels]
        labels, handles = zip(*sorted(zip(labels, handles), key=lambda t: t[0].lower()))
        ax.legend(handles, labels)
    if position == "above":
        sn.move_legend(
            ax, "lower center",
            bbox_to_anchor=(.5, 1 + padding_bottom), ncol=cols,
            title=title, frameon=frame
        )
    elif position == "right":
        sn.move_legend(ax, "upper left", bbox_to_anchor=(1, 1),
            ncol=cols, title=title, frameon=frame
        )
    else:
        ax.legend_.set_title(title)
        handles, labels = ax.legend_.legend_handles, ax.legend_.texts
        labels = [label.get_text() for label in labels]
        ax.legend(handles, labels, ncols=cols, columnspacing=0.8)
    ax.legend_.get_frame().set_edgecolor('black')

def grid(ax, axis):
    ax.grid(axis=axis, color='grey', linestyle='dashed', alpha=0.4)