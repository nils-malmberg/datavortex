from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field


class ParseRequest(BaseModel):
    session_id: str
    separator: str


class UploadResponse(BaseModel):
    session_id: str
    filename: str
    file_kind: str
    encoding: str
    detected_separator: Optional[str] = None
    available_separators: list[str] = []
    raw_preview: list[str] = []
    already_parsed: bool = False


class ParseResponse(BaseModel):
    session_id: str
    separator: Optional[str]
    n_rows: int
    n_columns: int
    columns: list[str]
    column_types: dict[str, str]


# --- Visualisations (Phase 2) ------------------------------------------------

Plot1DType = Literal["histogram", "box", "violin", "kde", "bar", "pie"]
Plot2DType = Literal["scatter", "line", "heatmap", "hexbin", "bar_grouped", "bubble"]
Plot3DType = Literal["scatter3d", "surface"]


class Plot1DRequest(BaseModel):
    session_id: str
    column: str
    plot_type: Plot1DType
    group_by: Optional[str] = None
    bins: int = 20
    title: Optional[str] = None


class Plot2DRequest(BaseModel):
    session_id: str
    plot_type: Plot2DType
    x: Optional[str] = None
    y: Optional[str] = None
    color_by: Optional[str] = None
    size_by: Optional[str] = None
    columns: Optional[list[str]] = None  # utilisé par 'heatmap' (sous-ensemble de colonnes numériques)
    bins: int = 30  # utilisé par 'hexbin'
    title: Optional[str] = None


class Plot3DRequest(BaseModel):
    session_id: str
    plot_type: Plot3DType
    x: str
    y: str
    z: str
    color_by: Optional[str] = None
    title: Optional[str] = None


class ExportPlotRequest(BaseModel):
    session_id: str
    kind: Literal["1d", "2d", "3d", "ml", "advanced"]
    params: dict
    format: Literal["png", "svg", "html"]
    width: int = 900
    height: int = 600


# --- Filtrage & Colonnes calculées (Phase 3) ---------------------------------

class FilterCondition(BaseModel):
    type: Literal["condition"] = "condition"
    column: str
    operator: str
    value: Optional[Any] = None
    # Identifiant fourni par l'interface, renvoyé tel quel dans les indicateurs :
    # il rattache chaque mesure à la bonne ligne du constructeur de filtre, même
    # quand des conditions incomplètes sont écartées de la requête.
    id: Optional[str] = None


class FilterGroup(BaseModel):
    type: Literal["group"] = "group"
    logic: Literal["AND", "OR"] = "AND"
    conditions: list["FilterNode"] = []


FilterNode = Annotated[Union[FilterCondition, FilterGroup], Field(discriminator="type")]
FilterGroup.model_rebuild()


class ApplyFilterRequest(BaseModel):
    filter: Optional[FilterNode] = None


class CreateColumnRequest(BaseModel):
    name: str
    formula: str
    overwrite: bool = False
    preview_only: bool = False
    preview_rows: int = 10


# --- Export (Phase 4) --------------------------------------------------------

class ExportCsvRequest(BaseModel):
    session_id: str
    separator: str = ","
    encoding: str = "utf-8"
    include_filter_comment: bool = True


# --- Rapport PDF (Phase 6) ----------------------------------------------------

ReportSection = Literal["summary", "stats", "preview", "plots", "correlations", "metadata"]


class ReportPlotSpec(BaseModel):
    kind: Literal["1d", "2d", "3d", "ml", "advanced", "groupby", "pivot"]
    params: dict
    title: Optional[str] = None


class GenerateReportRequest(BaseModel):
    session_id: str
    sections: list[ReportSection] = []
    plots: list[ReportPlotSpec] = []
    page_format: Literal["A4", "Letter"] = "A4"
    orientation: Literal["portrait", "landscape"] = "portrait"
    resize_plots_to_fit: bool = True


# --- Fusion multi-fichiers (Phase 5 update) -----------------------------------

class MergeRequest(BaseModel):
    session_ids: list[str]
    mode: Literal["concat", "merge"]
    key_column: Optional[str] = None
    left_suffix: str = "_x"
    right_suffix: str = "_y"


# --- Machine Learning (Phase 7) -----------------------------------------------

RegressionModelType = Literal[
    "linear", "polynomial", "ridge", "lasso", "elastic_net",
    "svr", "gpr", "gradient_boosting", "random_forest",
]

ClassificationModelType = Literal[
    "logistic", "decision_tree", "random_forest",
    "svm", "gradient_boosting", "knn", "naive_bayes", "mlp",
    "voting", "stacking",
]

ClusteringModelType = Literal[
    "kmeans", "dbscan", "hierarchical", "agglomerative", "gmm", "mean_shift",
]


class RegressionRequest(BaseModel):
    session_id: str
    features: list[str]
    target: str
    model_type: RegressionModelType = "linear"
    degree: int = 2
    params: dict = {}


class ClassificationRequest(BaseModel):
    session_id: str
    features: list[str]
    target: str
    model_type: ClassificationModelType = "logistic"
    params: dict = {}


class ClusteringRequest(BaseModel):
    session_id: str
    features: list[str]
    model_type: ClusteringModelType = "kmeans"
    params: dict = {}
    color_by: Optional[str] = None


class PCARequest(BaseModel):
    session_id: str
    features: list[str]
    n_components: Literal[2, 3] = 2
    method: Literal["pca", "tsne", "umap"] = "pca"
    color_by: Optional[str] = None


# --- Réseaux de neurones & export de modèles (Phase 8.1) -----------------------

class NeuralLayerSpec(BaseModel):
    units: int = 16
    activation: Literal["relu", "tanh", "sigmoid", "linear"] = "relu"
    dropout: float = 0.0


class NeuralNetworkRequest(BaseModel):
    session_id: str
    features: list[str]
    target: str
    task: Literal["regression", "classification"]
    layers: list[NeuralLayerSpec] = Field(
        default_factory=lambda: [NeuralLayerSpec(units=16), NeuralLayerSpec(units=8)],
    )
    optimizer: Literal["adam", "sgd", "rmsprop"] = "adam"
    learning_rate: float = 0.001
    batch_size: int = 32
    epochs: int = 50
    validation_split: float = 0.2


class ModelExportRequest(BaseModel):
    session_id: str
    model_id: str
    format: Literal["joblib", "pickle", "json", "onnx", "tflite"] = "joblib"


class ModelMetadataRequest(BaseModel):
    session_id: str
    model_id: str


class TrainingScriptRequest(BaseModel):
    session_id: str
    model_id: str


# --- Statistiques avancées (Phase 8) ------------------------------------------

CorrelationMethod = Literal["pearson", "spearman", "kendall"]
TableFormat = Literal["csv", "excel", "latex"]


class StatsExportRequest(BaseModel):
    session_id: str
    table: Literal["summary", "correlations", "distributions", "missing"] = "summary"
    format: TableFormat = "csv"
    precision: int = 4


# --- Visualisations avancées (Phase 8) ----------------------------------------

AdvancedPlotType = Literal[
    # types repris de la Phase 2, enrichis des options avancées
    "scatter", "line", "bar_grouped", "bubble", "hexbin", "heatmap",
    "histogram", "box", "violin", "kde", "bar", "pie",
    "scatter3d", "surface",
    # nouveaux types Phase 8
    "violin_swarm", "ridge", "strip", "pair", "joint",
]

PaletteName = Literal["Default", "Viridis", "Plasma", "Inferno", "Cividis", "Twilight", "Okabe-Ito", "Tol Bright"]
ColorblindMode = Literal["none", "safe", "deuteranopia", "protanopia", "tritanopia", "grayscale"]
LegendPosition = Literal["top-right", "top-left", "bottom-right", "bottom-left", "top", "bottom", "none"]


class TrendSpec(BaseModel):
    type: Literal["none", "linear", "polynomial", "lowess"] = "none"
    degree: int = 2
    frac: float = 0.35  # fenêtre LOWESS, en proportion des points
    confidence: Literal["none", "95", "99"] = "none"
    show_equation: bool = True


class OverlaySpec(BaseModel):
    mean: bool = False
    median: bool = False
    std: bool = False
    std_sigmas: int = 2
    percentiles: list[float] = []


class AnnotationSpec(BaseModel):
    text: str
    x: float
    y: float
    arrow: bool = True
    size: int = 12


class StyleSpec(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    x_label: Optional[str] = None
    y_label: Optional[str] = None
    palette: PaletteName = "Default"
    colorblind_mode: ColorblindMode = "none"
    grid: bool = True
    legend_position: LegendPosition = "top-right"
    x_scale: Literal["linear", "log"] = "linear"
    y_scale: Literal["linear", "log"] = "linear"
    theme: Literal["auto", "light", "dark"] = "auto"
    width: int = 900
    height: int = 600
    dpi: int = 100
    annotations: list[AnnotationSpec] = []


class AdvancedPlotRequest(BaseModel):
    session_id: str
    plot_type: AdvancedPlotType = "scatter"
    x: Optional[str] = None
    y: Optional[str] = None
    z: Optional[str] = None
    color_by: Optional[str] = None
    size_by: Optional[str] = None
    group_by: Optional[str] = None
    columns: Optional[list[str]] = None
    bins: int = 30
    trend: TrendSpec = TrendSpec()
    overlays: OverlaySpec = OverlaySpec()
    style: StyleSpec = StyleSpec()


# --- Filtres avancés (Phase 8) -------------------------------------------------

class AdvancedFilterRequest(BaseModel):
    session_id: str
    filter: Optional[FilterNode] = None
    invert: bool = False
    preview_rows: int = 50
    preview_mode: Literal["all", "kept", "removed"] = "all"


# --- Groupby & agrégations (Phase 8) -------------------------------------------

AggregationFunc = Literal[
    "mean", "sum", "count", "min", "max", "std", "var", "sem",
    "median", "quantile", "first", "last", "nunique",
]


class AggregationSpec(BaseModel):
    column: str
    func: AggregationFunc = "mean"
    quantile: float = 0.5
    alias: Optional[str] = None


class GroupByRequest(BaseModel):
    session_id: str
    group_by: list[str] = []
    aggregations: list[AggregationSpec] = []
    sort_by: Optional[str] = None
    sort_ascending: bool = True
    limit: int = 500


class GroupByExportRequest(GroupByRequest):
    format: TableFormat = "csv"
    precision: int = 4


# --- Tableaux croisés dynamiques (Phase 8) -------------------------------------

PivotAggFunc = Literal["mean", "sum", "count", "min", "max", "std", "var", "median", "nunique"]


class PivotRequest(BaseModel):
    session_id: str
    index: list[str] = []
    columns: list[str] = []
    values: Optional[str] = None
    aggfunc: PivotAggFunc = "mean"
    margins: bool = False
    percentage: Literal["none", "total", "row", "column"] = "none"


class PivotExportRequest(PivotRequest):
    format: TableFormat = "csv"
    precision: int = 4


# --- Tests statistiques (Phase 8) ----------------------------------------------

StatTestFamily = Literal["hypothesis", "anova", "correlation", "goodness_of_fit"]
StatTestName = Literal[
    "ttest_ind", "ttest_rel", "ttest_1samp", "mannwhitney", "wilcoxon",
    "one_way", "two_way",
    "pearson", "spearman", "kendall",
    "shapiro", "ks", "anderson", "chi2",
]


class HypothesisTestRequest(BaseModel):
    session_id: str
    family: StatTestFamily = "hypothesis"
    test: StatTestName = "ttest_ind"
    column: Optional[str] = None
    column_b: Optional[str] = None
    group_column: Optional[str] = None
    group_a: Optional[str] = None
    group_b: Optional[str] = None
    factor_a: Optional[str] = None
    factor_b: Optional[str] = None
    alpha: float = 0.05
    alternative: Literal["two-sided", "less", "greater"] = "two-sided"
    popmean: float = 0.0
    equal_variance: bool = False
    post_hoc: Literal["none", "tukey", "bonferroni"] = "tukey"
    distribution: Literal["norm", "expon", "uniform", "lognorm"] = "norm"


# --- Opérations sur les colonnes (Phase 8) -------------------------------------

class ColumnOperationRequest(BaseModel):
    session_id: str
    op: Literal["rename", "duplicate", "delete", "reorder"]
    columns: list[str] = []
    new_name: Optional[str] = None
    order: Optional[list[str]] = None


class ColumnTransformRequest(BaseModel):
    session_id: str
    transform: Literal["binning", "encoding", "lag", "rolling"]
    source: str
    params: dict = {}
    new_name: Optional[str] = None
    replace: bool = False
