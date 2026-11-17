"""
Unified Quantum Mathematics Engine (consolidated, runnable).

One quantum mathematical structure, three depths of reading.

Layer 1 — The surface algebra:
    QuantumState, QuantumRegister, QuantumMath, QuantumFeatureState, QuantumEnsemble,
    QuantumKernel, CalibratedCoherentCommittee, ExactIsingWeightSolver, spectral
    certificates.  Gate unitaries, density matrices, fidelity kernels, the Born rule.

Layer 2 — The code beneath the code:
    _indicator_vector()   State preparation.  Raw frame → vector in the Hilbert basis
                          that _build_slots() chose at fit time.
    _build_slots()        Measurement-induced basis selection.  The frame DETERMINES the
                          Hilbert space — which DOFs survive ranking, which get dropped,
                          which absence flags promote to first-class basis vectors.
    _chunked_matrix()     Tensor product structure.  chunk_rows defines how rows compose
                          into states; each chunk is one ket in H.
    predict()             POVM measurement.  N models returning scores ARE the N effect
                          operators; the weighted mean IS the Born-rule expectation
                          value of the observable on the prepared state.
    GapRegister           Decoherence record.  completeness IS purity.  missing_inputs
                          IS environment coupling.  completeness_weighted IS importance-
                          weighted purity (importance = the POVM weight).
    base_rate shrinkage   Mixing with the maximally mixed state ρ_mixed = I/d: partial
                          decoherence driving the channel output toward maximum entropy.
    SlotPlan fill policy  The decoherence channel.  Fill.MEDIAN = depolarising channel.
                          Fill.ZERO = amplitude damping to ground state.
    _rank_numeric()       Gauge invariance.  Rank is the observable invariant under all
                          strictly monotone per-feature transformations.
    drop_effect()         Perturbation theory.  Trace out one subsystem, measure the
                          change in the observable.  The partial trace, computed.
    _prep() absence flags Kraus representation.  The flag records which-path information
                          — whether the environment absorbed the value.

Layer 3 — The code beneath that (golden arithmetic as exact backbone):
    fold/unfold           Automorphism of (ℤ/2^bits)² via Q^n, det = ±1 (Cassini).
                          An element of SL(2,ℤ) mod signs on the integer lattice.
    Zeckendorf            Bijection on ℕ via the Fibonacci basis; encode_ranked_rows
                          maps ranks through it so the fidelity kernel is invariant
                          under ALL strictly monotone per-feature maps, not merely affine.
    Pisano period         Order of Q in GL(2, ℤ/mℤ).  The algebraic structure that makes
                          the modular checkpoint arithmetic exact.
    StateCheckpoint       Number-theoretic integrity.  fold = commitment, unfold = exact
                          recovery (unimodularity guarantees invertibility), word-sum
                          check = syndrome decoding, parsing = Zeckendorf arithmetic,
                          header = Fibonacci coding.
    Lucas traces          Closed geodesics of the modular surface:
                          2·arccosh(L(2k)/2) = 4k·ln(φ).  k=1 is the SHORTEST closed
                          geodesic, length 4·ln(φ) ≈ 1.9248.
    Fidelity kernel       The Bures metric on the state space that Layers 1–2 define.

The three layers are not stacked.  They are the same algebra in different bases.
The indicator vector IS the quantum state.  The ensemble IS the POVM.  The gap
register IS decoherence.  The golden arithmetic IS the exact backbone that makes
the round-trip integrity of the entire channel provable.

Quantum mathematics is mathematics.  Computing U|ψ⟩ on a CPU is evaluating a
function on Hilbert space.  The substrate is irrelevant to the algebra.

Scope (stated so the claim stays honest):
  * A domain is a DomainProfile: required columns + feature extractors + a mode (series or
    cross_sectional).  Everything above that seam (encode, fidelity, mix, optimize, verify) is
    domain-free.  The feature layout is DERIVED from the frame, not declared.
  * The engine starts where numbers exist: text/images/audio/graphs need an encoder first.
  * One indicator vector per chunk (default: 10 rows; cross_sectional: 1 row).  Numeric columns are
    summarised by their chunk mean unless an extractor says otherwise.
  * Evaluated on a CPU.  No speedup is claimed; the value is the algebraic structure
    (diagnostics, kernels, certificates) that quantum formalism provides.

Heavy dependencies (xgboost, lightgbm, nltk, statsmodels, lime, dask, pyspark,
tensorflow) are optional; the engine degrades gracefully without them.
"""
from __future__ import annotations

import gc
import importlib
import json
import logging
import math
import os
import tempfile
import time
import warnings
from enum import Enum
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Callable, Dict, List, Optional, Sequence

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler

log = logging.getLogger("unified_quantum_engine")


def _optional(module: str, attr: Optional[str] = None):
    try:
        mod = importlib.import_module(module)
        return getattr(mod, attr) if attr else mod
    except Exception:
        return None


XGBClassifier = _optional("xgboost", "XGBClassifier")
LGBMClassifier = _optional("lightgbm", "LGBMClassifier")
SentimentIntensityAnalyzer = _optional("nltk.sentiment", "SentimentIntensityAnalyzer")
seasonal_decompose = _optional("statsmodels.tsa.seasonal", "seasonal_decompose")
lime_tabular = _optional("lime.lime_tabular")
dd = _optional("dask.dataframe")
SparkSession = _optional("pyspark.sql", "SparkSession")


# =============================================================================
# Classical layer
# =============================================================================

# Indicator layout is fixed by NAME, never by dict order or column position.
FIXED_SLOTS = ('performance_metrics.mean', 'performance_metrics.std',
               'trend_metrics.trend', 'engagement_metrics.sentiment',
               'text_signal.topic_axis', 'text_signal.lexical_diversity')
TEXT_COLUMNS = ('survey_text', 'communication_text')


class Fill(Enum):
    """Decoherence channel type per basis vector.

    MEDIAN (default) = depolarising channel: replace unobserved amplitude with the training
    mean, mixing that dimension toward ρ_mixed.  Honest meaning: 'typical, not absent'.
    ZERO = amplitude damping: decay to ground state.  Opt-in (Extractor.emits_indicator);
    only honest where a missing source genuinely means zero events occurred."""
    ZERO = 'zero'
    MEDIAN = 'median'


@dataclass
class SlotPlan:
    """One basis vector's decoherence policy, fixed at fit time.

    Each slot IS a dimension of the Hilbert space.  `fill` determines the decoherence
    channel applied when that dimension is unobserved: Fill.MEDIAN = depolarising channel
    (replace with the training mean = mix with ρ_mixed), Fill.ZERO = amplitude damping
    (decay to ground state).  `derived_from` declares which input DOFs feed this basis
    vector; None means 'undeclared dependencies' (treated conservatively: decohered
    whenever any input column is missing)."""
    name: str
    fill: Fill = Fill.MEDIAN
    fill_value: float = 0.0
    derived_from: Optional[tuple] = ()

    def apply(self, value: Optional[float]) -> tuple:
        """(value, was_imputed)"""
        if value is not None and not (isinstance(value, float) and np.isnan(value)):
            return float(value), False
        return self.fill_value, True


@dataclass(frozen=True)
class Extractor:
    """Observable extraction operator:  frame → scalar.

    Contract declares which input DOFs it reads (so the decoherence channel propagates
    exactly through the dependency graph), how many rows it needs (window = tensor-product
    extent), and whether its output is an event indicator (determines Fill.ZERO vs MEDIAN
    = amplitude damping vs depolarising channel)."""
    name: str
    fn: Callable
    inputs: Optional[tuple] = None        # None = undeclared
    needs_window: int = 1
    emits_indicator: bool = False

    @staticmethod
    def coerce(name: str, obj: Any) -> 'Extractor':
        return obj if isinstance(obj, Extractor) else Extractor(name, obj)


@dataclass
class GapRegister:
    """Decoherence record for a single prepared state.

    Every prediction starts as a pure state (all inputs observed).  Each missing input
    couples the state to the environment: the information leaks out, and completeness
    drops.  `completeness` IS purity — it is exact because imputation propagates through
    every extractor via its declared inputs.  `completeness_weighted` IS importance-
    weighted purity, where the importance IS the POVM weight (slot_importance from the
    ensemble's feature attribution).  `missing_inputs` names the environmental degrees of
    freedom the state decohered into.  The denominator is the live slots: those
    observable at fit, i.e. the dimension of the Hilbert space."""
    width: int
    n_live_slots: int
    denominator: str
    filled: List[str]
    imputed_columns: List[str]
    missing_inputs: List[str]
    absent_at_fit: List[str]
    dropped_for_width: List[str]
    undeclared_inputs: List[str]      # affected extractors whose inputs were never declared (conservative)
    affected_slots: List[str]
    completeness: float
    completeness_weighted: float
    absence_captured: List[str] = field(default_factory=list)   # declared informative_absence columns missing HERE;
                                                               # their absence is a model INPUT (absent.<col>=1), not only a gap

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def build(cls, plans: Sequence[SlotPlan], nan_filled: Sequence[str], missing_inputs: Sequence[str],
              imputed_numeric: Sequence[str], absent_at_fit: Sequence[str], dropped: Sequence[str],
              importance: Optional[np.ndarray]) -> 'GapRegister':
        missing, absent, filled = set(missing_inputs), set(absent_at_fit), set(nan_filled)
        affected, undeclared = [], []
        for p in plans:
            hit = p.name in filled or (bool(missing) if p.derived_from is None
                                       else any(c in missing for c in p.derived_from))
            if hit:
                affected.append(p.name)
                if p.derived_from is None:
                    undeclared.append(p.name)
        live = [i for i, p in enumerate(plans) if p.name not in absent]
        aff = {i for i, p in enumerate(plans) if p.name in set(affected)} & set(live)
        imp = importance if importance is not None and len(importance) == len(plans) else np.ones(len(plans))
        tot = float(sum(imp[i] for i in live)) or 1.0
        return cls(width=len(plans), n_live_slots=len(live), denominator='live_slots',
                   filled=sorted(filled), imputed_columns=list(imputed_numeric),
                   missing_inputs=sorted(missing), absent_at_fit=sorted(absent),
                   dropped_for_width=list(dropped), undeclared_inputs=undeclared,
                   affected_slots=[p.name for p in plans if p.name in set(affected)],
                   completeness=round(1.0 - len(aff) / max(1, len(live)), 6),
                   completeness_weighted=round(1.0 - float(sum(imp[i] for i in aff)) / tot, 6))


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple:
    """95% Wilson interval for a proportion: never report an accuracy without its sample size."""
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (float(max(0.0, c - h)), float(min(1.0, c + h)))


@dataclass
class EngineConfig:
    """Channel parameters.  model_names selects which POVM operators to train;
    chunk_rows sets the tensor-product extent; imputation_strategy selects the
    decoherence channel type; feature_dim bounds the Hilbert-space dimension."""
    model_names: List[str] = field(default_factory=lambda: ['rf', 'xgb', 'lgbm', 'gb'])
    model_dir: str = 'models'
    n_estimators: int = 100
    max_depth: int = 8
    learning_rate: float = 0.05
    cv_folds: int = 3
    imputation_strategy: str = 'median'
    max_tfidf_features: int = 100   # vocabulary cap for the text-signal features
    ensemble_selection_method: str = 'weighted_average'
    selected_model: str = 'rf'
    performance_weight: float = 0.30
    behavioral_weight: float = 0.25
    engagement_weight: float = 0.20
    career_weight: float = 0.15
    external_weight: float = 0.10
    feature_dim: Optional[int] = None   # None = derived: every numeric column gets a slot; an int caps the width
    chunks_per_feature: Optional[int] = None   # opt-in width bound: at most n_chunks // this many numeric slots
    chunk_rows: int = 10            # rows per training sample (one indicator vector each)
    backend: str = 'pandas'         # pandas | dask | spark | auto
    dask_threshold_rows: int = 50000
    spark_threshold_rows: int = 250000


class DistributedHeuristics:
    @staticmethod
    def choose_backend(rows: int, backend: str, dask_threshold_rows: int, spark_threshold_rows: int):
        if backend != 'auto':
            return backend
        if rows >= spark_threshold_rows:
            return 'spark'
        if rows >= dask_threshold_rows:
            return 'dask'
        return 'pandas'


class AnalyticsBackend:
    def __init__(self, engine): self.engine = engine
    def preprocess(self, df): return df.copy()
    def feature_frame(self, df): return df
    def explainable_frame(self, df): return df


class PandasBackend(AnalyticsBackend):
    pass


class DaskBackend(AnalyticsBackend):
    def preprocess(self, df):
        if dd is None:
            return df.copy()
        return dd.from_pandas(df, npartitions=max(1, min(8, len(df) // 10000 or 1))).compute()


class SparkBackend(AnalyticsBackend):
    def __init__(self, engine):
        super().__init__(engine)
        self._spark = None

    def _session(self):
        if SparkSession is None:
            return None
        if self._spark is None:
            self._spark = (SparkSession.builder.master('local[*]')
                           .appName('UnifiedAnalyticsEngine').getOrCreate())
        return self._spark

    def preprocess(self, df):
        s = self._session()
        if s is None:
            return df.copy()
        return s.createDataFrame(df).toPandas()


class _FallbackSentiment:
    """Tiny lexicon scorer used when NLTK VADER is unavailable."""
    POS = {'great', 'good', 'engaged', 'happy', 'love', 'excellent', 'normal', 'ok', 'fine'}
    NEG = {'stressed', 'bad', 'leave', 'suspicious', 'angry', 'hate', 'burnout', 'quit'}

    def polarity_scores(self, text: str) -> Dict[str, float]:
        toks = str(text).lower().split()
        if not toks:
            return {'compound': 0.0}
        s = sum((t in self.POS) - (t in self.NEG) for t in toks)
        return {'compound': float(np.tanh(s / 2.0))}


def _make_sentiment():
    if SentimentIntensityAnalyzer is not None:
        try:
            return SentimentIntensityAnalyzer()
        except LookupError:
            try:
                import nltk
                nltk.download('vader_lexicon', quiet=True)
                return SentimentIntensityAnalyzer()
            except Exception:
                pass
        except Exception:
            pass
    if not _WARNED.get('vader'):
        _WARNED['vader'] = True                              # once per process, not once per engine
        log.warning('VADER unavailable; using fallback lexicon sentiment.')
    return _FallbackSentiment()


class UnifiedAnalyticsEngine:
    """The quantum channel.

    Data flows through this engine as states flow through a quantum channel:

        frame  →  _build_slots()   basis selection (which Hilbert space)
               →  _indicator_vector()  state preparation  |ψ⟩ ∈ H
               →  _fill()          decoherence channel (NaN → training mean = mix with ρ_mixed)
               →  scaler.transform()   unitary change of basis (preserves inner products)
               →  predict()        POVM measurement (ensemble of models = effect operators)
               →  GapRegister      decoherence record (purity, environment coupling, which-path)
               →  base_rate        maximally mixed state contribution (Bayesian prior = ρ_mixed)

    fit_engine() fixes the Hilbert space (slot layout, scaler parameters, fill values)
    and trains the POVM operators (the models).  predict() prepares the incoming state
    in that fixed basis, applies the decoherence channel for any missing inputs, and
    measures with the POVM.

    The gap register is exact: imputation propagates through every extractor via its
    declared inputs, so completeness (= purity) is computed, not estimated.
    """
    def __init__(self, config: Optional[Any] = None, profile: Optional['DomainProfile'] = None):
        self.profile = profile
        if profile is not None:                      # profile supplies defaults; explicit config keys win
            base = {'chunk_rows': profile.effective_chunk_rows(), 'feature_dim': profile.feature_dim}
            config = ({**base, **config} if isinstance(config, dict)
                      else replace(config, **base) if config is not None else base)
        self.config = EngineConfig(**config) if isinstance(config, dict) else (config or EngineConfig())
        self.feature_engineering_methods: Dict[str, Callable] = {}
        self.scaler = StandardScaler()                # unitary change of basis (preserves inner products)
        self.imputer = SimpleImputer(strategy=self.config.imputation_strategy, keep_empty_features=True)  # decoherence channel
        self.tfidf_vectorizer = TfidfVectorizer(max_features=self.config.max_tfidf_features, stop_words='english')
        self.text_weights: Optional[np.ndarray] = None      # leading lexical axis (unsupervised: no label leakage)
        self.sentiment_analyzer = _make_sentiment()
        self.numeric_columns: List[str] = []
        self.slot_names: Optional[List[str]] = None       # basis vectors of H, fixed at fit
        self.feature_fill: Optional[np.ndarray] = None    # ρ_mixed amplitudes (training mean per basis vector)
        self.absent_slots: List[str] = []                 # basis vectors with no training observation (amplitude-damped to 0)
        self.plans_: List[SlotPlan] = []                  # per-basis-vector decoherence policy, fixed at fit
        self.extractor_meta: Dict[str, Extractor] = {}
        self.slot_importance: Optional[np.ndarray] = None  # POVM weight per basis vector (mean model importance)
        self.base_rate: Optional[float] = None             # maximally mixed state contribution (Bayesian prior = ρ_mixed)
        self.dropped_for_width: List[str] = []             # DOFs removed during Hilbert-space dimensional reduction
        self.absence_columns: List[str] = []              # DOFs whose decoherence is informative (which-path flags)
        self.constant_slots: List[str] = []               # constant across every training chunk (data-induced)
        self._train_matrix: Optional[np.ndarray] = None
        self.is_fitted = False
        self._backends: Dict[str, AnalyticsBackend] = {}
        self.backend = self._select_backend()
        os.makedirs(self.config.model_dir, exist_ok=True)
        self._load_artifacts()
        self.models = self._load_models()
        self.is_fitted = self.is_fitted and bool(self.models)
        self.wide_vs_chunks = False
        if profile is not None:                      # a domain's extractors are registered, not hard-coded
            for n, fn in profile.extractors.items():
                self.add_feature_engineering(n, fn)

    # ---- backend selection -------------------------------------------------
    def _make_backend(self, name: str) -> AnalyticsBackend:
        if name not in self._backends:
            cls = {'spark': SparkBackend, 'dask': DaskBackend}.get(name, PandasBackend)
            self._backends[name] = cls(self)
        return self._backends[name]

    def _select_backend(self):
        name = self.config.backend
        return self._make_backend('pandas' if name == 'auto' else name)

    def _backend_for(self, rows: int) -> AnalyticsBackend:
        if self.config.backend != 'auto':
            return self.backend
        return self._make_backend(DistributedHeuristics.choose_backend(
            rows, 'auto', self.config.dask_threshold_rows, self.config.spark_threshold_rows))

    # ---- persistence -------------------------------------------------------
    def _path(self, fn: str) -> str:
        return os.path.join(self.config.model_dir, fn)

    def _load_artifacts(self):
        loaded = 0
        for attr, fn in {'scaler': 'scaler.joblib', 'imputer': 'imputer.joblib'}.items():
            if os.path.exists(self._path(fn)):
                setattr(self, attr, joblib.load(self._path(fn)))
                loaded += 1
        meta = self._path('meta.joblib')
        if os.path.exists(meta):
            m = joblib.load(meta)
            if m.get('slot_names') is not None and m.get('plans') is not None:   # older layouts are stale
                n_in = getattr(self.scaler, 'n_features_in_', None)
                if n_in is not None and len(m['slot_names']) != n_in:
                    raise ValueError(f"artifact layout has {len(m['slot_names'])} slots but the scaler "
                                     f"expects {n_in}; artifacts are inconsistent, refit")
                self.numeric_columns = m['numeric_columns']
                self._train_matrix = m['train_matrix']
                self.slot_names = m['slot_names']
                self.feature_fill = m['feature_fill']
                self.tfidf_vectorizer = m.get('tfidf_vectorizer', self.tfidf_vectorizer)
                self.text_weights = m.get('text_weights')
                self.absent_slots = m.get('absent_slots', [])
                self.plans_ = m['plans']
                self.slot_importance = m.get('slot_importance')
                self.base_rate = m.get('base_rate')
                self.dropped_for_width = m.get('dropped_for_width', [])
                self.absence_columns = m.get('absence_columns', [])
                loaded += 1
        self.is_fitted = loaded == 3

    def _save_artifacts(self):
        joblib.dump(self.scaler, self._path('scaler.joblib'))
        joblib.dump(self.imputer, self._path('imputer.joblib'))
        joblib.dump({'numeric_columns': self.numeric_columns, 'train_matrix': self._train_matrix,
                     'slot_names': self.slot_names, 'feature_fill': self.feature_fill,
                     'tfidf_vectorizer': self.tfidf_vectorizer, 'text_weights': self.text_weights,
                     'absent_slots': self.absent_slots, 'plans': self.plans_,
                     'slot_importance': self.slot_importance, 'base_rate': self.base_rate,
                     'dropped_for_width': self.dropped_for_width, 'absence_columns': self.absence_columns},
                    self._path('meta.joblib'))

    def _load_models(self) -> Dict[str, Any]:
        models = {}
        for name in self.config.model_names:
            p = self._path(f'{name}.joblib')
            if os.path.exists(p):
                models[name] = joblib.load(p)
        return models  # never trains on synthetic noise: unfitted engine raises in predict()

    def add_feature_engineering(self, name: str, fn: Any, inputs: Optional[Sequence[str]] = None,
                                needs_window: int = 1, emits_indicator: bool = False):
        """Custom features return scalars and must be registered BEFORE fit_engine() (layout is fixed at fit;
        after fit/load only names already in the saved layout may be re-registered).
        Declare `inputs` so missing data propagates exactly; undeclared features are treated conservatively."""
        ext = (Extractor(name, fn.fn, fn.inputs, fn.needs_window, fn.emits_indicator)
               if isinstance(fn, Extractor)
               else Extractor(name, fn, None if inputs is None else tuple(inputs), needs_window, emits_indicator))
        if self.slot_names is not None and f'custom.{name}' not in self.slot_names:
            raise RuntimeError(f"cannot add new feature '{name}' after fit: the slot layout is fixed; "
                               "register custom features before fit_engine() and refit")
        self.feature_engineering_methods[name] = ext.fn
        self.extractor_meta[name] = ext

    # ---- models ------------------------------------------------------------
    def _default_model(self, name):
        c = self.config
        if name == 'rf':
            return RandomForestClassifier(n_estimators=c.n_estimators, max_depth=c.max_depth, random_state=42)
        if name == 'gb':
            return GradientBoostingClassifier(random_state=42)
        if name == 'xgb':
            return None if XGBClassifier is None else XGBClassifier(
                n_estimators=c.n_estimators, max_depth=c.max_depth, learning_rate=c.learning_rate,
                eval_metric='logloss', random_state=42)
        if name == 'lgbm':
            return None if LGBMClassifier is None else LGBMClassifier(
                n_estimators=c.n_estimators, max_depth=c.max_depth, learning_rate=c.learning_rate,
                random_state=42, verbose=-1, min_child_samples=2)
        if name == 'lr':
            return LogisticRegression(max_iter=1000)
        raise ValueError(f'Unknown model name: {name}')

    # ---- feature extraction ------------------------------------------------
    def _extract_text_sentiment(self, text):
        if not isinstance(text, str):
            return 0.0
        return float(self.sentiment_analyzer.polarity_scores(text)['compound'])

    def _texts(self, df: pd.DataFrame) -> Optional[List[str]]:
        cols = [c for c in TEXT_COLUMNS if c in df.columns]
        if not cols:
            return None
        return df[cols].fillna('').astype(str).agg(' '.join, axis=1).tolist()

    def _fit_text(self, df: pd.DataFrame) -> None:
        """TF-IDF over survey/communication text; the leading SVD axis becomes the 'topic_axis' signal.
        Unsupervised on purpose: a label-derived text score computed on the same rows the models
        train on would leak the target into the features."""
        self.text_weights = None
        texts = self._texts(df)
        if not texts or not any(t.strip() for t in texts):
            return
        try:
            X = self.tfidf_vectorizer.fit_transform(texts)
            if X.shape[1] < 2:
                return
            w = TruncatedSVD(n_components=1, random_state=42).fit(X).components_[0].copy()
        except ValueError:                       # empty vocabulary (e.g. only stop words)
            return
        if w[np.argmax(np.abs(w))] < 0:          # deterministic sign convention
            w = -w
        self.text_weights = w

    def _absence_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        """Which-path record:  per-row 0/1 flags marking which DOFs the environment absorbed.
        Computed on the RAW frame before the decoherence channel (imputation) destroys the
        evidence.  A column absent entirely is decohered on every row."""
        cols = {f'__absent__{c}': (np.ones(len(df)) if c not in df.columns else df[c].isna().to_numpy(float))
                for c in self.absence_columns}
        return pd.DataFrame(cols, index=df.index)

    def _prep(self, df: pd.DataFrame) -> pd.DataFrame:
        """Kraus map:  impute (apply the decoherence channel) but preserve the which-path
        information for columns that declared absence informative — the Kraus operators
        record which environment branch the state decohered into, not just that it did."""
        absent = self._absence_frame(df)
        out = self._impute(df)
        return pd.concat([out, absent], axis=1) if len(absent.columns) else out

    def _trend(self, df: pd.DataFrame) -> float:
        s = df[['date', 'performance_score']].dropna().copy()
        s['date'] = pd.to_datetime(s['date'])
        s = s.sort_values('date')
        y = s['performance_score'].to_numpy(dtype=float)
        if len(y) < 2:
            return 0.0
        if seasonal_decompose is not None and len(y) >= 6:
            try:
                period = min(5, max(2, len(y) // 2))
                d = seasonal_decompose(pd.Series(y), model='additive', period=period,
                                       extrapolate_trend='freq')
                return float(np.nanmean(np.gradient(d.trend.to_numpy())))
            except Exception:
                pass
        return float(np.polyfit(np.arange(len(y)), y, 1)[0])  # slope per step

    def _extract_risk_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extract observables from the frame — the raw measurements that _prepare_input_features
        projects onto the Hilbert-space basis.  Each group (performance_metrics, text_signal, etc.)
        is one block of the observation; custom extractors extend the observable algebra."""
        out: Dict[str, Any] = {}
        cols = df.columns
        if 'performance_score' in cols:
            out['performance_metrics'] = {'mean': float(df['performance_score'].mean()),
                                          'std': float(df['performance_score'].std(ddof=0) or 0)}
        if 'survey_text' in cols:
            out['engagement_metrics'] = {
                'sentiment': float(df['survey_text'].fillna('').map(self._extract_text_sentiment).mean())}
        if 'date' in cols and 'performance_score' in cols and len(df) > 2:
            out['trend_metrics'] = {'trend': self._trend(df)}
        texts = self._texts(df)
        if texts is not None and self.text_weights is not None:
            X = self.tfidf_vectorizer.transform(texts)
            toks = [t for doc in texts for t in self.tfidf_vectorizer.build_analyzer()(doc)]
            out['text_signal'] = {'topic_axis': float(X.dot(self.text_weights).mean()),
                                  'lexical_diversity': float(len(set(toks)) / len(toks)) if toks else np.nan}
        num = df.select_dtypes(include=[np.number])
        if not num.empty:
            out['numeric_means'] = {c: float(num[c].mean()) for c in num.columns
                                    if c != 'performance_score' and not c.startswith('__absent__')}
        if self.absence_columns:
            out['absent'] = {c: float(df[f'__absent__{c}'].mean()) for c in self.absence_columns
                             if f'__absent__{c}' in df.columns}
        for k, fn in self.feature_engineering_methods.items():
            out[k] = fn(df)
        return out

    def _applicable_fixed(self, df: pd.DataFrame) -> List[str]:
        """Built-in indicator slots that the frame can actually support (HR-origin catalog, used only if present)."""
        cols, out = set(df.columns), []
        if 'performance_score' in cols:
            out += ['performance_metrics.mean', 'performance_metrics.std']
            if 'date' in cols and self.config.chunk_rows > 2:
                out.append('trend_metrics.trend')
        if 'survey_text' in cols:
            out.append('engagement_metrics.sentiment')
        if self.text_weights is not None:
            out += ['text_signal.topic_axis', 'text_signal.lexical_diversity']
        return out

    def _rank_numeric(self, df: pd.DataFrame, cols: List[str], y: Optional[np.ndarray] = None) -> List[str]:
        """Gauge-invariant feature ordering.

        Rank IS the observable invariant under all strictly monotone per-feature
        transformations — the gauge group of the feature space.  This method selects
        which basis vectors survive dimensional reduction of the Hilbert space, using
        only gauge-invariant statistics:

        * needs >= MIN_RANK_SAMPLES samples, else name order (a ranking on fewer is noise);
        * windows (chunk_rows >= 2): between-chunk / within-chunk variance ratio (units cancel);
        * cross_sectional (1 row per vector): |Spearman ρ with the label| on TRAINING rows
          (rank-based, invariant to any monotone rescaling).  Plain variance is NOT gauge-
          invariant and would rank by units.  Without labels there is no gauge-invariant
          signal, so the order falls back to name and a warning says so.
        * The statistic is rounded (RHO_DECIMALS) so near-ties become real ties; ties
          resolve by NAME (invariant under rescaling; variance would break gauge)."""
        k = self.config.chunk_rows
        n_samples = len(df) if k < 2 else len(df) // k
        if n_samples < MIN_RANK_SAMPLES:
            log.warning('only %d samples (< %d): a rank statistic would be noise; keeping columns in name order',
                        n_samples, MIN_RANK_SAMPLES)
            return sorted(cols)
        if k < 2:
            if y is not None and len(y) == len(df) and len(np.unique(y)) > 1:
                yr = pd.Series(np.asarray(y, float)).rank().to_numpy()
                sc = []
                for c in cols:
                    xr = df[c].rank().to_numpy()
                    sc.append(0.0 if xr.std() == 0 else round(abs(float(np.corrcoef(xr, yr)[0, 1])), RHO_DECIMALS))
                return [cols[j] for j in sorted(range(len(cols)), key=lambda j: (-sc[j], cols[j]))]
            log.warning('cross_sectional width bound without labels: no scale-free ranking exists, '
                        'keeping columns in name order')
            return sorted(cols)
        if len(cols) < 2 or len(df) < 2 * k:
            return sorted(cols)
        idx = np.array_split(np.arange(len(df)), max(1, len(df) // k))
        arr = df[cols].to_numpy(float)
        means = np.vstack([np.nanmean(arr[i], axis=0) for i in idx])
        within = np.mean([np.nanvar(arr[i], axis=0, ddof=1) / len(i) for i in idx if len(i) > 1], axis=0)
        f = np.round(np.nan_to_num(np.nanvar(means, axis=0, ddof=1) / (within + 1e-12)), RHO_DECIMALS)
        order = sorted(range(len(cols)), key=lambda j: (-float(f[j]), cols[j]))
        return [cols[j] for j in order]

    def _build_slots(self, df: pd.DataFrame, y: Optional[np.ndarray] = None):
        """Measurement-induced basis selection:  the frame DETERMINES the Hilbert space.

        Which degrees of freedom survive ranking, which get dropped for width, which
        absence flags promote to first-class basis vectors — all decided here and fixed
        at fit.  The resulting slot layout IS the orthonormal basis of the state space H
        that every subsequent state preparation and POVM measurement operates in.

        Width bounding (feature_dim, chunks_per_feature) is dimensional reduction of H;
        anything cut is recorded in dropped_for_width.  `absence_columns` is set by
        fit_engine BEFORE _prep: the which-path flags must be read off the raw frame."""
        custom = sorted(self.feature_engineering_methods)
        for n in custom:                                   # window contract: refuse, don't zero
            ext = self.extractor_meta.get(n)
            if ext is not None and self.config.chunk_rows < ext.needs_window:
                raise DataContractError(f"extractor '{n}' needs a window of {ext.needs_window} rows but "
                                        f"chunk_rows={self.config.chunk_rows}; use a series mode or a row-local extractor")
        fixed = self._applicable_fixed(df)
        cols = sorted(c for c in self.numeric_columns if c != 'performance_score')
        budget = None
        if self.config.feature_dim is not None:
            headroom = self.config.feature_dim - len(fixed) - len(custom) - len(self.absence_columns)
            if headroom <= 0:
                log.warning('feature_dim=%d leaves no room for numeric columns after %d built-in and %d custom '
                            'slots; width will exceed feature_dim (built-in and custom slots are never dropped)',
                            self.config.feature_dim, len(fixed), len(custom))
            budget = max(0, headroom)
        if self.config.chunks_per_feature:
            n_chunks = max(1, len(df) // max(1, self.config.chunk_rows))
            b2 = max(1, n_chunks // self.config.chunks_per_feature)
            budget = b2 if budget is None else min(budget, b2)
        kept, dropped = cols, []
        if budget is not None and len(cols) > budget:
            kept = sorted(self._rank_numeric(df, cols, y)[:budget])
            dropped = sorted(set(cols) - set(kept))
            log.warning('width bounded to %d numeric slots; dropped %d columns', budget, len(dropped))
        self.dropped_for_width = dropped

        text_in = tuple(c for c in TEXT_COLUMNS if c in df.columns)
        fixed_inputs = {'performance_metrics.mean': ('performance_score',), 'performance_metrics.std': ('performance_score',),
                        'trend_metrics.trend': ('performance_score', 'date'),
                        'engagement_metrics.sentiment': ('survey_text',),
                        'text_signal.topic_axis': text_in, 'text_signal.lexical_diversity': text_in}
        plans = [SlotPlan(n, Fill.MEDIAN, 0.0, fixed_inputs[n]) for n in fixed]
        plans += [SlotPlan(f'numeric_means.{c}', Fill.MEDIAN, 0.0, (c,)) for c in kept]
        plans += [SlotPlan(f'absent.{c}', Fill.ZERO, 0.0, (c,)) for c in self.absence_columns]   # 0 == present
        for n in custom:
            ext = self.extractor_meta.get(n)
            plans.append(SlotPlan(f'custom.{n}', Fill.ZERO if (ext and ext.emits_indicator) else Fill.MEDIAN, 0.0,
                                  None if ext is None else ext.inputs))
        self.plans_ = plans
        self.slot_names = [p.name for p in plans]

    def _prepare_input_features(self, indicators: Dict[str, Any]) -> np.ndarray:
        """Project extracted observables onto the slot basis → raw amplitudes in H.

        A missing indicator is NaN here; the decoherence channel (_fill) replaces it with
        its training mean downstream (mixing with ρ_mixed along that dimension).  A slot
        with no training observation at all (absent_slots) has no mean to use — it fills
        with 0.0 (amplitude damping to ground) and is reported, never hidden."""
        if self.slot_names is None:
            raise RuntimeError('Feature layout not defined yet; fit the engine first.')
        unregistered = [n[len('custom.'):] for n in self.slot_names
                        if n.startswith('custom.') and n[len('custom.'):] not in self.feature_engineering_methods]
        if unregistered:
            raise RuntimeError(f'custom features {unregistered} are part of the fitted layout but are not '
                               'registered; call add_feature_engineering() for them before predicting')
        vals: List[float] = []
        for slot in self.slot_names:
            group, _, key = slot.partition('.')
            if group == 'custom':
                v = indicators.get(key)
                if v is not None and not isinstance(v, (int, float, np.number)):
                    raise TypeError(f"Custom feature '{key}' must return a scalar, got {type(v).__name__}")
            else:
                bucket = indicators.get(group)
                v = bucket.get(key) if isinstance(bucket, dict) else None
            vals.append(float(v) if v is not None else np.nan)
        return np.asarray(vals, dtype=float)

    def _fill(self, vec: np.ndarray) -> np.ndarray:
        """Decoherence channel:  NaN slots (missing observations) are replaced with their
        training mean — mixing the prepared state with the maximally mixed state ρ_mixed
        along the decohered dimensions.  A fully observed state passes through unchanged
        (pure); each NaN drives one dimension toward maximum entropy."""
        if self.feature_fill is None:
            return vec
        return np.where(np.isnan(vec), self.feature_fill, vec)



    def _indicator_vector(self, df: pd.DataFrame) -> np.ndarray:
        """State preparation:  raw frame  →  |ψ⟩ in the slot-space Hilbert basis.

        The basis was fixed at fit time by _build_slots(); this method projects the incoming
        frame onto that basis.  Preps unless already prepped, so absence flags (which-path
        information) are never read as 'present' by a caller that skipped _prep.
        Pass the raw frame: an already-imputed frame has lost the decoherence evidence."""
        if self.absence_columns and not any(str(c).startswith('__absent__') for c in df.columns):
            df = self._prep(df)
        return self._fill(self._prepare_input_features(self._extract_risk_indicators(df)))

    def _chunked_matrix(self, df: pd.DataFrame, y: Optional[np.ndarray] = None):
        """Tensor product structure:  chunk_rows defines how rows compose into states.
        Each chunk becomes one ket |ψ_k⟩ in H; the training matrix is the collection of
        prepared states the POVM operators (models) are trained against."""
        n_chunks = max(1, len(df) // max(1, self.config.chunk_rows))
        frames = np.array_split(np.arange(len(df)), n_chunks)
        X = np.vstack([self._indicator_vector(df.iloc[idx]) for idx in frames])
        yc = None
        if y is not None:
            yc = np.array([int(np.mean(y[idx]) >= 0.5) for idx in frames])
        return X, yc

    def _impute(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply the depolarising channel to all numeric DOFs: NaN → training mean.
        An entirely absent column is set to NaN first (full decoherence on that axis),
        not silently zeroed — amplitude damping would be dishonest here."""
        if not self.numeric_columns:
            return df
        df = df.copy()
        for c in self.numeric_columns:
            if c not in df.columns:
                df[c] = np.nan                       # absent column -> full decoherence, not silent zero
        df[self.numeric_columns] = self.imputer.transform(df[self.numeric_columns])
        return df

    # ---- fit (fix the Hilbert space) / predict (POVM measurement) ----------
    def fit_engine(self, X_train: pd.DataFrame, y_train: Optional[pd.Series] = None):
        """Fix the Hilbert space and train the POVM operators.

        _build_slots() selects the measurement basis (which DOFs become basis vectors).
        _chunked_matrix() prepares the training states.  The models trained here ARE
        the effect operators of the POVM that predict() will apply.  The scaler
        parameters, fill values, and slot layout are the channel's fixed structure —
        they do not change after fit."""
        if self.profile is not None:
            missing = self.profile.missing_required(X_train)
            if missing:
                raise DataContractError(f"profile '{self.profile.name}' requires columns {missing}")
        df = self._backend_for(len(X_train)).preprocess(X_train.copy()).reset_index(drop=True)
        y = None
        if y_train is not None:
            y = np.asarray(y_train).astype(int)
            if len(y) != len(df):
                raise ValueError(f'y_train has {len(y)} rows but X_train has {len(df)}')

        num = df.select_dtypes(include=[np.number])
        self.numeric_columns = list(num.columns)
        if not num.empty:
            self.imputer.fit(num)
        declared = list(self.profile.informative_absence) if self.profile is not None else None
        self.absence_columns = declared if declared is not None else list(self.absence_columns)   # reload keeps its own
        df = self._prep(df)
        self._fit_text(df)

        self.feature_fill = None
        self._build_slots(df, y)
        if self.profile is not None and self.profile.expected_width is not None \
                and len(self.slot_names) != self.profile.expected_width:
            raise DataContractError(f"profile '{self.profile.name}' expects width {self.profile.expected_width}, "
                                    f"frame produced {len(self.slot_names)}")
        X, yc = self._chunked_matrix(df, y)                  # raw: NaN where an indicator is absent
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)
            med = np.nanmedian(X, axis=0)                    # robust: median, not mean
        absent = np.isnan(X).all(axis=0)
        for plan, m, gone in zip(self.plans_, med, absent):
            plan.fill_value = 0.0 if (gone or plan.fill is Fill.ZERO) else float(m)
        fill = np.array([p.fill_value for p in self.plans_])
        self.feature_fill = fill
        self.absent_slots = [n for n, gone in zip(self.slot_names, absent) if gone]
        if self.absent_slots:
            log.warning('Slots with no training observation (filled with 0.0): %s', self.absent_slots)
        self.wide_vs_chunks = X.shape[1] > X.shape[0]
        if self.wide_vs_chunks:
            log.warning('Width %d exceeds the %d training chunks: expect overfitting; set chunks_per_feature or feature_dim.',
                        X.shape[1], X.shape[0])
        X = np.where(np.isnan(X), fill, X)
        self.constant_slots = []
        stray = []
        for plan, col in zip(self.plans_, X.T):
            if plan.name in self.absent_slots or float(np.nanstd(col)) != 0.0:
                continue
            self.constant_slots.append(plan.name)
            if plan.name.startswith('absent.'):
                continue                                     # nothing was missing in training: legitimately constant
            srcs = [c for c in (plan.derived_from or ()) if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
            if any(float(np.nanstd(df[c].to_numpy(float))) > 0 for c in srcs):
                stray.append(plan.name)                      # inputs VARY but the slot does not: the engine broke it
        if stray:
            raise DataContractError(f'slots constant across every training chunk although their inputs vary: {stray}')
        dead_flags = [n for n in self.constant_slots if n.startswith('absent.')]
        other = [n for n in self.constant_slots if not n.startswith('absent.')]
        if dead_flags:
            log.warning('informative_absence declared for %s but no training chunk had it missing: the flag carries '
                        'no information until training data contains the absence', [n[len('absent.'):] for n in dead_flags])
        if other:
            log.warning('slots constant across every training chunk (the data, not the layout): %s', other)
        if yc is None:
            yc = (X[:, 0] > np.median(X[:, 0])).astype(int)
        if len(X) < 4 or len(np.unique(yc)) < 2:
            raise ValueError(
                f'Need >= 4 chunks with both classes present (got {len(X)} chunks, '
                f'classes={np.unique(yc).tolist()}). Provide more rows or lower chunk_rows.')

        self.scaler.fit(X)
        self._train_matrix = self.scaler.transform(X)
        self.models = {}
        for name in self.config.model_names:
            model = self._default_model(name)
            if model is None:
                log.warning('Model %s skipped: dependency not installed.', name)
                continue
            model.fit(self._train_matrix, yc)
            joblib.dump(model, self._path(f'{name}.joblib'))
            self.models[name] = model
        imps = []
        for m in self.models.values():
            fi = getattr(m, 'feature_importances_', None)
            if fi is not None and len(fi) == X.shape[1]:
                fi = np.asarray(fi, float)
                imps.append(fi / fi.sum() if fi.sum() > 0 else np.ones_like(fi) / len(fi))
        self.slot_importance = np.mean(imps, axis=0) if imps else np.ones(X.shape[1]) / X.shape[1]
        self.base_rate = float(np.mean(yc))
        self._save_artifacts()
        self.is_fitted = True
        return self

    def predict(self, data) -> Dict[str, Any]:
        """POVM measurement on a single prepared state.

        State preparation (_indicator_vector) → decoherence channel (_fill: NaN → training
        mean = partial depolarisation) → unitary basis change (scaler) → measurement by N
        effect operators (models), each returning a Born-rule outcome (score).  The
        weighted mean of the scores IS the expectation value of the ensemble observable.
        The GapRegister records the decoherence: completeness = purity, missing_inputs =
        environmental DOFs the state coupled to, absence_captured = which-path flags that
        were promoted to informative basis vectors rather than lost."""
        if not self.is_fitted or not self.models:
            raise RuntimeError('Engine is not fitted. Call fit_engine first or load persisted artifacts.')
        raw = data.copy() if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
        imputed_cols = [c for c in self.numeric_columns if c not in raw.columns]
        df = self._prep(self._backend_for(len(raw)).preprocess(raw))
        indicators = self._extract_risk_indicators(df)
        vec = self._prepare_input_features(indicators)
        all_inputs = {c for p in self.plans_ for c in (p.derived_from or ())}
        missing_inputs = sorted({c for c in all_inputs | set(self.numeric_columns)
                                 if c not in raw.columns or raw[c].isna().all()})
        imputed_numeric = sorted(set(imputed_cols) | {c for c in self.numeric_columns
                                                      if c in raw.columns and raw[c].isna().all()})
        gaps = GapRegister.build(self.plans_, [n for n, m in zip(self.slot_names, np.isnan(vec)) if m],
                                 missing_inputs, imputed_numeric, self.absent_slots,
                                 self.dropped_for_width, self.slot_importance).to_dict()
        gaps['absence_captured'] = sorted(c for c, v in indicators.get('absent', {}).items() if v > 0)
        x = self.scaler.transform(self._fill(vec).reshape(1, -1))
        if x.shape[1] != len(self.plans_):
            raise RuntimeError(f'scaler produced {x.shape[1]} columns for a {len(self.plans_)}-slot layout')
        preds = {}
        for name, model in self.models.items():
            if hasattr(model, 'predict_proba'):
                proba = model.predict_proba(x)[0]
                sc = proba[list(model.classes_).index(1)] if 1 in model.classes_ else 0.0
            else:
                sc = float(model.predict(x)[0])
            preds[name] = {'score': float(sc), 'weight': 1.0, 'confidence': 0.9}
        score = float(np.mean([v['score'] for v in preds.values()]))
        return {'score': score, 'models': preds, 'indicators': indicators, 'gaps': gaps,
                'backend': self.config.backend}

    def predict_each(self, data: pd.DataFrame) -> pd.DataFrame:
        """POVM measurement on every prepared state in the frame (one per chunk;
        cross_sectional mode: one per row).  Returns the expectation value, purity
        (completeness), and decoherence weight for each state."""
        df = data.reset_index(drop=True)
        n_chunks = max(1, len(df) // max(1, self.config.chunk_rows))
        rows = []
        for idx in np.array_split(np.arange(len(df)), n_chunks):
            r = self.predict(df.iloc[idx])
            g = r['gaps']
            rows.append({'start': int(idx[0]), 'stop': int(idx[-1]) + 1, 'score': r['score'],
                         'n_filled': len(g['filled']), 'completeness': g['completeness'],
                         'completeness_weighted': g['completeness_weighted'],
                         'imputed': ';'.join(g['imputed_columns']), 'affected': ';'.join(g['affected_slots']),
                         **{f'p_{m}': v['score'] for m, v in r['models'].items()}})
        return pd.DataFrame(rows)

    def explain(self, data):
        if lime_tabular is None:
            raise ImportError('lime is required for explain(); pip install lime')
        if self._train_matrix is None:
            raise RuntimeError('No training matrix available; fit the engine first.')
        df = self._prep(data.copy())
        x = self.scaler.transform(self._indicator_vector(df).reshape(1, -1))
        model = self.models[self._selected_name()]
        explainer = lime_tabular.LimeTabularExplainer(
            self._train_matrix, mode='classification', feature_names=list(self.slot_names),
            discretize_continuous=False)
        return explainer.explain_instance(
            x[0], model.predict_proba, num_features=min(5, x.shape[1])).as_list()

    def _selected_name(self) -> str:
        if not self.models:
            raise RuntimeError('No fitted models available.')
        sel = self.config.selected_model
        return sel if sel in self.models else next(iter(self.models))

    def benchmark(self, X: pd.DataFrame, y) -> Dict[str, float]:
        if not self.is_fitted:
            raise RuntimeError('Engine is not fitted.')
        df = self._prep(X.copy().reset_index(drop=True))
        M, yc = self._chunked_matrix(df, np.asarray(y).astype(int))
        name = self._selected_name()
        p = self.models[name].predict(self.scaler.transform(M))
        correct = int((np.asarray(p) == yc).sum())
        return {'model': name, 'ci95': wilson_interval(correct, len(yc)), 'f1': f1_score(yc, p, zero_division=0),
                'precision': precision_score(yc, p, zero_division=0),
                'recall': recall_score(yc, p, zero_division=0), 'accuracy': accuracy_score(yc, p),
                'n_chunks': int(len(yc))}

    def cleanup(self):
        tf = _optional('tensorflow')
        if tf is not None:
            tf.keras.backend.clear_session()
        gc.collect()


# ---------------------------
# Extended system utilities
# ---------------------------

class DataContractError(Exception):
    pass


class FeatureRegistry:
    def __init__(self): self._registry: Dict[str, Callable] = {}
    def register(self, name: str, fn: Callable): self._registry[name] = fn
    def items(self): return self._registry.items()


class ModelRegistry:
    def __init__(self): self._registry: Dict[str, Any] = {}
    def register(self, name: str, model): self._registry[name] = model
    def get(self, name): return self._registry.get(name)
    def items(self): return self._registry.items()


class UnifiedAnalyticsOrchestrator:
    def __init__(self, engine: UnifiedAnalyticsEngine, sector: Optional[str] = None):
        self.engine = engine
        self.feature_registry = FeatureRegistry()
        self.model_registry = ModelRegistry()
        self.audit_log: List[Dict[str, Any]] = []
        self.monitor = PerformanceMonitor()
        self.persistence = PersistenceManager(engine.config.model_dir)
        self.profile = engine.profile or (SectorProfiles.by_name(sector) if sector else None)
        self.sector = sector or (self.profile.name if self.profile else None)

    @classmethod
    def for_domain(cls, name: str, model_dir: str, **config) -> 'UnifiedAnalyticsOrchestrator':
        """Domain by registry name: engine + profile + contract, no branching in code."""
        engine = UnifiedAnalyticsEngine({'model_dir': model_dir, **config}, profile=SectorProfiles.by_name(name))
        return cls(engine)

    def register_feature(self, name: str, fn: Any, **contract):
        self.feature_registry.register(name, fn)
        self.engine.add_feature_engineering(name, fn, **contract)
        self.audit_log.append({'event': 'register_feature', 'name': name})

    def register_model(self, name: str, model):
        self.model_registry.register(name, model)
        self.engine.models[name] = model
        self.audit_log.append({'event': 'register_model', 'name': name})

    def validate_contract(self, df: pd.DataFrame):
        if not isinstance(df, pd.DataFrame):
            raise DataContractError('Input must be a pandas DataFrame')
        if df.empty:
            raise DataContractError('Input DataFrame is empty')
        missing = []
        if self.profile:
            hard = self.profile.missing_required(df)
            if hard:
                raise DataContractError(f"profile '{self.profile.name}' requires columns {hard}")
            missing = self.profile.missing_signals(df)
            if missing:
                log.warning('Sector %s: missing primary signals %s', self.sector, missing)
        self.audit_log.append({'event': 'validate_contract', 'rows': len(df), 'cols': list(df.columns),
                               'sector': self.sector, 'missing_signals': missing})
        return True

    def fit(self, df: pd.DataFrame, y: Optional[pd.Series] = None):
        self.validate_contract(df)
        t0 = time.perf_counter()
        self.engine.fit_engine(df, y)
        dt = time.perf_counter() - t0
        self.monitor.log('fit_seconds', dt)
        self.monitor.log('fit_rows', len(df))
        self.persistence.save_json({
            'sector': self.sector, 'rows': len(df), 'models': sorted(self.engine.models),
            'slot_names': self.engine.slot_names, 'numeric_columns': self.engine.numeric_columns,
            'text_signal_active': self.engine.text_weights is not None,
            'absent_slots': self.engine.absent_slots, 'width': len(self.engine.slot_names),
            'mode': self.profile.mode if self.profile else None, 'chunk_rows': self.engine.config.chunk_rows,
            'wide_vs_chunks': self.engine.wide_vs_chunks, 'dropped_for_width': self.engine.dropped_for_width,
            'fit_seconds': dt, 'config': asdict(self.engine.config)}, 'manifest.json')
        self.audit_log.append({'event': 'fit', 'rows': len(df)})
        return self

    def predict(self, df: pd.DataFrame):
        self.validate_contract(df)
        t0 = time.perf_counter()
        pred = self.engine.predict(df)
        self.monitor.log('predict_seconds', time.perf_counter() - t0)
        self.monitor.log('predict_score_classical', pred.get('score'))
        self.audit_log.append({'event': 'predict', 'rows': len(df), 'score': pred.get('score')})
        return pred

    def explain(self, df: pd.DataFrame):
        self.validate_contract(df)
        exp = self.engine.explain(df)
        self.audit_log.append({'event': 'explain', 'rows': len(df)})
        return exp

    def export_audit_log(self, path: str = 'output/audit_log.csv'):
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        pd.DataFrame(self.audit_log).to_csv(path, index=False)
        return path


def _has(df: pd.DataFrame, *cols: str) -> bool:
    return all(c in df.columns for c in cols)


def _slope(x: np.ndarray) -> float:
    return float(np.polyfit(np.arange(len(x)), x, 1)[0]) if len(x) >= 3 else np.nan


ALLOWED_ASSERTS: set = set()   # qualified names ('Class.method') of deliberately kept precondition asserts
_WARNED: Dict[str, bool] = {}
RHO_DECIMALS = 6          # near-ties in a rank statistic are numerical noise: round, then break by name
MIN_RANK_SAMPLES = 20      # below this a rank statistic is noise: a column can top the ranking by chance

NEGATIVE_TERMS = ('stressed', 'leave', 'quit', 'burnout', 'angry')

# --- extractors: row-frame -> scalar (NaN = "not observable"), the ONLY place a domain touches the engine ---
def hr_perf_volatility(df): return float(df['performance_score'].std(ddof=0) / (df['performance_score'].mean() + 1e-9)) if _has(df, 'performance_score') else np.nan
def hr_negative_text_share(df): return float(df['survey_text'].fillna('').str.contains('|'.join(NEGATIVE_TERMS)).mean()) if _has(df, 'survey_text') else np.nan
def fin_velocity_p90(df): return float(df['transaction_velocity'].quantile(0.9)) if _has(df, 'transaction_velocity') else np.nan
def fin_risk_interaction(df): return float((df['device_risk'] * df['session_anomaly']).mean()) if _has(df, 'device_risk', 'session_anomaly') else np.nan
def fin_suspicious_share(df): return float((df['survey_text'] == 'suspicious').mean()) if _has(df, 'survey_text') else np.nan
def sc_delay_p90(df): return float(df['route_delay'].quantile(0.9)) if _has(df, 'route_delay') else np.nan
def sc_delivery_cv(df): return float(df['delivery_time'].std(ddof=0) / (df['delivery_time'].mean() + 1e-9)) if _has(df, 'delivery_time') else np.nan
def sc_delay_slope(df): return _slope(df['route_delay'].to_numpy(float)) if _has(df, 'route_delay') else np.nan
def sc_exposure(df): return float((df['supplier_risk'] * df['weather']).mean()) if _has(df, 'supplier_risk', 'weather') else np.nan


@dataclass
class DomainProfile:
    """A domain as a declared module: contract + extractors + sampling mode.  Adding a domain is data."""
    name: str
    description: str = ''
    required_columns: tuple = ()          # hard contract: fit/predict raise if absent
    primary_signals: tuple = ()           # soft contract: absence is logged and recorded in the audit trail
    informative_absence: tuple = ()       # columns whose ABSENCE is itself a signal (missing-not-at-random)
    extractors: Dict[str, Any] = field(default_factory=dict)   # name -> Extractor (callables are coerced)
    mode: str = 'series'                  # 'series' (chunk_rows rows per vector) | 'cross_sectional' (1 row)
    chunk_rows: int = 10
    feature_dim: Optional[int] = None     # None = derived width
    expected_width: Optional[int] = None  # optional contract on the derived width
    notes: str = ''

    def __post_init__(self):
        if self.mode not in ('series', 'cross_sectional'):
            raise DataContractError(f"mode must be 'series' or 'cross_sectional', got {self.mode!r}")
        self.extractors = {n: Extractor.coerce(n, e) for n, e in self.extractors.items()}
        window = self.effective_chunk_rows()
        wide = [n for n, e in self.extractors.items() if e.needs_window > window]
        if wide:                                           # refuse the combination instead of emitting constants
            raise DataContractError(f"{self.name}: window of {window} row(s) but {wide} need more; "
                                    "switch mode or make them row-local")

    def effective_chunk_rows(self) -> int:
        return 1 if self.mode == 'cross_sectional' else int(self.chunk_rows)

    def missing_required(self, df: pd.DataFrame) -> List[str]:
        return [c for c in self.required_columns if c not in df.columns]

    def missing_signals(self, df: pd.DataFrame) -> List[str]:
        return [c for c in self.primary_signals if c not in df.columns]

    def __getitem__(self, key: str):              # backwards-compatible dict-style access
        return getattr(self, key)


class DomainRegistry:
    """Registry: by_name() is the entry point; a new domain is register(DomainProfile(...))."""
    _REGISTRY: Dict[str, DomainProfile] = {}

    @classmethod
    def register(cls, profile: DomainProfile, replace_existing: bool = False) -> DomainProfile:
        key = profile.name.lower()
        if key in cls._REGISTRY and not replace_existing:
            raise DataContractError(f"profile '{key}' already registered")
        cls._REGISTRY[key] = profile
        return profile

    @classmethod
    def by_name(cls, name: str) -> DomainProfile:
        try:
            return cls._REGISTRY[name.lower()]
        except KeyError:
            raise DataContractError(f"Unknown sector profile: {name}; registered: {cls.names()}") from None

    @classmethod
    def names(cls) -> List[str]:
        return sorted(cls._REGISTRY)

    @staticmethod
    def hr(): return DomainRegistry.by_name('hr')
    @staticmethod
    def fintech(): return DomainRegistry.by_name('fintech')
    @staticmethod
    def supply_chain(): return DomainRegistry.by_name('supply_chain')


SectorProfiles = DomainRegistry      # backwards-compatible alias


SectorProfiles.register(DomainProfile(
    'hr', 'People analytics, retention, engagement.', required_columns=('performance_score',),
    primary_signals=('performance_score', 'promotion_history', 'survey_text'),
    extractors={'perf_volatility': Extractor('perf_volatility', hr_perf_volatility, ('performance_score',), needs_window=2),
                'negative_text_share': Extractor('negative_text_share', hr_negative_text_share, ('survey_text',))},
    mode='series', notes='Each vector summarises a window of consecutive records.'))
SectorProfiles.register(DomainProfile(
    'fintech', 'Fraud, AML, credit risk, compliance.', required_columns=('transaction_velocity',),
    primary_signals=('transaction_velocity', 'ip_geolocation', 'device_risk', 'session_anomaly'),
    informative_absence=('device_risk',),     # an unknown device is not an average device
    extractors={'velocity_p90': Extractor('velocity_p90', fin_velocity_p90, ('transaction_velocity',)),
                'risk_interaction': Extractor('risk_interaction', fin_risk_interaction, ('device_risk', 'session_anomaly')),
                'suspicious_share': Extractor('suspicious_share', fin_suspicious_share, ('survey_text',))},
    mode='cross_sectional', notes='Each row (session/transaction) is its own decision.'))
SectorProfiles.register(DomainProfile(
    'supply_chain', 'ETA prediction, disruption detection.', required_columns=('route_delay',),
    primary_signals=('delivery_time', 'route_delay', 'weather', 'supplier_risk'),
    extractors={'delay_p90': Extractor('delay_p90', sc_delay_p90, ('route_delay',)),
                'delivery_cv': Extractor('delivery_cv', sc_delivery_cv, ('delivery_time',), needs_window=2),
                'delay_slope': Extractor('delay_slope', sc_delay_slope, ('route_delay',), needs_window=3),
                'exposure': Extractor('exposure', sc_exposure, ('supplier_risk', 'weather'))},
    mode='series', notes='Each vector summarises a window of consecutive days.'))


class ExplainabilityHub:
    def __init__(self, engine: UnifiedAnalyticsEngine): self.engine = engine
    def lime(self, df: pd.DataFrame): return self.engine.explain(df)
    def shap_ready(self):
        tree = [n for n in self.engine.models if n in ('rf', 'xgb', 'lgbm', 'gb')]
        return {'tree_models_fitted': tree, 'implemented': False,
                'status': 'not_implemented (only LIME is wired; tree models are SHAP-compatible)'}


class PersistenceManager:
    def __init__(self, model_dir: str): self.model_dir = model_dir

    def artifact_paths(self):
        return {k: os.path.join(self.model_dir, f'{k}.joblib') for k in ('scaler', 'imputer', 'meta')}

    def save_json(self, obj: Dict[str, Any], filename: str):
        path = os.path.join(self.model_dir, filename)
        with open(path, 'w') as f:
            json.dump(obj, f, indent=2, default=str)
        return path


class PerformanceMonitor:
    def __init__(self): self.records: List[Dict[str, Any]] = []
    def log(self, metric: str, value: Any): self.records.append({'metric': metric, 'value': value})
    def summary(self): return pd.DataFrame(self.records)


class UnifiedAnalyticsDemo:
    """Synthetic frames.  labeled=True also returns a target with real structure to learn."""

    @staticmethod
    def build_hr_demo(n: int = 100, seed: int = 0, labeled: bool = False):
        r = np.random.default_rng(seed)
        df = pd.DataFrame({
            'performance_score': r.random(n),
            'survey_text': r.choice(['great place', 'fine', 'stressed', 'engaged', 'want to leave'], size=n),
            'date': pd.date_range('2025-01-01', periods=n, freq='D')})
        return (df, (df['performance_score'] < df['performance_score'].median()).astype(int)) if labeled else df

    @staticmethod
    def build_fintech_demo(n: int = 100, seed: int = 0, labeled: bool = False, label_noise: float = 0.15):
        r = np.random.default_rng(seed)
        df = pd.DataFrame({
            'transaction_velocity': r.random(n), 'ip_geolocation': r.random(n),
            'device_risk': r.random(n), 'session_anomaly': r.random(n),
            'survey_text': r.choice(['ok', 'suspicious', 'normal'], size=n)})
        if not labeled:
            return df
        score = df['transaction_velocity'] + df['device_risk'] + df['session_anomaly'] + 0.3 * (df['survey_text'] == 'suspicious')
        flip = r.random(n) < label_noise                # irreducible label noise: accuracy cannot reach 1.0
        return df, pd.Series(((score > 1.7).to_numpy() ^ flip).astype(int), index=df.index)

    @staticmethod
    def build_supply_chain_demo(n: int = 100, seed: int = 0, labeled: bool = False, label_noise: float = 0.15):
        r = np.random.default_rng(seed)
        block = np.arange(n) // 10                      # disruption regimes last ~10 days
        regime = (r.random(block.max() + 1) > 0.5).astype(float)[block]
        df = pd.DataFrame({
            'delivery_time': r.random(n) * 10 + 3 * regime, 'route_delay': r.random(n) * 0.5 + 0.25 * regime,
            'weather': r.random(n), 'supplier_risk': r.random(n) * 0.6 + 0.4 * regime,
            'date': pd.date_range('2025-01-01', periods=n, freq='D')})
        if not labeled:
            return df
        flip = (r.random(block.max() + 1) < label_noise)[block]   # a whole regime is mislabeled
        return df, pd.Series((regime.astype(bool) ^ flip).astype(int), index=df.index)


class SystemBlueprint:
    version = '1.0'
    components = ['EngineConfig', 'UnifiedAnalyticsEngine', 'UnifiedAnalyticsOrchestrator',
                  'ExplainabilityHub', 'PersistenceManager', 'PerformanceMonitor']
    planned_sectors = ['Retail', 'Healthcare', 'Manufacturing']      # NOT registered: by_name() raises for these

    @classmethod
    def registered_sectors(cls) -> List[str]:
        return DomainRegistry.names()


# =============================================================================
# Quantum layer (exact statevector math; qubit 0 is the leftmost tensor factor)
# =============================================================================

class QuantumContractError(Exception):
    pass


@dataclass
class QuantumConfig:
    dimension: int = 2
    precision: float = 1e-9
    max_qubits: int = 32
    backend: str = 'math'
    normalize: bool = True
    allow_complex: bool = True


PAULI = {
    'I': np.eye(2, dtype=complex),
    'X': np.array([[0, 1], [1, 0]], dtype=complex),
    'Y': np.array([[0, -1j], [1j, 0]], dtype=complex),
    'Z': np.array([[1, 0], [0, -1]], dtype=complex),
}


def _apply_local(amps: np.ndarray, matrix: np.ndarray, targets: List[int], n: int) -> np.ndarray:
    """Apply a k-qubit gate to chosen qubits of an n-qubit statevector."""
    k = len(targets)
    psi = amps.reshape([2] * n)
    gate = matrix.reshape([2] * (2 * k))
    out = np.tensordot(gate, psi, axes=(list(range(k, 2 * k)), targets))
    out = np.moveaxis(out, list(range(k)), targets)
    return out.reshape(-1)


class QuantumState:
    """A normalized vector in a finite-dimensional complex Hilbert space.

    This is the mathematical object |psi> in C^d.  `probabilities()` computes the
    exact Born distribution p_i = |<i|psi>|^2.  `density_matrix()` returns |psi><psi|.
    """

    def __init__(self, amplitudes: np.ndarray, labels: Optional[List[str]] = None):
        self.amplitudes = np.asarray(amplitudes, dtype=complex)
        self.labels = labels or [f'|{i}>' for i in range(len(self.amplitudes))]
        self.normalize()

    def normalize(self):
        norm = np.linalg.norm(self.amplitudes)
        if norm == 0:
            raise QuantumContractError('Zero-norm quantum state')
        self.amplitudes = self.amplitudes / norm
        return self

    def probabilities(self):
        """Exact Born probabilities: p_i = |<i|psi>|^2."""
        return np.abs(self.amplitudes) ** 2

    def density_matrix(self):
        """Outer product |psi><psi| — the rank-1 projector onto this state."""
        a = self.amplitudes.reshape(-1, 1)
        return a @ np.conjugate(a.T)


class QuantumOperator:
    def __init__(self, matrix: np.ndarray, name: str = 'U'):
        self.matrix = np.asarray(matrix, dtype=complex)
        self.name = name
        self._validate_square()

    def _validate_square(self):
        if self.matrix.ndim != 2 or self.matrix.shape[0] != self.matrix.shape[1]:
            raise QuantumContractError('Operator must be square')

    def apply(self, state: QuantumState) -> QuantumState:
        if self.matrix.shape[1] != state.amplitudes.shape[0]:
            raise QuantumContractError('Operator/state dimension mismatch')
        return QuantumState(self.matrix @ state.amplitudes, labels=state.labels)

    def dagger(self):
        return QuantumOperator(np.conjugate(self.matrix.T), name=f'{self.name}†')


class QuantumMath:
    @staticmethod
    def ket0(dim: int = 2):
        v = np.zeros(dim, dtype=complex); v[0] = 1.0; return QuantumState(v)

    @staticmethod
    def ket1(dim: int = 2):
        v = np.zeros(dim, dtype=complex); v[min(1, dim - 1)] = 1.0; return QuantumState(v)

    @staticmethod
    def superposition(weights: np.ndarray):
        return QuantumState(np.asarray(weights, dtype=complex))

    @staticmethod
    def pauli_x(): return QuantumOperator(PAULI['X'], 'X')
    @staticmethod
    def pauli_y(): return QuantumOperator(PAULI['Y'], 'Y')
    @staticmethod
    def pauli_z(): return QuantumOperator(PAULI['Z'], 'Z')

    @staticmethod
    def hadamard():
        return QuantumOperator((1 / np.sqrt(2)) * np.array([[1, 1], [1, -1]], dtype=complex), 'H')

    @staticmethod
    def tensor(a: QuantumState, b: QuantumState) -> QuantumState:
        return QuantumState(np.kron(a.amplitudes, b.amplitudes), labels=(a.labels + b.labels))

    @staticmethod
    def kron_op(a: QuantumOperator, b: QuantumOperator) -> QuantumOperator:
        return QuantumOperator(np.kron(a.matrix, b.matrix), name=f'{a.name}⊗{b.name}')

    @staticmethod
    def expectation(state: QuantumState, operator: QuantumOperator):
        return float(np.real(np.conjugate(state.amplitudes) @ (operator.matrix @ state.amplitudes)))

    @staticmethod
    def fidelity(a: QuantumState, b: QuantumState):
        return float(np.abs(np.conjugate(a.amplitudes) @ b.amplitudes) ** 2)


class QuantumMathEngine:
    """Layer 1 runtime:  execute quantum-mathematical operations (gate application,
    measurement, analysis) on the Hilbert-space algebra.  The 'math' backend IS
    evaluation of functions on Hilbert space — no hardware abstraction."""
    def __init__(self, config: Optional[Any] = None):
        self.config = QuantumConfig(**config) if isinstance(config, dict) else (config or QuantumConfig())
        self.registry: Dict[str, Callable] = {}
        self.audit: List[Dict[str, Any]] = []
        self.backend = self.config.backend

    def register_operation(self, name: str, fn: Callable):
        self.registry[name] = fn
        self.audit.append({'event': 'register_operation', 'name': name})

    def state(self, amplitudes, labels=None):
        s = QuantumState(np.asarray(amplitudes, dtype=complex), labels=labels)
        self.audit.append({'event': 'state_create', 'dim': len(s.amplitudes)})
        return s

    def operator(self, matrix, name='U'):
        o = QuantumOperator(matrix, name=name)
        self.audit.append({'event': 'operator_create', 'name': name, 'shape': o.matrix.shape})
        return o

    def evolve(self, state: QuantumState, operator: QuantumOperator):
        out = operator.apply(state)
        self.audit.append({'event': 'evolve', 'operator': operator.name})
        return out

    def measure(self, state: QuantumState):
        probs = state.probabilities()
        idx = int(np.argmax(probs))  # most-probable outcome under the exact Born distribution
        self.audit.append({'event': 'measure', 'index': idx, 'probability': float(probs[idx])})
        return {'index': idx, 'probabilities': probs.tolist()}

    def compose(self, *operators: QuantumOperator):
        if not operators:
            raise QuantumContractError('No operators to compose')
        m = operators[0].matrix
        for op in operators[1:]:
            m = op.matrix @ m
        return QuantumOperator(m, name='∘'.join(op.name for op in operators))

    def circuit_from_principles(self, intent: Dict[str, Any]):
        if intent.get('basis', 'computational') == 'computational':
            return [self.operator(QuantumMath.hadamard().matrix, 'H'),
                    self.operator(QuantumMath.pauli_z().matrix, 'Z')]
        return [self.operator(np.eye(self.config.dimension, dtype=complex), 'I')]

    def first_principles_report(self, state: QuantumState):
        return {'dimension': int(state.amplitudes.shape[0]),
                'norm': float(np.linalg.norm(state.amplitudes)),
                'probabilities': state.probabilities().tolist(),
                'density_matrix': state.density_matrix().tolist()}


class QuantumAgnosticAdapter:
    def __init__(self, engine: QuantumMathEngine): self.engine = engine
    def compile_intent(self, intent): return self.engine.circuit_from_principles(intent)

    def run(self, intent: Dict[str, Any], state: QuantumState):
        for op in self.compile_intent(intent):
            state = op.apply(state)
        return self.engine.measure(state)


class QuantumDemo:
    @staticmethod
    def entangled_like_state():
        return QuantumMath.superposition(np.array([1, 0, 0, 1], dtype=complex))

    @staticmethod
    def bell_like_operator():
        hi = np.kron(QuantumMath.hadamard().matrix, np.eye(2))
        cnot = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]], dtype=complex)
        return QuantumOperator(cnot @ hi, 'BellPrep')   # (H⊗I) first, then CNOT


class QuantumRegister:
    """A state in a tensor-product Hilbert space H = (C^2)^{otimes n}, evolved by operator application.

    This is a mathematical object — a vector in a 2^n-dimensional complex vector space — not a
    simulation of a physical device.  `apply` composes unitary operators on the state; `measure`
    returns the exact Born probabilities |<i|psi>|^2.
    """

    def __init__(self, qubits: int):
        if qubits < 1:
            raise QuantumContractError('Register must contain at least one qubit')
        self.qubits = qubits
        self.dim = 2 ** qubits
        self.state = QuantumMath.ket0(self.dim)
        self.depth = 0
        self.operations: List[str] = []

    def reset(self):
        self.state = QuantumMath.ket0(self.dim)
        self.depth = 0
        self.operations.clear()
        return self

    def apply(self, operator: QuantumOperator, label: Optional[str] = None,
              targets: Optional[Sequence[int]] = None):
        """Operator composition on Hilbert space: |psi'> = U|psi>.
        Full-width operators multiply directly; smaller gates act on `targets`."""
        d = operator.matrix.shape[0]
        k = int(round(np.log2(d)))
        if 2 ** k != d or k > self.qubits:
            raise QuantumContractError(f'Operator dim {d} incompatible with {self.qubits}-qubit register')
        tg = list(targets) if targets else list(range(k))
        if len(tg) != k or len(set(tg)) != k or any(q < 0 or q >= self.qubits for q in tg):
            raise QuantumContractError(f'Invalid targets {tg} for a {k}-qubit gate')
        if k == self.qubits and tg == list(range(k)):          # canonical full-width order
            self.state = operator.apply(self.state)
        else:                                                  # honors targets, incl. permuted full-width
            self.state = QuantumState(_apply_local(self.state.amplitudes, operator.matrix, tg, self.qubits),
                                      labels=self.state.labels)
        self.depth += 1
        self.operations.append(label or operator.name)
        return self

    def measure(self):
        """Exact Born probabilities: p_i = |<i|psi>|^2.  Returns the most probable outcome and the full distribution."""
        p = self.state.probabilities()
        idx = int(np.argmax(p))
        return {'index': idx, 'probabilities': p.tolist(), 'depth': self.depth, 'ops': self.operations[:]}


class QuantumMathPrimitives:
    @staticmethod
    def identity(n: int): return QuantumOperator(np.eye(n, dtype=complex), 'I')

    @staticmethod
    def phase(theta: float):
        return QuantumOperator(np.array([[1, 0], [0, np.exp(1j * theta)]], dtype=complex), f'P({theta})')

    @staticmethod
    def rx(theta: float):
        c, s = np.cos(theta / 2), -1j * np.sin(theta / 2)
        return QuantumOperator(np.array([[c, s], [s, c]], dtype=complex), f'Rx({theta})')

    @staticmethod
    def ry(theta: float):
        c, s = np.cos(theta / 2), np.sin(theta / 2)
        return QuantumOperator(np.array([[c, -s], [s, c]], dtype=complex), f'Ry({theta})')

    @staticmethod
    def rz(theta: float):
        return QuantumOperator(np.array([[np.exp(-1j * theta / 2), 0], [0, np.exp(1j * theta / 2)]],
                                        dtype=complex), f'Rz({theta})')

    @staticmethod
    def cnot():
        return QuantumOperator(np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]],
                                        dtype=complex), 'CNOT')

    @staticmethod
    def swap():
        return QuantumOperator(np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]],
                                        dtype=complex), 'SWAP')


class QuantumPrinciplesEngine:
    def __init__(self, max_qubits: int = 32):
        self.max_qubits = max_qubits
        self.registry: Dict[str, Callable] = {}
        self.evaluations: List[Dict[str, Any]] = []

    def register(self, name: str, fn: Callable):
        self.registry[name] = fn

    def register_default_primitives(self):
        self.register('H', QuantumMath.hadamard)
        self.register('X', QuantumMath.pauli_x)
        self.register('Z', QuantumMath.pauli_z)
        self.register('CNOT', QuantumMathPrimitives.cnot)
        self.register('SWAP', QuantumMathPrimitives.swap)
        self.register('RX', QuantumMathPrimitives.rx)
        self.register('RY', QuantumMathPrimitives.ry)
        self.register('RZ', QuantumMathPrimitives.rz)
        return self

    def validate_register(self, reg: QuantumRegister):
        if reg.qubits > self.max_qubits:
            raise QuantumContractError('Register exceeds engine qubit limit')
        return True

    def parallel_depth(self, layers: List[List[QuantumOperator]]):
        return sum(1 for layer in layers if layer)

    def apply_layers(self, reg: QuantumRegister, layers: List[List[QuantumOperator]]):
        self.validate_register(reg)
        for layer in layers:
            if not layer:
                continue
            op = layer[0]
            for extra in layer[1:]:
                op = QuantumMath.kron_op(op, extra)
            reg.apply(op, label=f'layer:{op.name}')
        return reg

    def evaluate(self, reg: QuantumRegister):
        self.validate_register(reg)
        result = reg.measure()
        self.evaluations.append({'qubits': reg.qubits, 'depth': result['depth'], 'result': result['index']})
        return result

    def first_principles_summary(self, reg: QuantumRegister):
        p = reg.state.probabilities()
        nz = p[p > 0]
        return {'qubits': reg.qubits, 'dimension': reg.dim, 'depth': reg.depth,
                'norm': float(np.linalg.norm(reg.state.amplitudes)),
                'entropy_proxy': float(-np.sum(nz * np.log2(nz)))}


class QuantumPipeline:
    def __init__(self, engine: QuantumPrinciplesEngine):
        self.engine = engine
        self.steps: List[Dict[str, Any]] = []

    def add_step(self, label: str, op_factory: Callable, *args, **kwargs):
        self.steps.append({'label': label, 'factory': op_factory, 'args': args, 'kwargs': kwargs})
        return self

    def build(self):
        return [s['factory'](*s['args'], **s['kwargs']) for s in self.steps]

    def run(self, qubits: int):
        reg = QuantumRegister(qubits)
        for op in self.build():
            reg.apply(op)
        return self.engine.evaluate(reg)


class QuantumMathReport:
    """Reports on exact quantum mathematical quantities — no simulation, no noise channels."""
    pass


class QuantumFirstPrinciplesDemo:
    @staticmethod
    def bell_state_pipeline():
        eng = QuantumPrinciplesEngine().register_default_primitives()
        pipe = QuantumPipeline(eng)
        pipe.add_step('hadamard', QuantumMath.hadamard)
        pipe.add_step('cnot', QuantumMathPrimitives.cnot)
        return pipe


# ---------------------------
# Multi-qubit algebra and backend-neutral IR
# ---------------------------

class QuantumIR:
    def __init__(self, name: str = 'QuantumIR'):
        self.name = name
        self.instructions: List[Dict[str, Any]] = []

    def add(self, op: str, targets: List[int], params: Optional[Dict[str, Any]] = None):
        self.instructions.append({'op': op, 'targets': targets, 'params': params or {}})
        return self

    def serialize(self):
        return {'name': self.name, 'instructions': self.instructions}

    @staticmethod
    def deserialize(blob: Dict[str, Any]):
        q = QuantumIR(blob.get('name', 'QuantumIR'))
        q.instructions = list(blob.get('instructions', []))
        return q


class PartialTrace:
    @staticmethod
    def trace_out(state: QuantumState, keep=1) -> np.ndarray:
        """Reduced density matrix. `keep` = int (first k qubits) or list of qubit indices."""
        n = int(round(np.log2(len(state.amplitudes))))
        keep_l = list(range(keep)) if isinstance(keep, int) else sorted(keep)
        if any(q < 0 or q >= n for q in keep_l):
            raise QuantumContractError('keep index out of range')
        rho = state.density_matrix().reshape([2] * (2 * n))
        cur = n
        for q in sorted((q for q in range(n) if q not in keep_l), reverse=True):
            rho = np.trace(rho, axis1=q, axis2=q + cur)
            cur -= 1
        d = 2 ** len(keep_l)
        return rho.reshape(d, d)


def _entropy_bits(rho: np.ndarray) -> float:
    ev = np.linalg.eigvalsh((rho + rho.conj().T) / 2)
    ev = ev[ev > 1e-12]
    return float(max(0.0, -np.sum(ev * np.log2(ev))))


class MultiQubitMath:
    @staticmethod
    def basis(n: int, index: int):
        v = np.zeros(2 ** n, dtype=complex); v[index] = 1.0
        return QuantumState(v)

    @staticmethod
    def bell_pair():
        return QuantumState(np.array([1, 0, 0, 1], dtype=complex) / np.sqrt(2), labels=['00', '01', '10', '11'])

    @staticmethod
    def ghz(n: int):
        if n < 2:
            raise QuantumContractError('GHZ requires at least 2 qubits')
        v = np.zeros(2 ** n, dtype=complex); v[0] = v[-1] = 1 / np.sqrt(2)
        return QuantumState(v)

    @staticmethod
    def w_state(n: int):
        if n < 2:
            raise QuantumContractError('W-state requires at least 2 qubits')
        v = np.zeros(2 ** n, dtype=complex)
        for i in range(n):
            v[1 << i] = 1 / np.sqrt(n)
        return QuantumState(v)

    @staticmethod
    def entanglement_entropy(state: QuantumState, subsystem_size: int = 1):
        """True bipartite entanglement entropy (bits): S of the reduced state of the first k qubits."""
        return _entropy_bits(PartialTrace.trace_out(state, subsystem_size))

    @staticmethod
    def concurrence_like(state: QuantumState):
        if len(state.amplitudes) < 4:
            return 0.0
        return float(2 * np.abs(state.amplitudes[0] * state.amplitudes[-1]))


class QuantumStateFactory:
    @staticmethod
    def from_bits(bits: str):
        return MultiQubitMath.basis(len(bits), int(bits, 2))

    @staticmethod
    def from_ir(ir: QuantumIR, qubits: int):
        reg = QuantumRegister(qubits)
        fixed = {'H': QuantumMath.hadamard, 'X': QuantumMath.pauli_x, 'Y': QuantumMath.pauli_y,
                 'Z': QuantumMath.pauli_z, 'CNOT': QuantumMathPrimitives.cnot,
                 'SWAP': QuantumMathPrimitives.swap}
        rot = {'RX': QuantumMathPrimitives.rx, 'RY': QuantumMathPrimitives.ry,
               'RZ': QuantumMathPrimitives.rz, 'PHASE': QuantumMathPrimitives.phase}
        for instr in ir.instructions:
            op = instr['op'].upper()
            params, targets = instr.get('params', {}), instr.get('targets') or None
            if op == 'I':
                continue
            if op in fixed:
                reg.apply(fixed[op](), targets=targets)
            elif op in rot:
                reg.apply(rot[op](params.get('theta', 0.0)), targets=targets)
            else:
                raise QuantumContractError(f'Unsupported IR op: {op}')
        return reg


SUPPORTED_GATES = {'H', 'X', 'Y', 'Z', 'RX', 'RY', 'RZ', 'PHASE', 'CNOT', 'SWAP', 'I'}


class QuantumBackendNeutralCompiler:
    def __init__(self): self.supported = set(SUPPORTED_GATES)

    def compile(self, circuit: List[Dict[str, Any]]):
        ir = QuantumIR()
        for inst in circuit:
            op = inst.get('op', '').upper()
            if op not in self.supported:
                raise QuantumContractError(f'Unsupported gate: {op}')
            ir.add(op, inst.get('targets', []), inst.get('params', {}))
        return ir


class QuantumAnalyzer:
    @staticmethod
    def bloch_vector(state: QuantumState):
        if len(state.amplitudes) != 2:
            raise QuantumContractError('Bloch vector defined for 1-qubit states only')
        a, b = state.amplitudes
        return {'x': float(2 * np.real(np.conjugate(a) * b)),
                'y': float(2 * np.imag(np.conjugate(a) * b)),
                'z': float(np.abs(a) ** 2 - np.abs(b) ** 2)}

    @staticmethod
    def purity(state: QuantumState):
        rho = state.density_matrix()
        return float(np.real(np.trace(rho @ rho)))

    @staticmethod
    def von_neumann_entropy(state: QuantumState):
        """S(rho) of the state itself: 0 for any pure state."""
        return _entropy_bits(state.density_matrix())

    @staticmethod
    def shannon_entropy(state: QuantumState):
        """Entropy of the computational-basis measurement distribution."""
        p = state.probabilities(); p = p[p > 0]
        return float(-np.sum(p * np.log2(p)))

    @staticmethod
    def top_amplitudes(state: QuantumState, k: int = 5):
        p = state.probabilities()
        return [{'basis_index': int(i), 'probability': float(p[i])} for i in np.argsort(-p)[:k]]


class QuantumWorkflow:
    def __init__(self): self.steps: List[Dict[str, Any]] = []

    def add_gate(self, op: str, targets: List[int], params: Optional[Dict[str, Any]] = None):
        self.steps.append({'op': op, 'targets': targets, 'params': params or {}})
        return self

    def to_ir(self): return QuantumBackendNeutralCompiler().compile(self.steps)

    def execute(self, qubits: int):
        """Evaluate the circuit: sequential operator composition on Hilbert space, then exact Born probabilities."""
        reg = QuantumStateFactory.from_ir(self.to_ir(), qubits)
        return reg.measure()


class QuantumDocumentation:
    @staticmethod
    def principles():
        return {'state': 'A normalized complex vector in Hilbert space.',
                'operator': 'A linear, square transformation on state space.',
                'composition': 'Operators compose by matrix multiplication and tensor product.',
                'measurement': 'Born rule: probabilities are the squared magnitudes of amplitudes.',
                'spectral': 'Self-adjoint operators have real eigenvalues; the spectrum is the set of observable values.'}


class QuantumMetrics:
    @staticmethod
    def summary(state: QuantumState):
        return {'norm': float(np.linalg.norm(state.amplitudes)),
                'purity': QuantumAnalyzer.purity(state),
                'measurement_entropy': QuantumAnalyzer.shannon_entropy(state),
                'top': QuantumAnalyzer.top_amplitudes(state)}


# ---------------------------
# Hamiltonian evolution and symbolic optimization
# ---------------------------

class HamiltonianTerm:
    def __init__(self, coefficient: complex, operator: str, qubits: List[int]):
        self.coefficient = complex(coefficient)
        self.operator = operator.upper()
        self.qubits = list(qubits)


class Hamiltonian:
    """Sum of Pauli strings. A term (c, 'Z', [i, j]) means c * Z_i Z_j."""

    def __init__(self, num_qubits: int, terms: Optional[List[HamiltonianTerm]] = None):
        if num_qubits < 1:
            raise QuantumContractError('Hamiltonian requires at least one qubit')
        self.num_qubits = num_qubits
        self.terms = list(terms or [])
        self._cache: Optional[np.ndarray] = None

    def add_term(self, coefficient: complex, operator: str, qubits: List[int]):
        op = operator.upper()
        if op not in PAULI:
            raise QuantumContractError(f'Unsupported Pauli op: {operator}')
        if any(q < 0 or q >= self.num_qubits for q in qubits):
            raise QuantumContractError(f'Qubit index out of range in term on {qubits}')
        if len(set(qubits)) != len(qubits):
            raise QuantumContractError('Duplicate qubits in a single term')
        self.terms.append(HamiltonianTerm(coefficient, op, qubits))
        self._cache = None
        return self

    def matrix(self) -> np.ndarray:
        if self._cache is not None:
            return self._cache
        dim = 2 ** self.num_qubits
        H = np.zeros((dim, dim), dtype=complex)
        for t in self.terms:
            ops = [PAULI['I']] * self.num_qubits
            for q in t.qubits:
                ops[q] = PAULI[t.operator]
            full = ops[0]
            for m in ops[1:]:
                full = np.kron(full, m)
            H += t.coefficient * full
        if not np.allclose(H, H.conj().T):
            raise QuantumContractError('Hamiltonian is not hermitian')
        self._cache = H
        return H

    def expectation(self, state: QuantumState) -> float:
        return float(np.real(np.conjugate(state.amplitudes) @ (self.matrix() @ state.amplitudes)))

    def ground_energy(self) -> float:
        return float(np.linalg.eigvalsh(self.matrix())[0])


class TimeEvolution:
    @staticmethod
    def evolve(state: QuantumState, hamiltonian: Hamiltonian, time: float):
        """Evaluate exp(-iHt)|psi> by floating-point spectral decomposition.

        For self-adjoint H the mathematical evolution is unitary; NumPy's
        eigensolver, phase evaluation and matrix products incur rounding error.
        """
        w, V = np.linalg.eigh(hamiltonian.matrix())
        U = (V * np.exp(-1j * w * time)) @ V.conj().T
        return QuantumState(U @ state.amplitudes, labels=state.labels)


class SymbolicExpression:
    """Mod-2 (GF(2)) term algebra: a term present an even number of times cancels.
    Used by the optimizer to track Pauli frames: X@q / Z@q parity per qubit."""

    def __init__(self, terms: Optional[Sequence[str]] = None):
        self._terms: set = set()
        for t in terms or []:
            self.toggle(t)

    @property
    def terms(self) -> List[str]:
        return sorted(self._terms)

    def toggle(self, term: str) -> 'SymbolicExpression':
        self._terms ^= {term}
        return self

    add = toggle

    def simplify(self) -> 'SymbolicExpression':
        return SymbolicExpression(self.terms)       # already canonical; kept for API compatibility

    def __xor__(self, other: 'SymbolicExpression') -> 'SymbolicExpression':
        out = SymbolicExpression()
        out._terms = self._terms ^ other._terms
        return out

    def __contains__(self, term: str) -> bool: return term in self._terms
    def __len__(self) -> int: return len(self._terms)
    def __bool__(self) -> bool: return bool(self._terms)
    def __eq__(self, other) -> bool: return isinstance(other, SymbolicExpression) and self._terms == other._terms
    def __repr__(self) -> str: return f'SymbolicExpression({self.terms})'


class GateIdentityRules:
    """Rule table the optimizer consults.  Everything here is an exact identity (no global-phase drift)."""
    SELF_INVERSE = ('H', 'X', 'Y', 'Z', 'SWAP', 'CNOT')
    # rotation period at which the gate is EXACTLY the identity: R(2pi) = -I, so 4pi; PHASE is 2pi
    ROTATION_PERIOD = {'RX': 4 * np.pi, 'RY': 4 * np.pi, 'RZ': 4 * np.pi, 'PHASE': 2 * np.pi}

    @classmethod
    def reduce_pair(cls, a: str, b: str):
        return 'I' if a == b and a in cls.SELF_INVERSE else None

    @classmethod
    def combine(cls, a: Dict[str, Any], b: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Fuse `a` then `b` (same targets). Returns replacement instructions ([] = identity) or None."""
        if a.get('targets') != b.get('targets'):
            return None
        if cls.reduce_pair(a['op'], b['op']) == 'I':
            return []
        op = a['op']
        if op == b['op'] and op in cls.ROTATION_PERIOD:
            theta = float(a.get('params', {}).get('theta', 0.0)) + float(b.get('params', {}).get('theta', 0.0))
            period = cls.ROTATION_PERIOD[op]
            if abs(((theta + period / 2) % period) - period / 2) < 1e-12:
                return []
            return [{'op': op, 'targets': list(a['targets']), 'params': {'theta': theta}}]
        return None


class SymbolicReducer:
    """Commutation-aware peephole reduction.  A gate may slide back past any gate with disjoint
    targets (they commute exactly), then fuses with the first gate it shares a qubit with."""

    def reduce(self, instructions: List[Dict[str, Any]]):
        out: List[Dict[str, Any]] = []
        for inst in instructions:
            tg = set(inst.get('targets', []))
            merged = False
            for j in range(len(out) - 1, -1, -1):
                if set(out[j].get('targets', [])).isdisjoint(tg):
                    continue
                comb = GateIdentityRules.combine(out[j], inst)
                if comb is not None:
                    out[j:j + 1] = comb
                    merged = True
                break
            if not merged:
                out.append(inst)
        return out


class SymbolicGateOptimizer:
    PAULIS = ('X', 'Y', 'Z')

    def __init__(self):
        self.reducer = SymbolicReducer()

    def pauli_frames(self, instructions: List[Dict[str, Any]]):
        """Collapse each run of Pauli gates on a qubit to its net Pauli (X-part and Z-part parity, tracked
        with SymbolicExpression).  Equivalent up to a global phase, which is unobservable."""
        pending: Dict[int, SymbolicExpression] = {}
        out: List[Dict[str, Any]] = []

        def flush(q: int):
            expr = pending.pop(q, None)
            if not expr:
                return
            x, z = f'X@{q}' in expr, f'Z@{q}' in expr
            out.append({'op': 'Y' if (x and z) else 'X' if x else 'Z', 'targets': [q], 'params': {}})

        for inst in instructions:
            tg = inst.get('targets', [])
            if inst['op'] in self.PAULIS and len(tg) == 1:
                q = tg[0]
                e = pending.setdefault(q, SymbolicExpression())
                if inst['op'] in ('X', 'Y'):
                    e.toggle(f'X@{q}')
                if inst['op'] in ('Z', 'Y'):
                    e.toggle(f'Z@{q}')
            else:
                for q in tg:
                    flush(q)
                out.append(inst)
        for q in sorted(pending):
            flush(q)
        return out

    def optimize(self, ir: QuantumIR):
        instrs = list(ir.instructions)
        while True:                                   # iterate to a fixed point
            new = self.pauli_frames(self.reducer.reduce(instrs))
            if new == instrs:
                break
            instrs = new
        out = QuantumIR(ir.name + '_optimized')
        out.instructions = instrs
        return out


class CircuitSerializer:
    @staticmethod
    def to_json(ir: QuantumIR): return json.dumps(ir.serialize(), indent=2)
    @staticmethod
    def from_json(blob: str): return QuantumIR.deserialize(json.loads(blob))


class MeasurementPostulates:
    @staticmethod
    def projective_measure(state: QuantumState, seed: Optional[int] = None):
        """Sample an outcome by the Born rule, then collapse."""
        probs = state.probabilities()
        idx = int(np.random.default_rng(seed).choice(len(probs), p=probs / probs.sum()))
        basis = np.zeros_like(state.amplitudes); basis[idx] = 1.0
        return {'outcome': idx, 'collapsed_state': QuantumState(basis, labels=state.labels),
                'probabilities': probs.tolist()}

    @staticmethod
    def born_rule(state: QuantumState): return state.probabilities().tolist()


class EntanglementToolkit:
    @staticmethod
    def reduced_density_matrix(state: QuantumState, keep: int = 1):
        return PartialTrace.trace_out(state, keep)

    @staticmethod
    def entanglement_proxy(state: QuantumState):
        return float(1.0 - np.max(state.probabilities()))


# ---------------------------
# Symbolic algebra, scheduling, advanced entanglement, compilation
# ---------------------------

class GateScheduler:
    """ASAP layering that respects qubit dependencies."""
    def __init__(self): self.layers: List[List[Dict[str, Any]]] = []

    def add(self, gate: Dict[str, Any]):
        targets = set(gate.get('targets', []))
        last = -1
        for i, layer in enumerate(self.layers):
            if any(targets & set(g.get('targets', [])) for g in layer):
                last = i
        if last + 1 < len(self.layers):
            self.layers[last + 1].append(gate)
        else:
            self.layers.append([gate])
        return self

    def depth(self): return len([layer for layer in self.layers if layer])

    def compile_ir(self, ir: QuantumIR):
        self.layers = []
        for inst in ir.instructions:
            self.add(inst)
        return self

    def to_ir(self):
        ir = QuantumIR('scheduled')
        for layer in self.layers:
            ir.instructions.extend(layer)
        return ir


class AdvancedEntanglement:
    @staticmethod
    def schmidt_coefficients(state: QuantumState, subsystem_size: int = 1) -> np.ndarray:
        n = int(round(np.log2(len(state.amplitudes))))
        k = min(subsystem_size, n - 1) if n > 1 else 0
        if k < 1:
            return np.array([1.0])
        M = state.amplitudes.reshape(2 ** k, 2 ** (n - k))
        return np.linalg.svd(M, compute_uv=False)

    @staticmethod
    def schmidt_proxy(state: QuantumState):
        s = AdvancedEntanglement.schmidt_coefficients(state) ** 2
        return float(1 - np.max(s))

    @staticmethod
    def participation_ratio(state: QuantumState):
        d = np.sum(state.probabilities() ** 2)
        return float(1.0 / d) if d else 0.0

    @staticmethod
    def entanglement_profile(state: QuantumState):
        return {'proxy': EntanglementToolkit.entanglement_proxy(state),
                'schmidt_proxy': AdvancedEntanglement.schmidt_proxy(state),
                'entropy_bits': MultiQubitMath.entanglement_entropy(state),
                'participation_ratio': AdvancedEntanglement.participation_ratio(state),
                'concurrence_like': MultiQubitMath.concurrence_like(state)}


class BackendCompiler:
    def __init__(self, max_depth: int = 1000):
        self.max_depth = max_depth
        self.optimizer = SymbolicGateOptimizer()
        self.scheduler = GateScheduler()

    def compile(self, workflow: QuantumWorkflow):
        optimized = self.optimizer.optimize(workflow.to_ir())
        scheduled = self.scheduler.compile_ir(optimized)
        if scheduled.depth() > self.max_depth:
            raise QuantumContractError('Circuit depth exceeds backend limit')
        return scheduled.to_ir(), scheduled.depth()


class QuantumMathCompilerSuite:
    """Layer 1 algebraic compiler:  optimise an IR and evaluate it on Hilbert space.
    Pure mathematics — the operator algebra, not a hardware target."""

    def __init__(self):
        self.compiler = BackendCompiler()

    def compile_workflow(self, workflow: QuantumWorkflow): return self.compiler.compile(workflow)

    def execute(self, workflow: QuantumWorkflow, qubits: int):
        ir, depth = self.compile_workflow(workflow)
        reg = QuantumStateFactory.from_ir(ir, qubits)
        out = reg.measure()
        out['compiled_depth'] = depth
        return out


class QuantumMathValidation:
    @staticmethod
    def is_unitary(op: QuantumOperator, tol: float = 1e-9):
        eye = np.eye(op.matrix.shape[0], dtype=complex)
        return bool(np.allclose(op.matrix.conj().T @ op.matrix, eye, atol=tol))

    @staticmethod
    def is_normalized(state: QuantumState, tol: float = 1e-9):
        return bool(abs(np.linalg.norm(state.amplitudes) - 1.0) < tol)

    @staticmethod
    def validate_workflow(workflow: QuantumWorkflow):
        for inst in workflow.to_ir().instructions:
            if inst['op'] not in SUPPORTED_GATES:
                raise QuantumContractError(f"Invalid operation: {inst['op']}")
        return True


class QuantumMathToolkit:
    @staticmethod
    def report(state: QuantumState):
        return {'normalized': QuantumMathValidation.is_normalized(state),
                'metrics': QuantumMetrics.summary(state),
                'entanglement': AdvancedEntanglement.entanglement_profile(state)}

    @staticmethod
    def optimize_workflow(workflow: QuantumWorkflow):
        return SymbolicGateOptimizer().optimize(workflow.to_ir())



class GoldenIntegrityError(RuntimeError):
    """A golden-arithmetic certificate failed: the fold would not be exactly invertible."""


class GoldenArithmetic:
    """Layer 3:  the exact number-theoretic backbone.

    Q = [[1,1],[1,0]] ∈ SL(2,ℤ) (mod signs).  Everything here is an integer identity
    carrying its own certificate — the algebraic structure that makes the entire
    checkpoint and encoding system provably exact:

      * Cassini:  F(n+1)F(n−1) − F(n)² = (−1)^n  IS  det(Q^n).  A determinant of ±1
        is a unit modulo every m, so Q^n is invertible over ℤ/2^bits with an INTEGER
        inverse: the fold is lossless by arithmetic, not by checksum.
      * trace(Q^n) = L(n) (Lucas): second independent certificate on the same matrix.
        The Lucas traces connect to the closed geodesics of the modular surface
        (TheoremVerificationSuite.modular_geodesics_from_lucas).
      * Pisano period π(2^k) = 3·2^(k−1):  the order of Q in GL(2, ℤ/2^k ℤ).  Any
        step count reduces mod π before the matrix is built — the inverse stays
        computable for ANY steps.
      * Zeckendorf:  every n ≥ 0 is a unique sum of non-adjacent Fibonacci numbers.
        This IS the bijection on ℕ via the Fibonacci basis.  encode_ranked_rows uses
        it to achieve gauge-invariant state preparation (Layer 2 × Layer 3).
        Fibonacci coding ('11'-terminated) is its practical face and parses the
        folded checkpoint header on load.

    Substrate-free in the precise sense: integer arithmetic mod 2^bits, so the round
    trip is bit-identical on any hardware that can multiply integers."""

    @staticmethod
    def fib_pair(n: int, mod: Optional[int] = None) -> tuple:
        """(F(n), F(n+1)) by fast doubling; exact, or reduced mod `mod`."""
        if n < 0:
            raise ValueError('n must be non-negative')
        red = (lambda x: x % mod) if mod else (lambda x: x)
        a, b = 0, 1
        for bit in bin(n)[2:]:
            c = red(a * (2 * b - a))                   # F(2k)
            d = red(a * a + b * b)                     # F(2k+1)
            a, b = (d, red(c + d)) if bit == '1' else (c, d)
        return a, b

    @classmethod
    def fib(cls, n: int, mod: Optional[int] = None) -> int:
        return cls.fib_pair(n, mod)[0]

    @classmethod
    def lucas(cls, n: int, mod: Optional[int] = None) -> int:
        """L(n) = 2 F(n+1) - F(n) = trace(Q^n)."""
        f_n, f_n1 = cls.fib_pair(n, mod)
        v = 2 * f_n1 - f_n
        return v % mod if mod else v

    @classmethod
    def cassini(cls, n: int) -> int:
        """F(n+1)F(n-1) - F(n)^2, with F(-1) = 1.  Equals (-1)^n = det(Q^n)."""
        f_n, f_n1 = cls.fib_pair(n)
        return f_n1 * (f_n1 - f_n) - f_n * f_n

    @staticmethod
    def pisano_pow2(k: int) -> int:
        """Order of Q modulo 2^k: 3 * 2^(k-1).  Cross-checked by brute force in the theorem suite."""
        if k < 1:
            raise ValueError('k must be positive')
        return 3 * (1 << (k - 1))

    @classmethod
    def _certify(cls, M: tuple, n: int, m: int) -> None:
        """Cassini (det) and Lucas (trace) certificates, checked mod m on the matrix actually used."""
        (a, b), (c, d) = M
        want = 1 if n % 2 == 0 else m - 1
        if (a * d - b * c) % m != want:
            raise GoldenIntegrityError(f'Cassini certificate failed: det(Q^{n}) mod m != (-1)^{n}')
        if (a + d) % m != cls.lucas(n, m):
            raise GoldenIntegrityError(f'Lucas certificate failed: trace(Q^{n}) != L({n}) mod m')

    @classmethod
    def fold_matrix(cls, steps: int, bits: int) -> tuple:
        """(Q^steps mod 2^bits, reduced steps).  Steps reduce mod the Pisano period first."""
        if not 8 <= bits <= 4096 or bits % 8:
            raise ValueError(f'bits must be a multiple of 8 in [8, 4096], got {bits}')
        if steps < 0:
            raise ValueError('steps must be non-negative')
        m = 1 << bits
        n = steps % cls.pisano_pow2(bits)
        f_n, f_n1 = cls.fib_pair(n, m)
        M = ((f_n1, f_n), (f_n, (f_n1 - f_n) % m))
        cls._certify(M, n, m)
        return M, n

    @classmethod
    def unfold_matrix(cls, steps: int, bits: int) -> tuple:
        """Exact integer inverse of Q^steps mod 2^bits: (-1)^n times the adjugate (Cassini)."""
        ((a, b), (c, d)), n = cls.fold_matrix(steps, bits)
        m = 1 << bits
        sgn = 1 if n % 2 == 0 else -1
        return ((sgn * d % m, -sgn * b % m), (-sgn * c % m, sgn * a % m))

    @classmethod
    def fold_words(cls, words: Sequence[int], steps: int, bits: int) -> List[int]:
        """Fold consecutive (lo, hi) pairs.  Bijective on (Z/2^bits)^2, so exactly invertible."""
        return cls._apply_words(cls.fold_matrix(steps, bits)[0], words, bits)

    @classmethod
    def unfold_words(cls, words: Sequence[int], steps: int, bits: int) -> List[int]:
        return cls._apply_words(cls.unfold_matrix(steps, bits), words, bits)

    @staticmethod
    def _apply_words(M: tuple, words: Sequence[int], bits: int) -> List[int]:
        if len(words) % 2:
            raise ValueError('fold operates on (lo, hi) pairs: word count must be even')
        m = 1 << bits
        (a, b), (c, d) = M
        out: List[int] = []
        for i in range(0, len(words), 2):
            lo, hi = words[i], words[i + 1]
            out += [(a * lo + b * hi) % m, (c * lo + d * hi) % m]
        return out

    @classmethod
    def zeckendorf(cls, n: int) -> List[int]:
        """Ascending Fibonacci indices (>= 2, no two adjacent) summing to n.  Unique."""
        if n < 0:
            raise ValueError('n must be non-negative')
        if n == 0:
            return []
        fibs = [0, 1, 1]                                  # F(0), F(1), F(2)
        while fibs[-1] <= n:
            fibs.append(fibs[-1] + fibs[-2])
        k, chosen = len(fibs) - 1, []
        while n:
            while fibs[k] > n:
                k -= 1
            chosen.append(k)
            n -= fibs[k]
            k -= 1                                        # remainder < F(k-1), so non-adjacency is automatic
        return chosen[::-1]

    @classmethod
    def unzeckendorf(cls, indices: Sequence[int]) -> int:
        return sum(cls.fib(i) for i in indices)

    @classmethod
    def fib_code(cls, n: int) -> str:
        """Self-delimiting Fibonacci code of n >= 0 (encodes n + 1; '11' terminates the word)."""
        z = set(cls.zeckendorf(n + 1))
        return ''.join('1' if i in z else '0' for i in range(2, max(z) + 1)) + '1'   # top bit is 1, so this makes '11'

    @classmethod
    def fib_decode(cls, stream: str, pos: int = 0) -> tuple:
        """Decode one codeword starting at `pos`; returns (n, position after the terminator)."""
        total, prev, k, i = 0, False, 2, pos
        while i < len(stream):
            if stream[i] == '1':
                if prev:
                    return total - 1, i + 1
                total += cls.fib(k)
                prev = True
            else:
                prev = False
            i += 1
            k += 1
        raise GoldenIntegrityError('Fibonacci code truncated: no terminator found')


class StateCheckpoint:
    """Checkpoints are bit-exact: amplitudes are stored as their raw float64 words, FOLDED by
    GoldenArithmetic (Q^steps mod 2^64).  The fold costs nothing (Cassini: det +/-1, exact
    integer inverse) and buys diffusion: a low-order bit edit in a raw float moves the norm by
    ~1e-16 and sails past any tolerance, but the same edit on a folded word unfolds to garbage
    across the whole pair and the norm check catches it.  The header (steps, bits, word count)
    is Fibonacci-coded, so parsing it IS Zeckendorf arithmetic, and it carries the folded
    words' sum, verified before anything unfolds: losslessness is the determinant's job, the sum
    only detects edits (it is a detector, not a MAC: a compensating multi-word edit can pass it).
    Legacy 'state' blobs still load."""

    FOLD_STEPS = 10**9 + 7     # any size works: fold_matrix reduces mod the Pisano period pi(2^64)

    @staticmethod
    def save(reg: QuantumRegister, path: str, steps: int = None):
        steps = StateCheckpoint.FOLD_STEPS if steps is None else steps
        raw = np.ascontiguousarray(reg.state.amplitudes, dtype=np.complex128).tobytes()
        words = [int.from_bytes(raw[i:i + 8], 'little') for i in range(0, len(raw), 8)]
        folded = GoldenArithmetic.fold_words(words, steps, 64)
        word_sum = sum(folded) & 0xFFFF_FFFF_FFFF_FFFF
        header = (GoldenArithmetic.fib_code(steps) + GoldenArithmetic.fib_code(64)
                  + GoldenArithmetic.fib_code(len(folded)) + GoldenArithmetic.fib_code(word_sum))
        blob = {'qubits': reg.qubits, 'dim': reg.dim,
                'golden_header': header, 'payload': ''.join(f'{w:016x}' for w in folded),
                'depth': reg.depth, 'operations': reg.operations, 'labels': list(reg.state.labels)}
        with open(path, 'w') as f:
            json.dump(blob, f, indent=2)
        return path

    @staticmethod
    def load(path: str, tol: float = 1e-6):
        with open(path) as f:
            blob = json.load(f)
        reg = QuantumRegister(int(blob['qubits']))
        if 'payload' in blob:
            steps, pos = GoldenArithmetic.fib_decode(blob['golden_header'])
            bits, pos = GoldenArithmetic.fib_decode(blob['golden_header'], pos)
            n_words, pos = GoldenArithmetic.fib_decode(blob['golden_header'], pos)
            word_sum, _ = GoldenArithmetic.fib_decode(blob['golden_header'], pos)
            if bits != 64:                                  # the format writes 64-bit words, nothing else
                raise QuantumContractError(f'checkpoint format uses 64-bit words; header says {bits}')
            if n_words != 2 * reg.dim:                      # validated BEFORE any width arithmetic runs on it
                raise QuantumContractError(f'header promises {n_words} words; {reg.dim} amplitudes need {2 * reg.dim}')
            width = bits // 4
            hx = blob['payload']
            if len(hx) != n_words * width:
                raise QuantumContractError(f'payload is {len(hx)} hex chars; header promises {n_words * width}')
            words = [int(hx[i * width:(i + 1) * width], 16) for i in range(n_words)]
            if sum(words) & 0xFFFF_FFFF_FFFF_FFFF != word_sum:
                raise QuantumContractError('word sum mismatch: payload edited since save')
            raw = b''.join(w.to_bytes(bits // 8, 'little')
                           for w in GoldenArithmetic.unfold_words(words, steps, bits))
            amps = np.frombuffer(raw, dtype=np.complex128).copy()
        else:                                             # legacy format: plain [re, im] lists
            amps = np.array([complex(r, i) for r, i in blob['state']])
        if len(amps) != reg.dim:
            raise QuantumContractError(f'Checkpoint has {len(amps)} amplitudes for a {reg.qubits}-qubit register')
        norm = float(np.linalg.norm(amps))
        if not np.isfinite(norm) or abs(norm - 1.0) > tol:   # NaN/inf is corruption too, not a pass
            raise QuantumContractError(f'Checkpoint norm {norm} deviates from 1 by more than {tol}')
        reg.state = QuantumState(amps, labels=blob.get('labels'))   # renormalizes only float-rounding noise
        reg.depth = int(blob.get('depth', 0))
        reg.operations = list(blob.get('operations', []))
        return reg


# =============================================================================
# Layer 2 ↔ Layer 1:  the indicator vector IS the amplitude vector
# =============================================================================

class QuantumFeatureState:
    """Amplitude encoding:  the real-valued slot vector that _indicator_vector() produces
    IS already a vector in H; this class normalises it onto the unit sphere of a
    2^k-dimensional Hilbert space so the fidelity kernel, density matrices, and the
    full operator algebra of Layer 1 apply to it directly."""

    @staticmethod
    def encode(vector: np.ndarray, max_dim: int = 256) -> QuantumState:
        """State preparation on the 2^k-dimensional Hilbert space.

        Centre, scale, pad to a power of two, normalise.  A constant vector (zero
        variance) carries no information: returns |0⟩ (the vacuum).  The centering
        removes the global phase; the scaling sets the norm; the padding embeds into the
        nearest power-of-two dimension so the operator algebra is well-defined."""
        v = np.nan_to_num(np.asarray(vector, dtype=float).ravel())
        if v.size == 0:
            return QuantumMath.ket0(2)
        target = min(2 ** int(np.ceil(np.log2(max(2, len(v))))), max_dim)
        if len(v) > target:
            v = np.array([c.mean() for c in np.array_split(v, target)])
        v = v - v.mean()                   # center/scale the REAL features first ...
        std = v.std()
        if std == 0:                       # constant vector: no information, use |0>
            return QuantumMath.ket0(target)
        v = np.pad(v / std, (0, target - len(v)))   # ... then pad, so padding never leaks into the mean
        return QuantumState(v.astype(complex))

    @staticmethod
    def encode_ranked_rows(X: np.ndarray, max_dim: int = 256) -> List['QuantumState']:
        """Layer 2 × Layer 3:  gauge-invariant state preparation via the Fibonacci basis.

        Rank each feature (gauge invariance: ranks are invariant under all strictly
        monotone per-feature maps).  Zeckendorf-encode each rank into its unique 0/1
        vector of Fibonacci indices (Layer 3: the bijection on ℕ via the golden basis,
        no two adjacent ones).  Concatenate the per-feature blocks.  Amplitude-encode
        the bits (Layer 1: the state |ψ⟩ ∈ H).

        The fidelity kernel K(a,b) = |⟨φ(a)|φ(b)⟩|² over these states is therefore
        invariant under ALL strictly monotone per-feature transformations — the full
        gauge group — not merely affine ones.  Ranks are the integer domain where
        Zeckendorf is a bijection rather than a costume; the Fibonacci basis IS the
        natural encoding for gauge-invariant quantum state preparation."""
        X = np.atleast_2d(np.asarray(X, dtype=float))
        n, d = X.shape
        if n == 0 or d == 0:
            raise QuantumContractError('encode_ranked_rows needs a non-empty matrix')
        ranks = np.column_stack([pd.Series(X[:, j]).rank(method='dense').astype(int).to_numpy()
                                 for j in range(d)])
        top = max(GoldenArithmetic.zeckendorf(int(r))[-1] for r in ranks.max(axis=0))
        width = top - 1                                       # indices run 2..top -> top-1 bit slots
        states = []
        for i in range(n):
            bits: List[float] = []
            for j in range(d):
                z = set(GoldenArithmetic.zeckendorf(int(ranks[i, j])))
                bits += [1.0 if (k + 2) in z else 0.0 for k in range(width)]
            states.append(QuantumFeatureState.encode(np.array(bits), max_dim=max_dim))
        return states


class QuantumEnsemble:
    """The POVM in density-matrix form.

    predict() runs N models, each returning a score.  That IS a POVM: each model is an
    effect operator E_i, each score is the Born-rule outcome Tr(E_i ρ).  This class
    constructs the explicit density matrix ρ = Σ_i w_i |ψ_i⟩⟨ψ_i| and extracts the
    diagnostics that the operator algebra provides for free:

        purity  Tr(ρ²)              → confidence = |r̄|² (how sharply the POVM concentrates)
        von Neumann entropy S(ρ)    → model_disagreement_entropy (information-theoretic)
        pooled probability ρ[1,1]   ≡ weighted mean of scores (exact identity, not approximation)

    SCOPE OF `confidence`:  it measures AGREEMENT between models of the same family on the
    same features, high exactly when they co-move.  It is not accuracy.  It does not see
    missing inputs: completeness (GapRegister = decoherence record) catches the input gap.
    Do not read the two as one number.

    Model i with score p_i → |ψ_i⟩ = √(1−p_i)|0⟩ + √(p_i)|1⟩.
    ρ = Σ_i w_i |ψ_i⟩⟨ψ_i|.  This layer cannot change WHAT the ensemble predicts (ρ[1,1]
    = weighted mean); what it adds is the full operator-algebraic diagnostic layer.
    """

    @staticmethod
    def mix(scores: Dict[str, float], weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        names = list(scores)
        if not names:
            raise QuantumContractError('No model scores to mix')
        w = np.array([max(0.0, (weights or {}).get(n, 1.0)) for n in names], dtype=float)
        w = w / w.sum() if w.sum() > 0 else np.ones(len(names)) / len(names)
        rho = np.zeros((2, 2), dtype=complex)
        for wi, n in zip(w, names):
            p = float(np.clip(scores[n], 0.0, 1.0))
            rho += wi * QuantumState(np.array([np.sqrt(1 - p), np.sqrt(p)], dtype=complex)).density_matrix()
        rho = rho / np.real(np.trace(rho))
        purity = float(np.real(np.trace(rho @ rho)))
        defined = len(names) >= 2          # one voter is a pure state: purity == 1 at EVERY p, so it measures nothing
        return {'pooled_probability': float(np.real(rho[1, 1])),
                'purity': purity,
                'confidence': float(np.clip(2 * purity - 1, 0.0, 1.0)) if defined else None,   # = |Bloch vector|^2
                'model_disagreement_entropy': _entropy_bits(rho) if defined else None,
                'confidence_defined': defined,      # branch on this, not on truthiness: 0.0 is a valid confidence
                'n_models': len(names),
                'weights_used': dict(zip(names, w.tolist()))}


class QuantumKernel:
    """Bures metric on the state space.

    K(a,b) = |⟨φ(a)|φ(b)⟩|² is the fidelity kernel — positive semi-definite, and the
    natural Riemannian metric on the space of prepared states.  The Gram matrix it
    produces IS the inner-product structure of the Hilbert space that Layer 2 defines:
    the indicator vectors, normalised and encoded, live on this manifold."""

    @staticmethod
    def gram_matrix(X: np.ndarray) -> np.ndarray:
        states = [QuantumFeatureState.encode(row) for row in np.atleast_2d(X)]
        K = np.zeros((len(states), len(states)))
        for i, a in enumerate(states):
            for j in range(i, len(states)):
                if len(a.amplitudes) != len(states[j].amplitudes):
                    raise QuantumContractError('Encoded states have different dimensions')
                K[i, j] = K[j, i] = QuantumMath.fidelity(a, states[j])
        return K


class QuantumWeightOptimizer:
    """Variational search over POVM weights.

    The ensemble of N models IS a POVM with N effect operators.  Their relative weights
    determine the measurement basis.  This optimizer searches for the weight vector that
    minimises a physically motivated Ising Hamiltonian:

    Ansatz: Ry(θ_i) on every qubit (|0⟩ = 'unselected', |1⟩ = 'selected').
    Cost:   H = Σ_i (s_i − mean(s)) Z_i + λ Σ_{i<j} Z_i Z_j
            → above-average models lower the energy when selected (Z=−1 on |1⟩),
              below-average ones when dropped; the ZZ term penalises selecting or
              ignoring models in lockstep (encourages a diversified POVM).
    Weights = P(qubit i is |1⟩) = sin²(θ_i/2), floored at 0.05, normalised.
    Optimizer: seeded stochastic hill climbing (no gradients).
    """

    def __init__(self, n_models: int, seed: int = 1337, iterations: int = 200, lam: float = 0.3,
                 restarts: int = 8):
        self.n, self.iterations, self.lam, self.restarts = n_models, iterations, lam, restarts
        self.rng = np.random.default_rng(seed)

    def _cost_hamiltonian(self, scores: np.ndarray) -> Hamiltonian:
        H = Hamiltonian(self.n)
        centered = scores - scores.mean()
        for i in range(self.n):
            H.add_term(float(centered[i]), 'Z', [i])
        for i in range(self.n):
            for j in range(i + 1, self.n):
                H.add_term(self.lam, 'Z', [i, j])
        return H

    def _energy(self, H: Hamiltonian, theta: np.ndarray) -> float:
        reg = QuantumRegister(self.n)
        for i in range(self.n):
            reg.apply(QuantumMathPrimitives.ry(float(theta[i])), targets=[i])
        return H.expectation(reg.state)

    def optimize(self, scores: np.ndarray) -> Dict[str, Any]:
        s = np.asarray(scores, dtype=float)
        H = self._cost_hamiltonian(s)
        best, best_e = None, np.inf
        for _ in range(self.restarts):                     # seeded random restarts
            cur = self.rng.uniform(0, np.pi, self.n)
            cur_e, step = self._energy(H, cur), 0.5
            for _ in range(self.iterations):
                cand = np.clip(cur + self.rng.normal(0, step, self.n), 0.0, np.pi)
                e = self._energy(H, cand)
                if e < cur_e:
                    cur, cur_e = cand, e
                else:
                    step = max(0.02, step * 0.995)
            if cur_e < best_e:
                best, best_e = cur, cur_e
        w = np.clip(np.sin(best / 2) ** 2, 0.05, 1.0)
        return {'weights': (w / w.sum()).tolist(), 'energy': float(best_e),
                'ground_energy': H.ground_energy(), 'angles': best.tolist()}


class QuantumUnifiedEngine:
    """Full-stack quantum channel:  orchestrator (Layer 2: state preparation + POVM) joined
    with the explicit Hilbert-space algebra (Layer 1) for density-matrix diagnostics,
    fidelity kernels, and weight optimisation on the same prepared states."""

    def __init__(self, orchestrator: UnifiedAnalyticsOrchestrator, qmath: Optional[QuantumMathEngine] = None):
        self.orchestrator = orchestrator
        self.qmath = qmath or QuantumMathEngine({'backend': 'math'})
        self.audit: List[Dict[str, Any]] = []

    def fit(self, df: pd.DataFrame, y: Optional[pd.Series] = None) -> 'QuantumUnifiedEngine':
        self.orchestrator.fit(df, y)
        self.audit.append({'event': 'fit', 'rows': len(df)})
        return self

    def predict(self, df: pd.DataFrame, use_optimized_weights: bool = False,
                weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        result = self.orchestrator.predict(df)
        scores = {n: e['score'] for n, e in result['models'].items()}
        if use_optimized_weights:
            opt = self.optimize_model_weights(scores)
            weights = dict(zip(opt['models'], opt['weights']))
        q = QuantumEnsemble.mix(scores, weights)
        result['unweighted_score'] = result['score']          # classical mean, kept for comparison
        result['score'] = q['pooled_probability']             # authoritative: equals decision.probability
        result['quantum_decision'] = q
        result['decision'] = {'probability': q['pooled_probability'], 'confidence': q['confidence'],
                              'disagreement': q['model_disagreement_entropy'],
                              'confidence_defined': q['confidence_defined'],
                              'label': int(q['pooled_probability'] >= 0.5)}
        eng, g = self.orchestrator.engine, result['gaps']
        cw, base = g['completeness_weighted'], eng.base_rate
        result['data_quality'] = {                            # informational: `score` stays the pooled probability
            'completeness': g['completeness'], 'completeness_weighted': cw, 'base_rate': base,
            'shrunk_probability': (cw * q['pooled_probability'] + (1 - cw) * base) if base is not None else None}
        self.orchestrator.monitor.log('predict_score_pooled', q['pooled_probability'])   # the number the caller received
        self.audit.append({'event': 'quantum_predict', 'purity': q['purity']})
        return result

    def optimize_model_weights(self, scores: Dict[str, float], method: str = 'exact',
                               lam: float = 0.3) -> Dict[str, Any]:
        """method='exact': closed form (the implemented H has uniform all-to-all coupling).
        method='variational': seeded VQE-style search (needed only if couplings become non-uniform)."""
        names = list(scores)
        arr = np.array([scores[n] for n in names], dtype=float)
        if method == 'exact':
            res = ExactIsingWeightSolver(lam).solve(arr - arr.mean())
            out = {'models': names, 'weights': res['weights'], 'energy': res['energy'],
                   'selected': [n for n, f in zip(names, res['selected']) if f], 'method': 'exact'}
        else:
            out = {'models': names, **QuantumWeightOptimizer(len(names), lam=lam).optimize(arr),
                   'method': 'variational'}
        self.audit.append({'event': 'quantum_weight_optimization', 'energy': out['energy'], 'method': method})
        return out

    def row_similarity(self, row_a: pd.Series, row_b: pd.Series) -> float:
        a = pd.to_numeric(row_a, errors='coerce').to_numpy(dtype=float)
        b = pd.to_numeric(row_b, errors='coerce').to_numpy(dtype=float)
        return QuantumMath.fidelity(QuantumFeatureState.encode(a), QuantumFeatureState.encode(b))


class UnifiedAnalyticsSession:
    """One process, N domains.  Proofs run once; each domain is an orchestrator built from the registry."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or tempfile.mkdtemp(prefix='uqe_session_')
        self.domains: Dict[str, 'QuantumUnifiedEngine'] = {}
        self.proofs: Optional[Dict[str, Any]] = None

    def verify(self) -> Dict[str, Any]:
        """Quantum self-tests + verified identities, once per session."""
        results = {'quantum': QuantumTestSuite.run(), 'identities': TheoremVerificationSuite.run()}
        failed = [n for group in results.values() for n, ok in group if not ok]
        self.proofs = {'passed': sum(ok for g in results.values() for _, ok in g),
                       'total': sum(len(g) for g in results.values()), 'failed': failed}
        if failed:
            raise AssertionError(f'verification failed: {failed}')
        return self.proofs

    def open(self, domain: str, **config) -> 'QuantumUnifiedEngine':
        orch = UnifiedAnalyticsOrchestrator.for_domain(domain, os.path.join(self.base_dir, domain), **config)
        self.domains[domain] = QuantumUnifiedEngine(orch)
        return self.domains[domain]

    def fit(self, domain: str, df: pd.DataFrame, y: Optional[pd.Series] = None) -> 'UnifiedAnalyticsSession':
        (self.domains.get(domain) or self.open(domain)).fit(df, y)
        return self

    def decide(self, domain: str, df: pd.DataFrame, **kw) -> Dict[str, Any]:
        return self.domains[domain].predict(df, **kw)

    def engine(self, domain: str) -> UnifiedAnalyticsEngine:
        return self.domains[domain].orchestrator.engine

    def gap_register(self, domain: str) -> Dict[str, Any]:
        e = self.engine(domain)
        return {'profile': e.profile.name if e.profile else None,
                'mode': e.profile.mode if e.profile else None, 'chunk_rows': e.config.chunk_rows,
                'width': len(e.slot_names), 'absent_slots': list(e.absent_slots),
                'dropped_for_width': list(e.dropped_for_width),
                'wide_vs_chunks': e.wide_vs_chunks}


# =============================================================================
# Self-tests, package index, entry point
# =============================================================================


# =============================================================================
# Elevation layer: exact solver, operator embedding, calibrated coherent committee
# =============================================================================

def embed_operator(op: QuantumOperator, targets: Sequence[int], n: int) -> QuantumOperator:
    """Full 2^n x 2^n matrix of a k-qubit gate acting on `targets` (qubit 0 = leftmost factor)."""
    dim = 2 ** n
    cols = [_apply_local(np.eye(dim, dtype=complex)[:, j], op.matrix, list(targets), n) for j in range(dim)]
    return QuantumOperator(np.stack(cols, axis=1), name=f'{op.name}@{list(targets)}')


MultiQubitMath.embed = staticmethod(embed_operator)


def ising_energy(h: np.ndarray, z: np.ndarray, lam: float, J: Optional[np.ndarray] = None) -> float:
    """E(z) = sum_i h_i z_i + sum_{i<j} J_ij z_i z_j  (J defaults to uniform lam)."""
    n = len(h)
    if J is None:
        M = z.sum()
        return float(h @ z + lam * 0.5 * (M * M - n))
    return float(h @ z + sum(J[i, j] * z[i] * z[j] for i in range(n) for j in range(i + 1, n)))


def ising_bruteforce(h: np.ndarray, lam: float = 0.3, J: Optional[np.ndarray] = None, max_n: int = 20):
    """Exact for ANY coupling matrix, O(2^n). The honest fallback when the graph is not complete/uniform."""
    n = len(h)
    if n > max_n:
        raise QuantumContractError(f'brute force limited to n <= {max_n}')
    best, bz = np.inf, None
    for bits in range(2 ** n):
        z = np.array([1 - 2 * ((bits >> i) & 1) for i in range(n)], dtype=float)
        e = ising_energy(h, z, lam, J)
        if e < best:
            best, bz = e, z
    return best, bz


class ExactIsingWeightSolver:
    """Exact ground state of the POVM weight Hamiltonian.

    H = Σ_i h_i Z_i + λ Σ_{i<j} Z_i Z_j  (complete, uniform coupling).

    The fields h_i are model scores; the ground state determines which POVM operators
    (models) to select.  This is the same Hamiltonian the QuantumWeightOptimizer
    searches variationally — but for the complete uniform graph, the exact solution is
    O(n log n):

    Proof.  With M = Σ z_i:  Σ_{i<j} z_i z_j = (M²−n)/2.  Let D = {i : z_i=−1}
    ('selected', |1⟩), |D|=k, so M=n−2k and
        E = Σ_i h_i − 2 Σ_{i∈D} h_i + (λ/2)((n−2k)²−n).
    For fixed k, E is minimised by putting the k LARGEST fields in D.  Scanning
    k=0..n over prefix sums is exhaustive.  (Verified against 2^n brute force.)
    Exact only for the complete uniform graph; sparse/weighted J is NP-hard in general.
    """

    def __init__(self, lam: float = 0.3, floor: float = 0.05):
        self.lam, self.floor = float(lam), float(floor)

    def solve(self, fields: np.ndarray) -> Dict[str, Any]:
        h = np.asarray(fields, dtype=float)
        n = len(h)
        order = np.argsort(-h, kind='stable')
        prefix = np.concatenate([[0.0], np.cumsum(h[order])])
        ks = np.arange(n + 1)
        E = h.sum() - 2 * prefix + 0.5 * self.lam * ((n - 2 * ks) ** 2 - n)
        k = int(np.argmin(E))
        selected = np.zeros(n, dtype=bool)
        selected[order[:k]] = True
        w = np.where(selected, 1.0, self.floor)
        return {'selected': selected.tolist(), 'k_selected': k, 'energy': float(E[k]),
                'weights': (w / w.sum()).tolist(), 'spins': np.where(selected, -1, 1).tolist()}


class CalibratedCoherentCommittee:
    """Phase-calibrated POVM with coherence structure derived from data (label-free).

    The ensemble IS a POVM.  QuantumEnsemble constructs ρ without phases (the real
    subalgebra — coplanar Bloch baseline).  This class lifts to the full algebra:

    Voter i with score p_i:  |ψ_i⟩ = √(1−p_i)|0⟩ + e^{iφ_i} √(p_i)|1⟩.

    Phases encode error-correlation structure:  calibrate() extracts the first
    principal component of score deviations (p_i − mean p) on a holdout set and sets
    φ_i = arccos(corr(deviation_i, PC1)).  Models co-moving with the dominant
    disagreement axis get φ≈0; those opposing it get φ≈π.

    Bloch-vector identity:  confidence = |r̄|²,  1 − confidence = weighted variance.
    This is exact for qubits, not an approximation.

    This is a *hypothesis* about useful structure, not a theorem; use
    `committee_experiment` to test whether phases add anything beyond score variance.
    The spectral discrimination protocols (T1, T2) measure exactly this.
    """

    def __init__(self):
        self.phases: Optional[np.ndarray] = None

    def calibrate(self, P: np.ndarray) -> 'CalibratedCoherentCommittee':
        P = np.asarray(P, dtype=float)
        D = P - P.mean(axis=1, keepdims=True)
        D = D - D.mean(axis=0)
        if D.std() < 1e-12:
            self.phases = np.zeros(P.shape[1]); return self
        U, S, Vt = np.linalg.svd(D, full_matrices=False)
        pc = D @ Vt[0]
        c = np.array([np.corrcoef(D[:, i], pc)[0, 1] if D[:, i].std() > 1e-12 else 1.0
                      for i in range(P.shape[1])])
        self.phases = np.arccos(np.clip(np.nan_to_num(c, nan=1.0), -1, 1))
        return self

    @staticmethod
    def diagnostics(P: np.ndarray, phases: np.ndarray, weights: Optional[np.ndarray] = None):
        """Vectorized over rows of P.  C = |rbar|^2, S = h2((1+|rbar|)/2)  (exact for qubits)."""
        P = np.clip(np.atleast_2d(P), 0.0, 1.0)
        w = np.ones(P.shape[1]) if weights is None else np.asarray(weights, float)
        w = w / w.sum()
        a = 2 * np.sqrt(P * (1 - P))
        rx = (w * a * np.cos(phases)).sum(axis=1)
        ry = (w * a * np.sin(phases)).sum(axis=1)
        rz = (w * (1 - 2 * P)).sum(axis=1)
        C = rx ** 2 + ry ** 2 + rz ** 2
        q = np.clip((1 + np.sqrt(np.clip(C, 0, 1))) / 2, 1e-15, 1 - 1e-15)
        S = -(q * np.log2(q) + (1 - q) * np.log2(1 - q))
        return {'pooled_probability': (w * P).sum(axis=1), 'confidence': C, 'entropy': S}

    def mix(self, scores: Sequence[float], weights: Optional[np.ndarray] = None) -> Dict[str, float]:
        if self.phases is None:
            raise RuntimeError('calibrate() first')
        d = self.diagnostics(np.asarray(scores)[None, :], self.phases, weights)
        return {k: float(v[0]) for k, v in d.items()}


def _density_matrix_diagnostics(scores, phases, weights):
    """Reference implementation via explicit density matrices (cross-check for diagnostics())."""
    w = np.asarray(weights, float) / np.sum(weights)
    rho = np.zeros((2, 2), dtype=complex)
    for wi, p, ph in zip(w, scores, phases):
        rho += wi * QuantumState(np.array([np.sqrt(1 - p), np.exp(1j * ph) * np.sqrt(p)])).density_matrix()
    return {'confidence': 2 * float(np.real(np.trace(rho @ rho))) - 1, 'entropy': _entropy_bits(rho)}


def _spearman(a: np.ndarray, b: np.ndarray):
    """(rho, ok).  A constant input has no rank correlation: returns (0.0, False) instead of NaN."""
    ra, rb = pd.Series(a).rank().to_numpy(), pd.Series(b).rank().to_numpy()
    if ra.std() == 0 or rb.std() == 0:
        return 0.0, False
    return float(np.corrcoef(ra, rb)[0, 1]), True


def committee_experiment(n_models: int = 6, m_hold: int = 3000, m_test: int = 6000,
                         cluster_sign: float = -1.0, calib_sign: Optional[float] = None,
                         seed: int = 0) -> Dict[str, Any]:
    """Does calibrated phase structure predict the pooled mean's error better than plain score spread?

    Synthetic world: latent logit z; model scores = sigmoid(z + noise_i) where models in the
    first half share noise g, the second half share cluster_sign*g (complementary if -1,
    redundant if +1), plus idiosyncratic noise.  Target: |pooled_mean - true_probability|.
    Uncertainty predictors are compared by Spearman rank correlation with that error.
    """
    rng = np.random.default_rng(seed)
    sig = lambda x: 1 / (1 + np.exp(-x))

    def draw(m, sign):
        z = rng.normal(0, 1.5, m)
        g = rng.normal(0, 1.0, m)
        half = n_models // 2
        shared = np.where(np.arange(n_models) < half, 1.0, sign)[None, :] * g[:, None]
        P = sig(z[:, None] + 0.8 * shared + 0.4 * rng.normal(size=(m, n_models)))
        return P, sig(z)

    calib_sign = cluster_sign if calib_sign is None else calib_sign
    Ph, _ = draw(m_hold, calib_sign)       # calibration world
    Pt, t = draw(m_test, cluster_sign)     # test world (may differ: tests transfer, not just fit)
    err = np.abs(Pt.mean(axis=1) - t)
    com = CalibratedCoherentCommittee().calibrate(Ph)
    zero = np.zeros(n_models)
    d_cal = CalibratedCoherentCommittee.diagnostics(Pt, com.phases)
    d_zero = CalibratedCoherentCommittee.diagnostics(Pt, zero)
    # cross-check vectorized math against explicit density matrices on a few rows
    for i in range(5):
        ref = _density_matrix_diagnostics(Pt[i], com.phases, np.ones(n_models))
        if abs(ref['confidence'] - d_cal['confidence'][i]) > 1e-9 or abs(ref['entropy'] - d_cal['entropy'][i]) > 1e-9:
            raise RuntimeError('vectorized diagnostics disagree with the explicit density-matrix reference')
    preds = {'score_std (classical)': Pt.std(axis=1),
             '1-C, phases=0 (coplanar)': 1 - d_zero['confidence'],
             '1-C, calibrated phases': 1 - d_cal['confidence'],
             'S, calibrated phases': d_cal['entropy']}
    rho, degenerate = {}, []
    for k, v in preds.items():
        rho[k], ok = _spearman(v, err)
        if not ok:
            degenerate.append(k)
    return {'calibrated_on': calib_sign, 'tested_on': cluster_sign, 'phases': np.round(com.phases, 3).tolist(),
            'spearman_vs_error': rho, 'degenerate': degenerate}


# =============================================================================
# Spectral certificate layer — quantum mathematical discrimination infrastructure
# =============================================================================
#
# This is NOT a claims-management layer.  It is the mathematical framework for
# measuring when a quantum observable's spectrum separates from a classical
# observable's spectrum on given data.  The spectral gap is the operational
# content of "advantage": if gap > 0 the quantum structure captures something
# the classical structure misses; if gap ≤ 0 it does not.  Recording both
# directions — certificates and closures — with the same rigour is what makes
# the mathematics honest.
#
# From the operator-algebraic viewpoint:
#   - The committee IS a POVM: N models → N rank-1 projectors, the mixture is ρ.
#   - The Bloch vector |r̄| measures distance from the maximally mixed state.
#   - Phases encode the non-commutative part of the correlation algebra.
#   - The coplanar baseline (phases=0) restricts ρ to the maximal commutative
#     subalgebra — the "classical part" of the quantum geometry.
#   - The Mahalanobis baseline IS the Fisher-Rao distance on the statistical
#     manifold under the calibration covariance.
#   - A spectral gap closure = the quantum observable's spectrum no longer
#     separates from the classical observable's.
# =============================================================================


@dataclass(frozen=True)
class SpectralCertificate:
    """One certified spectral gap: quantum observable O_Q separated from
    classical observable O_C on data manifold M, backed by a proven identity.

    `kind` is the epistemic status:
        DIAGNOSTIC — exact identity, no advantage claim (e.g. committee geometry)
        PROVED     — the gap is a theorem (e.g. monotone invariance of Zeckendorf kernel)
        MEASURED   — the gap was measured on data, protocol attached
    """
    surface: str                # which quantum surface (e.g. 'committee_geometry')
    kind: str                   # DIAGNOSTIC | PROVED | MEASURED
    domain: str                 # data domain (e.g. 'model_risk')
    protocol: str               # which protocol produced the evidence
    identity: str               # the mathematical identity that backs it
    note: str                   # plain-language what-it-means


@dataclass(frozen=True)
class SpectralGapClosure:
    """One measured spectral gap closure: the quantum observable LOST to the
    classical baseline.

    This is NOT a bug.  It is the expected outcome when the data's structure
    does not reward the quantum geometry.  Filing it with the same schema as
    a certificate is what makes the ledger symmetric.
    """
    surface: str
    kind: str                   # always 'FALSIFIED'
    domain: str
    protocol: str               # T1, T2, T4, etc.
    metric: str                 # what was measured
    quantum_value: float
    classical_value: float
    delta: float                # quantum − classical (negative ⇒ quantum lost)
    classical_baseline: str     # which classical observable won
    note: str                   # why the loss is structural, not a bug


class SpectralCertificateRegistry:
    """Two books: certificates (gap open) and closures (gap closed).

    The registry consumes identities from TheoremVerificationSuite and protocol
    results from SpectralDiscrimination.  ``summary()`` reads both books and
    produces the sentence that belongs in front of a regulator — including the
    losses, not just the rigour.
    """

    def __init__(self):
        self.certificates: List[SpectralCertificate] = []
        self.closures: List[SpectralGapClosure] = []

    # -- registration ---------------------------------------------------------

    def register(self, cert: SpectralCertificate) -> 'SpectralCertificateRegistry':
        self.certificates.append(cert)
        return self

    def record_closure(self, closure: SpectralGapClosure) -> 'SpectralCertificateRegistry':
        self.closures.append(closure)
        return self

    # -- auto-ingest from protocol results ------------------------------------

    def ingest_protocol_result(self, result: Dict[str, Any],
                               domain: str = 'synthetic') -> 'SpectralCertificateRegistry':
        """Consume a T1/T2 result dict and file it into the appropriate book.

        If the strongest classical baseline beats the quantum calibrated measure
        by |Spearman|, the result is a gap closure; otherwise it is a measured
        certificate.
        """
        rho = result.get('spearman_vs_error', {})
        classical_keys = [k for k in rho if 'classical' in k.lower() or 'coplanar' in k.lower()]
        quantum_keys   = [k for k in rho if 'calibrated' in k.lower() and 'coplanar' not in k.lower()]
        if classical_keys and quantum_keys:
            best_classical = max(classical_keys, key=lambda k: abs(rho[k]))
            best_quantum   = max(quantum_keys,   key=lambda k: abs(rho[k]))
            qv, cv = abs(rho[best_quantum]), abs(rho[best_classical])
            if cv > qv:
                self.record_closure(SpectralGapClosure(
                    surface='committee_diagnostics', kind='FALSIFIED', domain=domain,
                    protocol='T1_rank_correlation', metric='|Spearman|',
                    quantum_value=qv, classical_value=cv, delta=qv - cv,
                    classical_baseline=best_classical,
                    note='Quantum rank correlation weaker than strongest classical baseline'))
            else:
                self.register(SpectralCertificate(
                    surface='committee_diagnostics', kind='MEASURED', domain=domain,
                    protocol='T1_rank_correlation',
                    identity=f'|rho_Q|={qv:.4f} > |rho_C|={cv:.4f}',
                    note='Calibrated quantum measure showed stronger rank correlation '
                         'with true error than the strongest classical baseline'))
        return self

    # -- summary (model risk statement) ---------------------------------------

    def summary(self) -> str:
        """The model-risk statement: what the spectral record says, honestly."""
        parts: List[str] = []
        for c in self.certificates:
            parts.append(f'Certified [{c.kind}] {c.surface} @ {c.domain} '
                         f'— backed by {c.identity}.')
        if self.closures:
            losses = '; '.join(
                f'{g.protocol} ({g.metric}: quantum={g.quantum_value:.4f} '
                f'< classical={g.classical_value:.4f})'
                for g in self.closures)
            parts.append(f'Measured counterevidence: {losses}.')
        if not parts:
            return 'No spectral certificates or closures recorded.'
        return ' '.join(parts)


class SpectralDiscrimination:
    """Protocols for measuring whether the quantum formalism (Layers 1–2) adds
    structure that the gauge-invariant observables alone (Layer 2 baselines) do not.

    Every 'advantage' claim is a mathematical statement about spectral gaps: does the
    quantum observable O_Q separate from the best comparable observable O_C on the data
    manifold?  Each protocol computes both, compares their spectral ordinates, and files
    the result as a SpectralCertificate (gap open) or SpectralGapClosure (gap closed).
    The ledger is symmetric: losses are filed with the same schema as wins.
    """

    # -- coplanar Bloch baseline (restriction to real subalgebra) -------------

    @staticmethod
    def phase_stripped_bloch(P: np.ndarray,
                             weights: Optional[np.ndarray] = None) -> Dict[str, Any]:
        """Restrict the committee Bloch vector to the real subalgebra (phases=0).

        This is the maximal commutative subalgebra of the committee's observable
        algebra — the "classical part" of the quantum geometry.  If the full
        quantum diagnostic (with calibrated phases) does no better than this
        baseline, the phase structure carries no incremental information.
        """
        zero_phases = np.zeros(P.shape[1])
        d = CalibratedCoherentCommittee.diagnostics(P, zero_phases, weights)
        return {'confidence_coplanar': d['confidence'],
                'entropy_coplanar': d['entropy'],
                'pooled_probability': d['pooled_probability']}

    # -- Fisher-Rao / Mahalanobis baseline ------------------------------------

    @staticmethod
    def fisher_rao_mahalanobis(P: np.ndarray) -> np.ndarray:
        """Mahalanobis distance of each row's score vector under the calibration
        covariance.

        This IS the Fisher-Rao distance on the statistical manifold of the
        model family — the natural classical metric.  Defined only when the
        covariance is non-degenerate (regularised here at 1e-8 for numerical
        stability).
        """
        D   = P - P.mean(axis=0)
        cov = (D.T @ D) / max(P.shape[0] - 1, 1)
        cov += 1e-8 * np.eye(cov.shape[0])          # regularise for rank deficiency
        L   = np.linalg.cholesky(cov)
        z   = np.linalg.solve(L, D.T).T
        return np.sqrt((z ** 2).sum(axis=1))

    # -- T1: rank-correlation protocol ----------------------------------------

    @staticmethod
    def rank_correlation_protocol(P_test: np.ndarray, true_probs: np.ndarray,
                                  phases_calibrated: np.ndarray,
                                  weights: Optional[np.ndarray] = None) -> Dict[str, Any]:
        """T1: partial Spearman of quantum / classical uncertainty against true error.

        Three classical baselines:
          * score_std            — row-wise σ of the score matrix
          * coplanar Bloch       — 1 − |r̄|² with phases forced to 0
          * cov_mahalanobis      — Fisher-Rao distance under calibration covariance

        The quantum measure is 1 − C (calibrated).  The partial Spearman is
        computed against the strongest classical baseline.
        """
        err  = np.abs(P_test.mean(axis=1) - true_probs)
        zero = np.zeros(P_test.shape[1])
        d_cal  = CalibratedCoherentCommittee.diagnostics(P_test, phases_calibrated, weights)
        d_zero = CalibratedCoherentCommittee.diagnostics(P_test, zero, weights)
        mahal  = SpectralDiscrimination.fisher_rao_mahalanobis(P_test)

        preds = {
            'score_std (classical)':       P_test.std(axis=1),
            'coplanar_bloch (classical)':  1 - d_zero['confidence'],
            'cov_mahalanobis (classical)': mahal,
            '1-C_calibrated (quantum)':    1 - d_cal['confidence'],
        }
        rho_vals: Dict[str, float] = {}
        for k, v in preds.items():
            rho_vals[k], _ = _spearman(v, err)

        strongest_classical = max(
            [k for k in rho_vals if 'classical' in k],
            key=lambda k: abs(rho_vals[k]))
        return {'spearman_vs_error': rho_vals,
                'strongest_classical': strongest_classical,
                'strongest_classical_rho': rho_vals[strongest_classical]}

    # -- T2: economic capture protocol ----------------------------------------

    @staticmethod
    def capture_rate_protocol(P_test: np.ndarray, true_probs: np.ndarray,
                              phases_calibrated: np.ndarray,
                              budget_fraction: float = 0.1,
                              weights: Optional[np.ndarray] = None) -> Dict[str, Any]:
        """T2: economic capture at equal measurement budget.

        At a fixed escalation budget (top ``budget_fraction`` of rows by each
        observable), what fraction of the true high-error rows does each
        observable capture?  This is the operational meaning of "advantage"
        in a resource-constrained setting.
        """
        err = np.abs(P_test.mean(axis=1) - true_probs)
        k   = max(1, int(len(err) * budget_fraction))
        true_top = set(np.argsort(-err)[:k])

        zero   = np.zeros(P_test.shape[1])
        d_cal  = CalibratedCoherentCommittee.diagnostics(P_test, phases_calibrated, weights)
        d_zero = CalibratedCoherentCommittee.diagnostics(P_test, zero, weights)
        mahal  = SpectralDiscrimination.fisher_rao_mahalanobis(P_test)

        measures = {
            'score_std':        P_test.std(axis=1),
            'coplanar_bloch':   1 - d_zero['confidence'],
            'cov_mahalanobis':  mahal,
            '1-C_calibrated':   1 - d_cal['confidence'],
        }
        captures: Dict[str, float] = {}
        for name, vals in measures.items():
            top_k = set(np.argsort(-vals)[:k])
            captures[name] = len(top_k & true_top) / max(len(true_top), 1)
        return {'budget_fraction': budget_fraction, 'k': k, 'captures': captures}

    # -- spectral certificate summary (the regulatory sentence) ---------------

    @staticmethod
    def spectral_certificate_summary(registry: 'SpectralCertificateRegistry') -> str:
        """Delegate to the registry's summary — the model-risk statement."""
        return registry.summary()


class TheoremVerificationSuite:
    """The proved identities that make the three-layer structure rigorous.

    Every entry is a mathematical theorem verified against the implementation:
    Layer 1 algebra (embedding, density-matrix, spectral), Layer 3 number theory
    (Cassini, Vajda, Pisano, Lucas traces, modular geodesics, Zeckendorf), and the
    cross-layer connections (fidelity = Bures, checkpoint round-trip, fold unimodularity).
    Only statements that are true."""

    @staticmethod
    def embedding_matches_kron() -> bool:
        rng = np.random.default_rng(7)
        for _ in range(10):
            U = QuantumOperator(QuantumMathPrimitives.rx(rng.uniform(0, 6)).matrix @
                                QuantumMathPrimitives.ry(rng.uniform(0, 6)).matrix)
            t = int(rng.integers(0, 3))
            ref = np.eye(1)
            for q in range(3):
                ref = np.kron(ref, U.matrix if q == t else np.eye(2))
            E = embed_operator(U, [t], 3).matrix
            if not (np.allclose(E, ref) and QuantumMathValidation.is_unitary(QuantumOperator(E))):
                return False
        cnot = QuantumMathPrimitives.cnot()
        ok01 = np.allclose(embed_operator(cnot, [0, 1], 3).matrix, np.kron(cnot.matrix, np.eye(2)))
        sw = QuantumMathPrimitives.swap().matrix
        flipped = sw @ cnot.matrix @ sw                         # CNOT with control=qubit 1
        ok10 = np.allclose(embed_operator(cnot, [1, 0], 2).matrix, flipped)
        return bool(ok01 and ok10)

    @staticmethod
    def kernel_psd_and_affine_invariance() -> bool:
        rng = np.random.default_rng(11)
        K = QuantumKernel.gram_matrix(rng.normal(size=(12, 5)))
        x = rng.normal(size=6)
        inv = abs(QuantumMath.fidelity(QuantumFeatureState.encode(x),
                                       QuantumFeatureState.encode(3 * x + 10)) - 1) < 1e-9
        return bool(np.linalg.eigvalsh(K).min() > -1e-10 and np.allclose(np.diag(K), 1) and inv)

    @staticmethod
    def bloch_variance_identity() -> bool:
        rng = np.random.default_rng(13)
        for _ in range(50):
            n = int(rng.integers(2, 8))
            p, ph = rng.uniform(0, 1, n), rng.uniform(0, 2 * np.pi, n)
            w = rng.uniform(0.5, 1, n); w /= w.sum()
            r = np.stack([2 * np.sqrt(p * (1 - p)) * np.cos(ph), 2 * np.sqrt(p * (1 - p)) * np.sin(ph), 1 - 2 * p], 1)
            rb = w @ r
            ref = _density_matrix_diagnostics(p, ph, w)
            var = float(sum(wi * (ri - rb) @ (ri - rb) for wi, ri in zip(w, r)))
            q = (1 + np.linalg.norm(rb)) / 2
            h2_ = 0.0 if q >= 1 - 1e-15 else -(q * np.log2(q) + (1 - q) * np.log2(1 - q))
            if not (abs(ref['confidence'] - rb @ rb) < 1e-9 and abs(1 - ref['confidence'] - var) < 1e-9
                    and abs(ref['entropy'] - h2_) < 1e-9):
                return False
        return True

    @staticmethod
    def scheduler_preserves_unitary() -> bool:
        rng = np.random.default_rng(17)
        for _ in range(20):
            n, ir = 3, QuantumIR('t')
            for _g in range(int(rng.integers(4, 10))):
                kind = int(rng.integers(0, 3))
                if kind == 0:
                    ir.add('H', [int(rng.integers(0, n))])
                elif kind == 1:
                    ir.add('RY', [int(rng.integers(0, n))], {'theta': float(rng.uniform(0, 3))})
                else:
                    a, b = rng.choice(n, 2, replace=False).tolist()
                    ir.add('CNOT', [a, b])
            s1 = QuantumStateFactory.from_ir(ir, n).state
            s2 = QuantumStateFactory.from_ir(GateScheduler().compile_ir(ir).to_ir(), n).state
            if not np.allclose(s1.amplitudes, s2.amplitudes, atol=1e-9):
                return False
        return True

    @staticmethod
    def partial_trace_and_ebit() -> bool:
        reg = QuantumRegister(2).apply(QuantumMathPrimitives.ry(0.9), targets=[0])
        rho = PartialTrace.trace_out(reg.state, keep=1)
        p = np.sin(0.45) ** 2
        ref = QuantumState(np.array([np.sqrt(1 - p), np.sqrt(p)])).density_matrix()
        return bool(np.allclose(rho, ref) and abs(MultiQubitMath.entanglement_entropy(MultiQubitMath.bell_pair()) - 1) < 1e-9)

    @staticmethod
    def exact_solver_equals_bruteforce() -> bool:
        rng = np.random.default_rng(19)
        for _ in range(60):
            n, lam = int(rng.integers(2, 11)), float(rng.uniform(-1, 1.5))
            h = rng.uniform(-1, 1, n)
            ex = ExactIsingWeightSolver(lam).solve(h)
            bf, _ = ising_bruteforce(h, lam)
            if abs(ex['energy'] - bf) > 1e-9:
                return False
        return True

    @staticmethod
    def exact_never_worse_than_variational() -> bool:
        rng = np.random.default_rng(23)
        for _ in range(5):
            s = rng.uniform(0, 1, 4)
            h = s - s.mean()
            var = QuantumWeightOptimizer(4, restarts=4).optimize(s)
            ex = ExactIsingWeightSolver(0.3).solve(h)
            if ex['energy'] > var['energy'] + 1e-9:
                return False
        return True

    @staticmethod
    def phase_changes_diagnostics_not_marginals() -> bool:
        a = CalibratedCoherentCommittee.diagnostics(np.array([[0.9, 0.1]]), np.array([0.0, 0.0]))
        b = CalibratedCoherentCommittee.diagnostics(np.array([[0.9, 0.1]]), np.array([0.0, np.pi]))
        return bool(abs(a['pooled_probability'][0] - b['pooled_probability'][0]) < 1e-12
                    and abs(a['entropy'][0] - 0.7219) < 1e-3 and abs(b['entropy'][0] - 1.0) < 1e-9)

    NAMES = ['embedding_matches_kron', 'kernel_psd_and_affine_invariance', 'bloch_variance_identity',
             'scheduler_preserves_unitary', 'partial_trace_and_ebit', 'exact_solver_equals_bruteforce',
             'exact_never_worse_than_variational', 'phase_changes_diagnostics_not_marginals',
             'golden_certificates', 'modular_geodesics_from_lucas',
             'zeckendorf_rank_encoding_is_monotone_invariant']

    @staticmethod
    def golden_certificates() -> bool:
        """Cassini = det(Q^n), Lucas = trace(Q^n), Pisano pi(2^k) = 3*2^(k-1) (vs brute force),
        fold round trip incl. steps far beyond the period, Zeckendorf uniqueness shape, and the
        Fibonacci code as a self-delimiting stream.  All integer; nothing tolerated to epsilon."""
        G = GoldenArithmetic
        rng = np.random.default_rng(89)
        for n in range(0, 300):
            if G.cassini(n) != (1 if n % 2 == 0 else -1):
                return False
        for n in range(0, 60):                                   # exact trace identity
            f_n, f_n1 = G.fib_pair(n)
            if f_n1 + (f_n1 - f_n) != G.lucas(n):
                return False
        for k in range(1, 13):                                   # brute-force Pisano period of 2^k
            m, (a, b), period = 1 << k, (0, 1), None
            for i in range(1, 6 * (1 << k) + 1):
                a, b = b, (a + b) % m
                if (a, b) == (0, 1):
                    period = i
                    break
            if period != G.pisano_pow2(k):
                return False
        for bits in (8, 64, 256):
            big = G.pisano_pow2(bits) * 5 + 7                    # reduction is load-bearing here
            if G.fold_matrix(big, bits)[0] != G.fold_matrix(7, bits)[0]:
                return False
            for _ in range(40):
                w = [int(rng.integers(0, 2**31)) * (int(rng.integers(0, 2**31)) + 1) % (1 << bits)
                     for _ in range(6)]
                st = int(rng.integers(0, 10**6))
                if G.unfold_words(G.fold_words(w, st, bits), st, bits) != w:
                    return False
        for n in list(range(0, 2000)) + [int(rng.integers(0, 10**12)) for _ in range(50)]:
            z = G.zeckendorf(n)
            if G.unzeckendorf(z) != n or any(b2 - a2 < 2 for a2, b2 in zip(z, z[1:])) or any(i < 2 for i in z):
                return False
        values = [0, 1, 7, 99, 4096, 10**6]
        stream = ''.join(G.fib_code(v) for v in values)
        pos, out = 0, []
        while pos < len(stream):
            v, pos = G.fib_decode(stream, pos)
            out.append(v)
        if out != values:
            return False
        for _ in range(25):                                      # gcd morphism: gcd(F(a), F(b)) = F(gcd(a, b))
            a2, b2 = int(rng.integers(1, 300)), int(rng.integers(1, 300))
            if math.gcd(G.fib(a2), G.fib(b2)) != G.fib(math.gcd(a2, b2)):
                return False
        return True

    @staticmethod
    def zeckendorf_rank_encoding_is_monotone_invariant() -> bool:
        """Ranks are invariant under any strictly monotone per-feature map and Zeckendorf is a
        bijection on the ranks, so the encoded states -- and hence the fidelity kernel -- are
        bit-IDENTICAL under x -> x^3, exp, arctan and affine maps applied per feature.  Plain
        amplitude encoding is only affine-invariant: the same transforms move it.  Both facts
        are asserted, and the encoding needs GoldenArithmetic to exist at all."""
        rng = np.random.default_rng(23)
        X = rng.normal(size=(14, 4))
        maps = (lambda col: col ** 3, np.exp, np.arctan, lambda col: 5 * col + 2)
        Y = np.column_stack([maps[j % 4](X[:, j]) for j in range(X.shape[1])])
        A = QuantumFeatureState.encode_ranked_rows(X)
        B = QuantumFeatureState.encode_ranked_rows(Y)
        same = all(np.array_equal(a.amplitudes, b.amplitudes) for a, b in zip(A, B))
        gram = QuantumKernel.gram_matrix  # the kernel this feeds stays PSD on the encoded bits
        K = gram(np.vstack([np.real(st.amplitudes) for st in A]))
        psd = float(np.linalg.eigvalsh(K).min()) > -1e-10
        plain_moves = abs(QuantumMath.fidelity(QuantumFeatureState.encode(X[0]),
                                               QuantumFeatureState.encode(Y[0])) - 1) > 1e-6
        return bool(same and psd and plain_moves)

    @staticmethod
    def modular_geodesics_from_lucas() -> bool:
        """trace(Q^2k) = L(2k) and 2*arccosh(L(2k)/2) = 4k*ln(phi): the closed geodesics of the
        modular surface that the fold's powers trace out, the k=1 case (trace 3, Markov triple
        (1,1,1)) being its SHORTEST closed geodesic, length 4*ln(phi) ~= 1.9248.  NOT 2*ln(phi):
        arccosh(sqrt(5)/2) = ln(phi) is true arithmetic, but no closed geodesic has that length
        here, and the figure-eight knot complement's systole is ~1.0871, not 0.9624 either."""
        phi = (1 + 5 ** 0.5) / 2
        for k in range(1, 7):
            L = GoldenArithmetic.lucas(2 * k)
            if abs(2 * math.acosh(L / 2) - 4 * k * math.log(phi)) > 1e-9:
                return False
        return abs(2 * math.acosh(3 / 2) - 4 * math.log(phi)) < 1e-12

    @classmethod
    def run(cls) -> List[tuple]:
        return [(n, bool(getattr(cls, n)())) for n in cls.NAMES]


def drop_effect(engine: 'UnifiedAnalyticsEngine', frame: pd.DataFrame, column: str, n: int = 200) -> Dict[str, Any]:
    """Perturbation theory:  trace out one subsystem and measure the change in the observable.

    Removing a column forces that dimension into the decoherence channel (NaN → training
    mean = depolarisation along that axis).  The change in predict()'s output IS the
    shift in the POVM expectation value under the partial trace.  Measured over many
    prepared states (rows in cross_sectional mode, windows otherwise) because one state
    cannot distinguish signal from noise.  `flipped` (units that crossed 0.5) is the
    operationally meaningful count: the number of states whose measurement outcome
    changed binary branch under the perturbation."""
    k = max(1, engine.config.chunk_rows)
    units = [frame.iloc[i:i + k] for i in range(0, len(frame) - k + 1, k)][:n]
    base, dropped, comp = [], [], []
    for unit in units:
        base.append(engine.predict(unit)['score'])
        d = engine.predict(unit.drop(columns=[column]))
        dropped.append(d['score']); comp.append(d['gaps']['completeness'])
    b, d_, c = np.array(base), np.array(dropped), np.array(comp)
    delta = np.abs(b - d_)
    rho, ok = _spearman(delta, 1 - c)
    flipped = int(((b >= 0.5) != (d_ >= 0.5)).sum())
    return {'n_units': len(units), 'mean_abs_delta': float(delta.mean()),
            'p90_abs_delta': float(np.percentile(delta, 90)), 'flipped': flipped,
            'flip_rate_ci95': wilson_interval(flipped, len(units)),    # quote the interval, not the point
            'mean_completeness': float(c.mean()), 'spearman_delta_vs_gap': rho, 'spearman_defined': ok}


class RegressionSuite:
    """One test per reviewed defect.  Tests verify the algebra at all three layers:
    operator identity (Layer 1), channel integrity (Layer 2), and spectral certificates (Layer 1↔2)."""

    @staticmethod
    def apply_honors_targets_full_width() -> bool:
        cnot = QuantumMathPrimitives.cnot()
        r = QuantumRegister(2).apply(QuantumMath.pauli_x(), targets=[0])             # |10>
        r.apply(cnot, targets=[1, 0])                                                # control=q1=0 -> no-op
        noop = np.argmax(r.state.probabilities()) == 2
        r.apply(cnot, targets=[0, 1])                                                # control=q0=1 -> |11>
        flip = np.argmax(r.state.probabilities()) == 3
        r2 = QuantumRegister(2).apply(QuantumMath.pauli_x(), targets=[1])            # |01>
        r2.apply(cnot, targets=[1, 0])                                               # control=q1=1 -> |11>
        rev = np.argmax(r2.state.probabilities()) == 3
        return bool(noop and flip and rev)

    @staticmethod
    def spectral_certificate_registry_symmetric() -> bool:
        """Registry files certificates and closures symmetrically; summary includes both."""
        reg = SpectralCertificateRegistry()
        reg.register(SpectralCertificate(
            surface='committee_geometry', kind='DIAGNOSTIC', domain='synthetic',
            protocol='identity', identity='Tr(rho)=1', note='unit trace'))
        reg.record_closure(SpectralGapClosure(
            surface='committee_diagnostics', kind='FALSIFIED', domain='synthetic',
            protocol='T1_rank_correlation', metric='|Spearman|',
            quantum_value=0.12, classical_value=0.35, delta=-0.23,
            classical_baseline='score_std (classical)',
            note='quantum lost to score_std'))
        s = reg.summary()
        has_cert = 'Certified [DIAGNOSTIC]' in s
        has_loss = 'counterevidence' in s and '0.3500' in s
        return bool(has_cert and has_loss and len(reg.certificates) == 1 and len(reg.closures) == 1)

    @staticmethod
    def checkpoint_roundtrip_and_corruption() -> bool:
        import tempfile
        reg = QuantumRegister(3).apply(QuantumMath.hadamard(), targets=[0]).apply(
            QuantumMathPrimitives.cnot(), targets=[0, 2])
        reg.state.labels = [f'b{i}' for i in range(8)]
        path = os.path.join(tempfile.mkdtemp(), 'ck.json')
        StateCheckpoint.save(reg, path)
        back = StateCheckpoint.load(path)
        exact = (np.asarray(back.state.amplitudes) == np.asarray(reg.state.amplitudes)).all()   # BIT-exact, not allclose
        ok = bool(exact) and back.state.labels == reg.state.labels
        blob = json.load(open(path))
        w = int(blob['payload'][:16], 16) ^ 1                       # one low-order bit in one folded word
        blob['payload'] = f'{w:016x}' + blob['payload'][16:]
        json.dump(blob, open(path, 'w'))
        try:
            StateCheckpoint.load(path); raised = False
        except QuantumContractError:
            raised = True
        return bool(ok and raised)

    @staticmethod
    def classical_schema_robustness() -> bool:
        import tempfile
        rng = np.random.default_rng(3)
        df = UnifiedAnalyticsDemo.build_hr_demo(200)
        df['extra'] = rng.normal(5, 1, len(df))
        y = (df['performance_score'] < df['performance_score'].median()).astype(int)
        eng = UnifiedAnalyticsEngine({'model_dir': tempfile.mkdtemp(), 'model_names': ['rf']})
        eng.fit_engine(df, y)
        chunk = df.head(20)
        full = eng._indicator_vector(eng._impute(chunk))
        permuted = eng._indicator_vector(eng._impute(chunk[list(chunk.columns[::-1])]))
        order_ok = np.allclose(full, permuted)                                   # column order irrelevant
        no_extra = chunk.drop(columns=['extra'])
        v = eng._indicator_vector(eng._impute(no_extra))
        j = eng.slot_names.index('numeric_means.extra')
        imputed_ok = (not np.isnan(v).any()) and abs(v[j] - eng.imputer.statistics_[eng.numeric_columns.index('extra')]) < 1e-9
        no_date = chunk.drop(columns=['date'])
        v2 = eng._indicator_vector(eng._impute(no_date))
        k = eng.slot_names.index('trend_metrics.trend')
        slot_ok = v2[k] == eng.feature_fill[k] and not np.isnan(v2).any()          # training mean, not a fake 0
        predict_ok = 0.0 <= eng.predict(no_extra.drop(columns=['date']))['score'] <= 1.0
        return bool(order_ok and imputed_ok and slot_ok and predict_ok)

    @staticmethod
    def summary_has_no_constant_field() -> bool:
        m = QuantumMetrics.summary(MultiQubitMath.bell_pair())
        return 'von_neumann' not in m and 'measurement_entropy' in m

    @staticmethod
    def symbolic_expression_algebra() -> bool:
        e = SymbolicExpression().toggle('X@0').toggle('Z@0').toggle('X@0')
        f = SymbolicExpression(['Z@0', 'Y@1'])
        return bool(e.terms == ['Z@0'] and (e ^ f).terms == ['Y@1'] and 'Z@0' in e
                    and not SymbolicExpression(['a', 'a']) and e.simplify() == e)

    @staticmethod
    def optimizer_is_equivalent_and_stronger() -> bool:
        opt = SymbolicGateOptimizer()
        # commutation-aware: H on q0 cancels across an unrelated gate on q1 (adjacent-only reducer missed this)
        ir = QuantumIR('t').add('H', [0]).add('RY', [1], {'theta': 0.4}).add('H', [0])
        if [i['op'] for i in opt.optimize(ir).instructions] != ['RY']:
            return False
        # exact rotation merge, and exact identity at the true period
        ir = QuantumIR('t').add('RX', [0], {'theta': 0.3}).add('RX', [0], {'theta': 0.4})
        o = opt.optimize(ir).instructions
        if not (len(o) == 1 and abs(o[0]['params']['theta'] - 0.7) < 1e-12):
            return False
        if opt.optimize(QuantumIR('t').add('RZ', [0], {'theta': 2 * np.pi}).add('RZ', [0], {'theta': 2 * np.pi})).instructions:
            return False
        # Pauli frames: X Z Y on q0 collapses to one gate
        ir = QuantumIR('t').add('X', [0]).add('Z', [0]).add('Y', [0])
        if len(opt.optimize(ir).instructions) > 1:
            return False
        # random circuits: optimized == original up to global phase, never longer
        rng = np.random.default_rng(5)
        ops1 = ['H', 'X', 'Y', 'Z', 'RX', 'RY', 'RZ']
        for _ in range(60):
            n, ir = 3, QuantumIR('r')
            for _g in range(int(rng.integers(5, 16))):
                if rng.uniform() < 0.2:
                    a, b = rng.choice(n, 2, replace=False).tolist()
                    ir.add('CNOT', [a, b])
                else:
                    op = ops1[int(rng.integers(len(ops1)))]
                    ir.add(op, [int(rng.integers(n))], {'theta': float(rng.choice([0.0, 0.5, 1.1, np.pi]))}
                           if op.startswith('R') else {})
            a = QuantumStateFactory.from_ir(ir, n).state
            o = opt.optimize(ir)
            b = QuantumStateFactory.from_ir(o, n).state
            if abs(QuantumMath.fidelity(a, b) - 1) > 1e-9 or len(o.instructions) > len(ir.instructions):
                return False
        return True

    @staticmethod
    def spectral_discrimination_baselines() -> bool:
        """SpectralDiscrimination computes coplanar Bloch and Fisher-Rao baselines."""
        rng = np.random.default_rng(42)
        P = rng.uniform(0.1, 0.9, (100, 5))                   # 100 rows, 5 models
        # coplanar baseline: phases=0 restricts to real subalgebra
        cop = SpectralDiscrimination.phase_stripped_bloch(P)
        conf_ok = cop['confidence_coplanar'].shape == (100,)
        # Fisher-Rao / Mahalanobis: one distance per row, always non-negative
        mahal = SpectralDiscrimination.fisher_rao_mahalanobis(P)
        mahal_ok = mahal.shape == (100,) and (mahal >= -1e-9).all()
        # T1 rank correlation: produces rho for each measure
        true_p = rng.uniform(0.2, 0.8, 100)
        phases = rng.uniform(-np.pi, np.pi, 5)
        t1 = SpectralDiscrimination.rank_correlation_protocol(P, true_p, phases)
        t1_ok = 'strongest_classical' in t1 and len(t1['spearman_vs_error']) == 4
        # T2 capture rate: at 10% budget
        t2 = SpectralDiscrimination.capture_rate_protocol(P, true_p, phases, 0.1)
        t2_ok = all(0 <= v <= 1 for v in t2['captures'].values()) and t2['k'] == 10
        return bool(conf_ok and mahal_ok and t1_ok and t2_ok)

    @staticmethod
    def text_signal_is_live() -> bool:
        import tempfile
        d = tempfile.mkdtemp()
        df = UnifiedAnalyticsDemo.build_hr_demo(200)
        y = (df['performance_score'] < df['performance_score'].median()).astype(int)
        eng = UnifiedAnalyticsEngine({'model_dir': d, 'model_names': ['rf']}).fit_engine(df, y)
        if eng.text_weights is None or 'text_signal.topic_axis' not in eng.slot_names:
            return False
        i = eng.slot_names.index('text_signal.topic_axis')
        a = df.head(20).assign(survey_text='stressed want leave')
        b = df.head(20).assign(survey_text='great place engaged')
        va, vb = eng._indicator_vector(a)[i], eng._indicator_vector(b)[i]
        varies = abs(va - vb) > 1e-6 and eng._train_matrix[:, i].std() > 0
        again = UnifiedAnalyticsEngine({'model_dir': d, 'model_names': ['rf']})          # persistence round trip
        persisted = again.is_fitted and np.isclose(again._indicator_vector(a)[i], va)
        no_text = eng._indicator_vector(df.head(20).drop(columns=['survey_text']))
        return bool(varies and persisted and not np.isnan(no_text).any())

    @staticmethod
    def orchestrator_wiring() -> bool:
        import tempfile
        d = tempfile.mkdtemp()
        orch = UnifiedAnalyticsOrchestrator(
            UnifiedAnalyticsEngine({'model_dir': d, 'model_names': ['rf']}), sector='hr')
        df = UnifiedAnalyticsDemo.build_hr_demo(200)
        y = (df['performance_score'] < df['performance_score'].median()).astype(int)
        orch.fit(df, y)
        orch.predict(df.head(20).drop(columns=['survey_text']))                 # missing a sector signal
        mon = orch.monitor.summary()
        manifest = json.load(open(os.path.join(d, 'manifest.json')))
        flagged = any(e.get('missing_signals') for e in orch.audit_log if e['event'] == 'validate_contract')
        return bool({'fit_seconds', 'predict_seconds'} <= set(mon['metric']) and flagged
                    and manifest['sector'] == 'hr' and manifest['text_signal_active']
                    and 'text_signal.topic_axis' in manifest['slot_names'])

    @staticmethod
    def feature_dim_respected_and_custom_guarded() -> bool:
        import tempfile
        d = tempfile.mkdtemp()
        r = np.random.default_rng(1)
        df = UnifiedAnalyticsDemo.build_hr_demo(200)
        for i in range(8):
            df[f'col{i}'] = r.normal(size=len(df))
        y = (df['performance_score'] < df['performance_score'].median()).astype(int)
        eng = UnifiedAnalyticsEngine({'model_dir': d, 'model_names': ['rf'], 'feature_dim': 10})
        for n in ('f_a', 'f_b', 'f_c'):
            eng.add_feature_engineering(n, lambda frame, n=n: float(frame['col0'].mean()))
        eng.fit_engine(df, y)
        within = len(eng.slot_names) <= 10 and sum(n.startswith('custom.') for n in eng.slot_names) == 3
        try:
            eng.add_feature_engineering('late', lambda frame: 0.0); late_blocked = False
        except RuntimeError:
            late_blocked = True
        again = UnifiedAnalyticsEngine({'model_dir': d, 'model_names': ['rf']})
        try:
            again.predict(df.head(20)); unregistered_caught = False
        except RuntimeError:
            unregistered_caught = True
        for n in ('f_a', 'f_b', 'f_c'):                                   # re-registering saved names is allowed
            again.add_feature_engineering(n, lambda frame: float(frame['col0'].mean()))
        return bool(within and late_blocked and unregistered_caught
                    and 0.0 <= again.predict(df.head(20))['score'] <= 1.0)

    @staticmethod
    def inconsistent_artifacts_raise() -> bool:
        import tempfile
        d = tempfile.mkdtemp()
        df = UnifiedAnalyticsDemo.build_hr_demo(120)
        y = (df['performance_score'] < df['performance_score'].median()).astype(int)
        UnifiedAnalyticsEngine({'model_dir': d, 'model_names': ['rf']}).fit_engine(df, y)
        bad = StandardScaler().fit(np.random.default_rng(0).normal(size=(10, 3)))
        joblib.dump(bad, os.path.join(d, 'scaler.joblib'))
        try:
            UnifiedAnalyticsEngine({'model_dir': d, 'model_names': ['rf']}); return False
        except ValueError as e:
            return 'refit' in str(e)

    @staticmethod
    def benchmark_survives_missing_selected_model() -> bool:
        import tempfile
        df = UnifiedAnalyticsDemo.build_hr_demo(200)
        y = (df['performance_score'] < df['performance_score'].median()).astype(int)
        eng = UnifiedAnalyticsEngine({'model_dir': tempfile.mkdtemp(), 'model_names': ['rf', 'gb'],
                                      'selected_model': 'not_installed'}).fit_engine(df, y)
        out = eng.benchmark(df, y)
        return bool(out['model'] in ('rf', 'gb') and 0.0 <= out['accuracy'] <= 1.0)

    @staticmethod
    def single_authoritative_score() -> bool:
        import tempfile
        df = UnifiedAnalyticsDemo.build_hr_demo(200)
        y = (df['performance_score'] < df['performance_score'].median()).astype(int)
        orch = UnifiedAnalyticsOrchestrator(
            UnifiedAnalyticsEngine({'model_dir': tempfile.mkdtemp(), 'model_names': ['rf', 'gb']}))
        q = QuantumUnifiedEngine(orch).fit(df, y)
        res = q.predict(df.head(20), use_optimized_weights=True)
        mean = float(np.mean([m['score'] for m in res['models'].values()]))
        return bool(abs(res['score'] - res['decision']['probability']) < 1e-12
                    and abs(res['unweighted_score'] - mean) < 1e-12)

    @staticmethod
    def spearman_constant_guard() -> bool:
        rho, ok = _spearman(np.ones(10), np.arange(10.0))
        rho2, ok2 = _spearman(np.arange(10.0), np.arange(10.0))
        return bool(rho == 0.0 and not ok and ok2 and abs(rho2 - 1) < 1e-12)

    @staticmethod
    def absent_slots_are_reported() -> bool:
        import tempfile
        df = UnifiedAnalyticsDemo.build_hr_demo(200)
        y = (df['performance_score'] < df['performance_score'].median()).astype(int)
        eng = UnifiedAnalyticsEngine({'model_dir': tempfile.mkdtemp(), 'model_names': ['rf']})
        eng.add_feature_engineering('ghost', lambda frame: np.nan)            # never observable
        eng.fit_engine(df, y)
        return bool(eng.absent_slots == ['custom.ghost'] and 'custom.ghost' in eng.predict(df.head(10))['gaps']['absent_at_fit'])

    @staticmethod
    def layout_is_derived_from_the_frame() -> bool:
        import tempfile
        df = UnifiedAnalyticsDemo.build_fintech_demo(200)                     # no performance/date columns
        y = (df['device_risk'] > 0.5).astype(int)
        eng = UnifiedAnalyticsEngine({'model_dir': tempfile.mkdtemp(), 'model_names': ['rf'], 'chunk_rows': 5}).fit_engine(df, y)
        no_hr_ghosts = not any(n.startswith(('performance_metrics', 'trend_metrics')) for n in eng.slot_names)
        every_column = all(f'numeric_means.{c}' in eng.slot_names for c in
                           ('transaction_velocity', 'ip_geolocation', 'device_risk', 'session_anomaly'))
        return bool(no_hr_ghosts and every_column and not eng.absent_slots)

    @staticmethod
    def _planted_frame(k: int, rows: int, seed: int):
        r = np.random.default_rng(seed)
        z = np.repeat(r.normal(size=rows // 10), 10)
        a = r.normal(0.6, 0.2, k)
        X = z[:, None] * a[None, :] + r.normal(size=(rows, k))
        return pd.DataFrame(X, columns=[f'c{i}' for i in range(k)]), pd.Series((z > 0).astype(int))

    @staticmethod
    def universality_across_widths() -> bool:
        import tempfile
        for k in (40, 400):
            df, y = RegressionSuite._planted_frame(k, 700, seed=k)
            tr, ytr, te, yte = df.head(500), y.head(500), df.tail(200).reset_index(drop=True), y.tail(200).reset_index(drop=True)
            eng = UnifiedAnalyticsEngine({'model_dir': tempfile.mkdtemp(), 'model_names': ['rf']}).fit_engine(tr, ytr)
            if not (len(eng.slot_names) == k and not eng.absent_slots and eng.wide_vs_chunks == (k > 50)):
                return False
            chunk = te.head(10)
            if not np.allclose(eng._indicator_vector(eng._impute(chunk)),
                               eng._indicator_vector(eng._impute(chunk[list(chunk.columns[::-1])]))):
                return False
            drop = ['c3', 'c7', 'c11']
            res = eng.predict(chunk.drop(columns=drop))
            if set(res['gaps']['imputed_columns']) != set(drop) or not 0 <= res['score'] <= 1:
                return False
            clean = eng.predict(chunk)['gaps']['completeness']
            if clean != 1.0 or abs(res['gaps']['completeness'] - (1 - 3 / k)) > 1e-9:
                return False
            if eng.benchmark(te, yte)['accuracy'] < 0.8:
                return False
        return True

    @staticmethod
    def _beats_baseline(bench: Dict[str, Any], y_test) -> bool:
        """Honest accuracy check: the 95% interval must clear the majority-class rate."""
        yt = np.asarray(y_test).astype(int)
        return bench['ci95'][0] > max(yt.mean(), 1 - yt.mean())

    @staticmethod
    def cross_sectional_is_a_named_profile_setting() -> bool:
        import tempfile
        prof = SectorProfiles.by_name('fintech')
        df, y = UnifiedAnalyticsDemo.build_fintech_demo(500, labeled=True)
        eng = UnifiedAnalyticsEngine({'model_dir': tempfile.mkdtemp(), 'model_names': ['rf']}, profile=prof)
        eng.fit_engine(df.head(350), y.head(350))
        each = eng.predict_each(df.tail(40))
        b = eng.benchmark(df.tail(150), y.tail(150))
        return bool(prof.mode == 'cross_sectional' and eng.config.chunk_rows == 1 and len(each) == 40
                    and RegressionSuite._beats_baseline(b, y.tail(150)))

    @staticmethod
    def audit_matches_decision() -> bool:
        import tempfile
        df, y = UnifiedAnalyticsDemo.build_fintech_demo(400, labeled=True)
        orch = UnifiedAnalyticsOrchestrator(
            UnifiedAnalyticsEngine({'model_dir': tempfile.mkdtemp(), 'model_names': ['rf', 'gb'], 'chunk_rows': 1}))
        q = QuantumUnifiedEngine(orch).fit(df.head(300), y.head(300))
        for i in range(300, 340):                       # find a row where the two models disagree
            res = q.predict(df.iloc[[i]], weights={'rf': 1.0, 'gb': 0.0})
            sc = [m['score'] for m in res['models'].values()]
            if abs(sc[0] - sc[1]) > 1e-3:
                break
        else:
            return False
        mon = orch.monitor.summary()
        last = lambda m: float(mon[mon['metric'] == m]['value'].iloc[-1])
        return bool(abs(last('predict_score_pooled') - res['score']) < 1e-12
                    and abs(last('predict_score_classical') - res['unweighted_score']) < 1e-12
                    and abs(res['score'] - res['unweighted_score']) > 1e-4         # the two numbers really differ
                    and 'predict_score' not in set(mon['metric']))

    @staticmethod
    def single_model_confidence_is_undefined() -> bool:
        one = QuantumEnsemble.mix({'rf': 0.5})
        two = QuantumEnsemble.mix({'a': 0.5, 'b': 0.5})
        split = QuantumEnsemble.mix({'a': 0.0, 'b': 1.0})
        return bool(one['confidence'] is None and one['model_disagreement_entropy'] is None
                    and not one['confidence_defined'] and one['n_models'] == 1
                    and two['confidence_defined'] and two['confidence'] > 0.99
                    and split['confidence_defined'] and split['confidence'] == 0.0)     # 0.0 is a real value

    @staticmethod
    def cross_sectional_ranking_is_scale_free() -> bool:
        import tempfile
        r = np.random.default_rng(4)
        y = pd.Series(r.integers(0, 2, 400))
        base = pd.DataFrame({'aa_noise': r.normal(size=400), 'bb_noise': r.normal(size=400),
                             'zz_signal': y.to_numpy() * 1.5 + r.normal(size=400)})   # last by NAME, first by signal
        kept = []
        for scale in (1.0, 1e-3, 1e3):
            df = base.assign(zz_signal=base.zz_signal * scale, aa_noise=base.aa_noise / scale)
            eng = UnifiedAnalyticsEngine({'model_dir': tempfile.mkdtemp(), 'model_names': ['rf'],
                                          'chunk_rows': 1, 'feature_dim': 1}).fit_engine(df, y)
            kept.append(tuple(eng.slot_names))
        return bool(all(k == ('numeric_means.zz_signal',) for k in kept))

    @staticmethod
    def feature_dim_headroom_is_warned() -> bool:
        import tempfile
        seen: List[str] = []

        class _H(logging.Handler):
            def emit(self, record): seen.append(record.getMessage())
        h = _H(); log.addHandler(h); _lvl, _prop = log.level, log.propagate; log.setLevel(logging.WARNING); log.propagate = False   # independent of host logging config; don't echo
        try:
            df = UnifiedAnalyticsDemo.build_hr_demo(200); df['extra'] = np.arange(200.0)
            y = (df['performance_score'] < df['performance_score'].median()).astype(int)
            eng = UnifiedAnalyticsEngine({'model_dir': tempfile.mkdtemp(), 'model_names': ['rf'], 'feature_dim': 2})
            eng.fit_engine(df, y)
        finally:
            log.removeHandler(h); log.setLevel(_lvl); log.propagate = _prop
        return bool(any('leaves no room' in m for m in seen) and len(eng.slot_names) > 2)

    @staticmethod
    def predict_each_keeps_gap_register() -> bool:
        import tempfile
        df, y = UnifiedAnalyticsDemo.build_fintech_demo(400, labeled=True)
        eng = UnifiedAnalyticsEngine({'model_dir': tempfile.mkdtemp(), 'model_names': ['rf']},
                                     profile=SectorProfiles.by_name('fintech')).fit_engine(df.head(300), y.head(300))
        frame = df.tail(20).drop(columns=['device_risk'])
        each = eng.predict_each(frame)
        one = eng.predict(frame.iloc[[3]])
        return bool({'completeness', 'imputed', 'affected'} <= set(each.columns)
                    and (each['imputed'] == 'device_risk').all() and (each['completeness'] < 1).all()
                    and abs(each['score'].iloc[3] - one['score']) < 1e-12)

    @staticmethod
    def undeclared_inputs_reported_only_when_affected() -> bool:
        import tempfile
        df, y = UnifiedAnalyticsDemo.build_fintech_demo(300, labeled=True)
        eng = UnifiedAnalyticsEngine({'model_dir': tempfile.mkdtemp(), 'model_names': ['rf'], 'chunk_rows': 1})
        eng.add_feature_engineering('opaque', lambda f: float(f['device_risk'].mean()) if 'device_risk' in f.columns else np.nan)
        eng.fit_engine(df.head(220), y.head(220))
        clean = eng.predict(df.tail(1))['gaps']
        hit = eng.predict(df.tail(1).drop(columns=['device_risk']))['gaps']
        return bool(clean['undeclared_inputs'] == [] and hit['undeclared_inputs'] == ['custom.opaque']
                    and 'custom.opaque' in hit['affected_slots'])

    @staticmethod
    def spectral_registry_ingests_protocol() -> bool:
        """Registry auto-ingests a T1 result into the correct book (certificate or closure)."""
        # Fabricate a result where quantum wins
        result_win = {'spearman_vs_error': {
            'score_std (classical)': 0.30,
            'coplanar_bloch (classical)': 0.25,
            '1-C_calibrated (quantum)': 0.55}}
        reg = SpectralCertificateRegistry()
        reg.ingest_protocol_result(result_win, domain='test_win')
        win_ok = len(reg.certificates) == 1 and len(reg.closures) == 0
        # Fabricate a result where quantum loses
        result_lose = {'spearman_vs_error': {
            'score_std (classical)': 0.60,
            'coplanar_bloch (classical)': 0.45,
            '1-C_calibrated (quantum)': 0.20}}
        reg.ingest_protocol_result(result_lose, domain='test_lose')
        lose_ok = len(reg.certificates) == 1 and len(reg.closures) == 1
        summary = reg.summary()
        both_ok = 'Certified [MEASURED]' in summary and 'counterevidence' in summary
        return bool(win_ok and lose_ok and both_ok)

    @staticmethod
    def demo_frames_do_not_depend_on_labeled_flag() -> bool:
        for b in (UnifiedAnalyticsDemo.build_supply_chain_demo, UnifiedAnalyticsDemo.build_fintech_demo):
            lab = b(200, seed=3, labeled=True)[0]
            if not lab.equals(b(200, seed=3, labeled=False)):
                return False
        return True

    @staticmethod
    def _mnar_frame(n: int, seed: int):
        r = np.random.default_rng(seed)
        x1, x2, risk = r.normal(size=n), r.normal(size=n), r.normal(size=n)
        missing = r.random(n) < 0.25                      # unknown device
        y = ((x1 + 0.5 * x2 + 0.5 * risk + 1.8 * missing + 0.7 * r.normal(size=n)) > 1.0).astype(int)
        return pd.DataFrame({'x1': x1, 'x2': x2, 'device_risk': np.where(missing, np.nan, risk)}), pd.Series(y), missing

    @staticmethod
    def absence_signal_recovers_mnar() -> bool:
        """Under MNAR a linear model cannot see "missing" once the value is median-filled;
        the absence slot restores it. Tree models can already split on the fill constant, so
        the flag is redundant for them (measured: no consistent gain) -- hence 'lr' here, and
        a margin on accuracy over the rows where the column was missing, averaged over seeds."""
        import tempfile
        gains = []
        for seed in (11, 12, 13):
            df, y, miss = RegressionSuite._mnar_frame(4000, seed)
            tr, te = slice(0, 3000), slice(3000, 4000)
            accs = {}
            for tag, absence in (('with', ('device_risk',)), ('without', ())):
                prof = DomainProfile(f'mnar_{tag}', mode='cross_sectional', informative_absence=absence)
                eng = UnifiedAnalyticsEngine({'model_dir': tempfile.mkdtemp(), 'model_names': ['lr']}, profile=prof)
                eng.fit_engine(df.iloc[tr], y.iloc[tr])
                held, yh, mh = df.iloc[te].reset_index(drop=True), y.iloc[te].reset_index(drop=True), miss[te]
                p = eng.predict_each(held)['score'].to_numpy() >= 0.5
                accs[tag] = float((p[mh] == yh.to_numpy()[mh]).mean())
            gains.append(accs['with'] - accs['without'])
        return bool(min(gains) > 0.10)

    @staticmethod
    def absence_flag_tracks_the_input() -> bool:
        import tempfile
        df, y, _ = RegressionSuite._mnar_frame(1500, 5)
        prof = DomainProfile('mnar_flag', mode='cross_sectional', informative_absence=('device_risk',))
        eng = UnifiedAnalyticsEngine({'model_dir': tempfile.mkdtemp(), 'model_names': ['rf']}, profile=prof).fit_engine(df, y)
        row = df.dropna().iloc[[0]]
        present = eng.predict(row)
        gone = eng.predict(row.drop(columns=['device_risk']))
        nan_val = eng.predict(row.assign(device_risk=np.nan))
        reloaded = UnifiedAnalyticsEngine({'model_dir': eng.config.model_dir, 'model_names': ['rf']})
        return bool('absent.device_risk' in eng.slot_names
                    and present['indicators']['absent']['device_risk'] == 0.0
                    and gone['indicators']['absent']['device_risk'] == 1.0
                    and nan_val['indicators']['absent']['device_risk'] == 1.0
                    and 'absent.device_risk' in gone['gaps']['affected_slots']
                    and 'absent.device_risk' not in present['gaps']['affected_slots']
                    and reloaded.absence_columns == ['device_risk']
                    and reloaded.predict(row.drop(columns=['device_risk']))['indicators']['absent']['device_risk'] == 1.0)

    @staticmethod
    def no_discarded_string_literals() -> bool:
        """A string that follows another statement in a function body is a discarded expression, not a docstring
        (`__doc__` is None).  The assert scan cannot see this; this one can."""
        import ast
        tree = ast.parse(open(__file__).read())
        bad = [f'{n.name}@{b.lineno}' for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               for b in n.body[1:] if isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant)
               and isinstance(b.value.value, str)]
        return not bad

    @staticmethod
    def indicator_vector_preps_raw_frames() -> bool:
        import tempfile
        df, y, _ = RegressionSuite._mnar_frame(1200, 7)
        prof = DomainProfile('mnar_raw', mode='cross_sectional', informative_absence=('device_risk',))
        eng = UnifiedAnalyticsEngine({'model_dir': tempfile.mkdtemp(), 'model_names': ['rf']}, profile=prof).fit_engine(df, y)
        i = eng.slot_names.index('absent.device_risk')
        row = df.dropna().iloc[[0]]
        return bool(eng._indicator_vector(row)[i] == 0.0
                    and eng._indicator_vector(row.drop(columns=['device_risk']))[i] == 1.0
                    and eng._indicator_vector(row.assign(device_risk=np.nan))[i] == 1.0)

    @staticmethod
    def reload_then_refit_keeps_absence() -> bool:
        import tempfile
        df, y, _ = RegressionSuite._mnar_frame(1200, 9)
        d = tempfile.mkdtemp()
        prof = DomainProfile('mnar_reload', mode='cross_sectional', informative_absence=('device_risk',))
        UnifiedAnalyticsEngine({'model_dir': d, 'model_names': ['rf']}, profile=prof).fit_engine(df, y)
        again = UnifiedAnalyticsEngine({'model_dir': d, 'model_names': ['rf']})          # profile is gone
        loaded = again.absence_columns == ['device_risk']
        again.fit_engine(df, y)                                                          # refit must not erase it
        return bool(loaded and again.absence_columns == ['device_risk'] and 'absent.device_risk' in again.slot_names
                    and again.predict(df.head(1).drop(columns=['device_risk']))['gaps']['absence_captured'] == ['device_risk'])

    @staticmethod
    def absence_is_in_the_gap_register() -> bool:
        import tempfile
        df, y, _ = RegressionSuite._mnar_frame(1200, 3)
        prof = DomainProfile('mnar_gap', mode='cross_sectional', informative_absence=('device_risk',))
        eng = UnifiedAnalyticsEngine({'model_dir': tempfile.mkdtemp(), 'model_names': ['rf']}, profile=prof).fit_engine(df, y)
        row = df.dropna().iloc[[0]]
        return bool(eng.predict(row)['gaps']['absence_captured'] == []
                    and eng.predict(row.drop(columns=['device_risk']))['gaps']['absence_captured'] == ['device_risk'])

    @staticmethod
    def constant_slot_invariant() -> bool:
        """Engine-induced constancy (inputs vary, slot does not) is a contract error; data-induced constancy
        (the input itself is constant) is recorded and warned, never raised."""
        import tempfile
        r = np.random.default_rng(4)
        df = pd.DataFrame({'a': r.normal(size=300), 'b': r.normal(size=300), 'flat': np.full(300, 5.0)})
        y = pd.Series((df['a'] + 0.3 * r.normal(size=300) > 0).astype(int))
        cfg = lambda: {'model_dir': tempfile.mkdtemp(), 'model_names': ['rf'], 'chunk_rows': 1}
        ok = UnifiedAnalyticsEngine(cfg()).fit_engine(df, y)
        data_induced = ok.constant_slots == ['numeric_means.flat']
        eng = UnifiedAnalyticsEngine(cfg())
        eng.add_feature_engineering('broken', lambda d: 1.0, inputs=('a',))
        try:
            eng.fit_engine(df, y); raised = False
        except DataContractError:
            raised = True
        return bool(data_induced and raised)

    @staticmethod
    def checkpoint_requires_golden_arithmetic() -> bool:
        """The fold is wired, not exhibited: the stored payload is not the raw amplitude bytes,
        the header only parses by Fibonacci decoding, and if GoldenArithmetic goes away the
        checkpoint cannot load.  Legacy 'state' blobs still load."""
        import tempfile
        reg = QuantumRegister(2).apply(QuantumMath.hadamard(), targets=[0])
        path = os.path.join(tempfile.mkdtemp(), 'ck.json')
        StateCheckpoint.save(reg, path)
        blob = json.load(open(path))
        raw = np.ascontiguousarray(reg.state.amplitudes, dtype=np.complex128).tobytes()
        not_raw = 'state' not in blob and blob['payload'] != raw.hex()
        steps, pos = GoldenArithmetic.fib_decode(blob['golden_header'])
        bits, _ = GoldenArithmetic.fib_decode(blob['golden_header'], pos)
        header_parses = steps == StateCheckpoint.FOLD_STEPS and bits == 64
        original = GoldenArithmetic.unfold_words
        GoldenArithmetic.unfold_words = classmethod(lambda cls, *a, **k: (_ for _ in ()).throw(
            GoldenIntegrityError('golden removed')))
        try:
            StateCheckpoint.load(path)
            broke = False
        except (GoldenIntegrityError, QuantumContractError):
            broke = True
        finally:
            GoldenArithmetic.unfold_words = original
        restored = (np.asarray(StateCheckpoint.load(path).state.amplitudes)
                    == np.asarray(reg.state.amplitudes)).all()
        legacy = {'qubits': 1, 'dim': 2, 'state': [[1.0, 0.0], [0.0, 0.0]],
                  'noise': {'t1': None, 't2': None, 'gate_error': 0.0},
                  'depth': 0, 'operations': [], 'labels': ['0', '1']}
        lp = os.path.join(tempfile.mkdtemp(), 'legacy.json')
        json.dump(legacy, open(lp, 'w'))
        legacy_ok = np.allclose(StateCheckpoint.load(lp).state.amplitudes, [1.0, 0.0])
        return bool(not_raw and header_parses and broke and restored and legacy_ok)

    @staticmethod
    def fold_diffusion_detects_low_order_tampering() -> bool:
        """Tamper detection, measured.  Flip ONE of the 4 lowest mantissa bits of one stored
        word.  Raw float bytes: the norm moves ~1e-16 and nothing fires (0/100 here).  Folded
        payload: the header's word sum breaks deterministically for any single-word edit
        (100/100), and the sum is checked BEFORE anything unfolds.  The sum is a detector of
        edits, not a MAC -- a compensating multi-word edit can preserve it -- and losslessness
        never rests on it: that is the determinant's job."""
        import tempfile
        rng = np.random.default_rng(97)
        reg = QuantumRegister(3).apply(QuantumMath.hadamard(), targets=[0]).apply(
            QuantumMath.hadamard(), targets=[1])
        path = os.path.join(tempfile.mkdtemp(), 'ck.json')
        StateCheckpoint.save(reg, path)
        clean = json.load(open(path))
        n_words = len(clean['payload']) // 16
        amps = np.ascontiguousarray(reg.state.amplitudes, dtype=np.complex128)
        caught_folded = caught_raw = trials = 0
        for _ in range(100):
            i, b = int(rng.integers(0, n_words)), int(rng.integers(0, 4))
            w = int(clean['payload'][i * 16:(i + 1) * 16], 16) ^ (1 << b)
            blob = dict(clean)
            blob['payload'] = clean['payload'][:i * 16] + f'{w:016x}' + clean['payload'][(i + 1) * 16:]
            json.dump(blob, open(path, 'w'))
            try:
                StateCheckpoint.load(path)
            except QuantumContractError:
                caught_folded += 1
            raw = bytearray(amps.tobytes())                      # same flip on UNfolded float bytes
            raw[i * 8 + b // 8] ^= (1 << (b % 8))
            tampered = np.frombuffer(bytes(raw), dtype=np.complex128)
            norm = float(np.linalg.norm(tampered))
            if not np.isfinite(norm) or abs(norm - 1.0) > 1e-6:
                caught_raw += 1
            trials += 1
        return bool(caught_folded == trials and caught_raw <= trials // 20)

    @staticmethod
    def rank_needs_enough_samples() -> bool:
        import tempfile
        seen: List[str] = []

        class _H(logging.Handler):
            def emit(self, record): seen.append(record.getMessage())
        r = np.random.default_rng(2)
        y = pd.Series(r.integers(0, 2, 15))                                   # 15 < MIN_RANK_SAMPLES
        df = pd.DataFrame({'aa': r.normal(size=15), 'zz': y.to_numpy() * 3.0 + r.normal(size=15)})
        h = _H(); log.addHandler(h); _lvl, _prop = log.level, log.propagate; log.setLevel(logging.WARNING); log.propagate = False   # independent of host logging config; don't echo
        try:
            eng = UnifiedAnalyticsEngine({'model_dir': tempfile.mkdtemp(), 'model_names': ['rf'],
                                          'chunk_rows': 1, 'feature_dim': 1}).fit_engine(df, y)
        finally:
            log.removeHandler(h); log.setLevel(_lvl); log.propagate = _prop
        return bool(eng.slot_names == ['numeric_means.aa'] and any('rank statistic would be noise' in m for m in seen))

    @staticmethod
    def rank_ties_do_not_depend_on_units() -> bool:
        import tempfile
        r = np.random.default_rng(8)
        y = pd.Series(r.integers(0, 2, 300))
        base = pd.DataFrame({f'n{i}': r.normal(size=300) for i in range(8)})   # all noise: every |rho| is a near-tie
        kept = set()
        for scales in (np.ones(8), 10.0 ** np.arange(-4, 4), 10.0 ** np.arange(3, -5, -1)):
            df = base * scales
            eng = UnifiedAnalyticsEngine({'model_dir': tempfile.mkdtemp(), 'model_names': ['rf'],
                                          'chunk_rows': 1, 'feature_dim': 3}).fit_engine(df, y)
            kept.add(tuple(eng.slot_names))
        return len(kept) == 1

    @staticmethod
    def drop_effect_counts_flips() -> bool:
        import tempfile
        df, y = UnifiedAnalyticsDemo.build_fintech_demo(1200, labeled=True)
        eng = UnifiedAnalyticsEngine({'model_dir': tempfile.mkdtemp(), 'model_names': ['rf']},
                                     profile=SectorProfiles.by_name('fintech')).fit_engine(df.head(900), y.head(900))
        d = drop_effect(eng, df.tail(300).reset_index(drop=True), 'device_risk', n=120)
        return bool(d['n_units'] == 120 and 0 <= d['flipped'] <= 120 and d['mean_abs_delta'] > 0
                    and d['p90_abs_delta'] >= d['mean_abs_delta'] and d['mean_completeness'] < 1)

    @staticmethod
    def no_bare_asserts_in_library_code() -> bool:
        """Library code must not rely on `assert` (stripped under -O).  Scope: this module only (test files are
        separate modules), `__main__` demo blocks and *Suite test classes are exempt, and a deliberate
        precondition assert must be listed in ALLOWED_ASSERTS by its qualified name."""
        import ast
        tree = ast.parse(open(__file__).read())
        bad = []
        for node in tree.body:
            if isinstance(node, ast.If) or (isinstance(node, ast.ClassDef) and node.name.endswith('Suite')):
                continue
            scopes = [(node.name, node)] if isinstance(node, ast.FunctionDef) else (
                [(f'{node.name}.{m.name}', m) for m in node.body if isinstance(m, ast.FunctionDef)]
                if isinstance(node, ast.ClassDef) else [])
            for qual, fn in scopes:
                if qual not in ALLOWED_ASSERTS and any(isinstance(n, ast.Assert) for n in ast.walk(fn)):
                    bad.append(qual)
        return not bad

    @staticmethod
    def registry_and_blueprint_agree() -> bool:
        reg = set(DomainRegistry.names())
        planned = {x.lower().replace(' ', '_') for x in SystemBlueprint.planned_sectors}
        try:
            DomainRegistry.by_name('retail'); raised = False
        except DataContractError:
            raised = True
        return bool(reg.isdisjoint(planned) and raised and {'hr', 'fintech', 'supply_chain'} <= reg
                    and not ExplainabilityHub(UnifiedAnalyticsEngine({'model_dir': __import__('tempfile').mkdtemp(),
                                                                       'model_names': ['rf']})).shap_ready()['implemented'])

    @staticmethod
    def new_domain_is_data_not_code() -> bool:
        r = np.random.default_rng(0)
        df = pd.DataFrame({'basket_value': r.random(300) * 100, 'returns': r.integers(0, 3, 300)})
        y = ((df['basket_value'] > 50) & (df['returns'] > 0)).astype(int)
        prof = DomainProfile('retail_test', 'returns risk', required_columns=('basket_value',),
                             primary_signals=('basket_value', 'returns'), mode='cross_sectional',
                             extractors={'return_rate': lambda f: float((f['returns'] > 0).mean()) if 'returns' in f.columns else np.nan})
        SectorProfiles.register(prof, replace_existing=True)
        try:
            sess = UnifiedAnalyticsSession()
            sess.open('retail_test', model_names=['rf'])
            sess.fit('retail_test', df.head(250), y.head(250))
            dec = sess.decide('retail_test', df.tail(1))
            try:
                sess.fit('retail_test', df.drop(columns=['basket_value']), y); contract = False
            except DataContractError:
                contract = True
            bad = DomainProfile('w', required_columns=(), expected_width=99)
            try:
                UnifiedAnalyticsEngine({'model_dir': tempfile.mkdtemp(), 'model_names': ['rf']}, profile=bad).fit_engine(df, y)
                width_contract = False
            except DataContractError:
                width_contract = True
            return bool(0 <= dec['decision']['probability'] <= 1 and contract and width_contract
                        and 'retail_test' in SectorProfiles.names())
        finally:
            SectorProfiles._REGISTRY.pop('retail_test', None)

    @staticmethod
    def two_domains_one_session() -> bool:
        sess = UnifiedAnalyticsSession()
        layouts, modes = [], []
        for dom, (df, y) in (('fintech', UnifiedAnalyticsDemo.build_fintech_demo(1200, labeled=True)),
                             ('supply_chain', UnifiedAnalyticsDemo.build_supply_chain_demo(2000, labeled=True))):
            cut = int(len(df) * 0.7)
            sess.open(dom, model_names=['rf', 'gb']).fit(df.head(cut), y.head(cut))
            te, yte = df.tail(len(df) - cut).reset_index(drop=True), y.tail(len(df) - cut).reset_index(drop=True)
            if not RegressionSuite._beats_baseline(sess.engine(dom).benchmark(te, yte), yte):
                return False
            layouts.append(tuple(sess.engine(dom).slot_names)); modes.append(sess.gap_register(dom)['mode'])
        return bool(layouts[0] != layouts[1] and modes[0] != modes[1])

    NAMES = ['apply_honors_targets_full_width', 'spectral_certificate_registry_symmetric',
             'checkpoint_roundtrip_and_corruption',
             'classical_schema_robustness', 'summary_has_no_constant_field',
             'symbolic_expression_algebra', 'optimizer_is_equivalent_and_stronger',
             'spectral_discrimination_baselines', 'text_signal_is_live', 'orchestrator_wiring',
             'feature_dim_respected_and_custom_guarded', 'inconsistent_artifacts_raise',
             'benchmark_survives_missing_selected_model', 'single_authoritative_score',
             'spearman_constant_guard', 'absent_slots_are_reported', 'layout_is_derived_from_the_frame',
             'universality_across_widths', 'cross_sectional_is_a_named_profile_setting',
             'new_domain_is_data_not_code', 'two_domains_one_session', 'audit_matches_decision',
             'single_model_confidence_is_undefined', 'cross_sectional_ranking_is_scale_free',
             'feature_dim_headroom_is_warned', 'predict_each_keeps_gap_register',
             'undeclared_inputs_reported_only_when_affected', 'spectral_registry_ingests_protocol',
             'demo_frames_do_not_depend_on_labeled_flag', 'no_bare_asserts_in_library_code',
             'registry_and_blueprint_agree', 'absence_signal_recovers_mnar', 'absence_flag_tracks_the_input',
             'rank_needs_enough_samples', 'rank_ties_do_not_depend_on_units', 'drop_effect_counts_flips',
             'no_discarded_string_literals', 'indicator_vector_preps_raw_frames', 'reload_then_refit_keeps_absence',
             'checkpoint_requires_golden_arithmetic', 'fold_diffusion_detects_low_order_tampering',
             'absence_is_in_the_gap_register', 'constant_slot_invariant']

    @classmethod
    def run(cls) -> List[tuple]:
        return [(n, bool(getattr(cls, n)())) for n in cls.NAMES]


class QuantumTestSuite:
    @staticmethod
    def run() -> List[tuple]:
        r: List[tuple] = []
        r.append(('unitary_H', QuantumMathValidation.is_unitary(QuantumMath.hadamard())))
        r.append(('normalized_state', QuantumMathValidation.is_normalized(QuantumMath.ket0())))

        wf = QuantumWorkflow().add_gate('H', [0]).add_gate('X', [0]).add_gate('X', [0])
        QuantumMathValidation.validate_workflow(wf)
        r.append(('optimizer_cancels_XX', len(QuantumMathToolkit.optimize_workflow(wf).instructions) == 1))

        bell = MultiQubitMath.bell_pair()
        r.append(('bell_entropy_1bit', abs(MultiQubitMath.entanglement_entropy(bell) - 1.0) < 1e-9))

        reg = QuantumRegister(2)
        for op in QuantumFirstPrinciplesDemo.bell_state_pipeline().build():
            reg.apply(op)
        r.append(('bell_prep_fidelity', abs(QuantumMath.fidelity(reg.state, bell) - 1.0) < 1e-9))

        wf2 = QuantumWorkflow().add_gate('H', [0]).add_gate('CNOT', [0, 1])
        ir, depth = BackendCompiler().compile(wf2)
        reg2 = QuantumStateFactory.from_ir(ir, 2)
        r.append(('compiled_bell', abs(QuantumMath.fidelity(reg2.state, bell) - 1.0) < 1e-9 and depth == 2))

        # scheduler must keep dependent gates ordered
        sch = GateScheduler()
        for g in [{'op': 'H', 'targets': [0]}, {'op': 'CNOT', 'targets': [0, 1]}, {'op': 'X', 'targets': [1]}]:
            sch.add(g)
        r.append(('scheduler_order', [g['op'] for g in sch.to_ir().instructions] == ['H', 'CNOT', 'X']))

        H = Hamiltonian(2).add_term(1.0, 'Z', [0, 1]).add_term(0.5, 'X', [0]).add_term(0.2, 'Y', [1])
        psi = TimeEvolution.evolve(QuantumMath.ket0(4), H, 0.7)
        r.append(('hamiltonian_unitary_evolution', QuantumMathValidation.is_normalized(psi)))

        unanimous = QuantumEnsemble.mix({'a': 0.8, 'b': 0.8, 'c': 0.8})
        split = QuantumEnsemble.mix({'a': 0.05, 'b': 0.95})
        r.append(('ensemble_agree_vs_split',
                  unanimous['confidence'] > split['confidence'] and
                  unanimous['model_disagreement_entropy'] < split['model_disagreement_entropy']))

        K = QuantumKernel.gram_matrix(np.random.default_rng(0).normal(size=(5, 6)))
        r.append(('kernel_psd', bool(np.linalg.eigvalsh(K).min() > -1e-9)))

        opt = QuantumWeightOptimizer(3).optimize(np.array([0.9, 0.5, 0.1]))
        r.append(('optimizer_prefers_high_score', opt['weights'][0] > opt['weights'][2]))
        return r


class QuantumPackageIndex:
    """Registry of the engine's quantum-mathematical surface (Layer 1 names).

    The 'channel' module IS the quantum channel (Layer 2): UnifiedAnalyticsEngine's
    state preparation, decoherence, and POVM measurement.  'golden' IS Layer 3."""
    version = '1.0'
    modules = {
        'core': ['QuantumState', 'QuantumOperator', 'QuantumMath', 'QuantumMathEngine'],
        'hilbert': ['QuantumRegister'],
        'ir': ['QuantumIR', 'QuantumBackendNeutralCompiler', 'QuantumWorkflow'],
        'analysis': ['QuantumAnalyzer', 'QuantumMetrics', 'AdvancedEntanglement'],
        'compile': ['SymbolicGateOptimizer', 'GateScheduler', 'BackendCompiler', 'QuantumMathCompilerSuite'],
        'ops': ['Hamiltonian', 'TimeEvolution', 'MeasurementPostulates', 'PartialTrace'],
        'persistence': ['CircuitSerializer', 'StateCheckpoint'],
        'golden': ['GoldenArithmetic', 'GoldenIntegrityError'],       # Layer 3
        'validation': ['QuantumMathValidation', 'QuantumTestSuite'],
        'spectral': ['SpectralCertificate', 'SpectralCertificateRegistry', 'SpectralGapClosure',
                     'SpectralDiscrimination'],
        'integration': ['QuantumFeatureState', 'QuantumEnsemble', 'QuantumKernel',
                        'QuantumWeightOptimizer', 'QuantumUnifiedEngine',
                        'ExactIsingWeightSolver', 'CalibratedCoherentCommittee',
                        'TheoremVerificationSuite', 'MultiQubitMath',
                        'DomainProfile', 'SectorProfiles', 'UnifiedAnalyticsSession'],
        'channel': ['UnifiedAnalyticsEngine', 'UnifiedAnalyticsOrchestrator', 'ExplainabilityHub',
                    'PersistenceManager', 'PerformanceMonitor'],       # Layer 2: the quantum channel
    }

    @classmethod
    def describe(cls) -> Dict[str, Any]:
        return {'version': cls.version, 'modules': {k: len(v) for k, v in cls.modules.items()},
                'registered_sectors': DomainRegistry.names(),
                'planned_sectors': SystemBlueprint.planned_sectors, 'blueprint': {'version': SystemBlueprint.version,
                                                     'components': SystemBlueprint.components},
                'principles': QuantumDocumentation.principles()}

    @classmethod
    def environment_check(cls) -> Dict[str, bool]:
        return {'xgboost': XGBClassifier is not None, 'lightgbm': LGBMClassifier is not None,
                'nltk': SentimentIntensityAnalyzer is not None,
                'statsmodels': seasonal_decompose is not None, 'lime': lime_tabular is not None,
                'dask': dd is not None, 'spark': SparkSession is not None,
                'tensorflow': _optional('tensorflow') is not None}


__all__ = [n for names in QuantumPackageIndex.modules.values() for n in names] + [
    'EngineConfig', 'QuantumPackageIndex', 'UnifiedAnalyticsDemo']


if __name__ == '__main__':
    logging.basicConfig(level=logging.WARNING, format='    [engine %(levelname)s] %(message)s')   # show what the engine says
    print('environment:', QuantumPackageIndex.environment_check())

    # 1. Proofs, once per session
    session = UnifiedAnalyticsSession()
    proofs = session.verify()
    print(f"\nproofs (once): {proofs['passed']}/{proofs['total']} passed "
          f"(quantum self-tests + verified identities)")

    # 2. Same engine, different domains, same session
    DEMOS = (('fintech', UnifiedAnalyticsDemo.build_fintech_demo, 'device_risk', 600),
             ('supply_chain', UnifiedAnalyticsDemo.build_supply_chain_demo, 'weather', 2400),
             ('hr', UnifiedAnalyticsDemo.build_hr_demo, 'date', 2400))     # >= 60 test units each (see MIN_UNITS)
    for domain, builder, drop_col, n_rows in DEMOS:
        df, y = builder(n_rows, labeled=True)
        cut = int(n_rows * 0.7)
        train, test = df.head(cut), df.tail(n_rows - cut).reset_index(drop=True)
        ytr, yte = y.head(cut), y.tail(n_rows - cut).reset_index(drop=True)
        session.open(domain, model_names=['rf', 'gb']).fit(train, ytr)
        eng, gap = session.engine(domain), session.gap_register(domain)
        acc = eng.benchmark(test, yte)
        k = eng.config.chunk_rows
        dec = session.decide(domain, test.head(k))
        deg = session.decide(domain, test.head(k).drop(columns=[drop_col]))
        maj = max(yte.mean(), 1 - yte.mean())
        print(f"\n[{domain}] mode={gap['mode']} chunk_rows={gap['chunk_rows']} width={gap['width']} "
              f"held-out accuracy={acc['accuracy']:.3f} 95% CI [{acc['ci95'][0]:.2f}, {acc['ci95'][1]:.2f}] "
              f"on {acc['n_chunks']} chunks (majority baseline {maj:.2f})"
              + ('  <-- few chunks: wide interval, read with care' if acc['n_chunks'] < 50 else ''))
        d = dec['decision']
        fmt = lambda v: 'undefined' if v is None else f'{v:.3f}'
        print(f"  decision: p={d['probability']:.3f} confidence={fmt(d['confidence'])} "
              f"disagreement={fmt(d['disagreement'])}")
        de = drop_effect(eng, test, drop_col, n=150)
        lo_f, hi_f = de['flip_rate_ci95']
        print(f"  drop '{drop_col}' over {de['n_units']} units: mean|delta|={de['mean_abs_delta']:.3f} "
              f"p90={de['p90_abs_delta']:.3f} flipped={de['flipped']}/{de['n_units']} "
              f"(flip rate 95% CI [{lo_f:.2f}, {hi_f:.2f}], mean completeness {de['mean_completeness']:.2f})"
              + ('' if de['n_units'] >= 60 else '  <-- indicative only: under 60 units'))
        print(f"  gap register (clean input):    absent_at_fit={dec['gaps']['absent_at_fit']} "
              f"filled={dec['gaps']['filled']}")
        print(f"  gap register (dropped '{drop_col}'): imputed_columns={deg['gaps']['imputed_columns']} "
              f"filled={deg['gaps']['filled']} completeness={deg['gaps']['completeness']:.2f} "
              f"-> score {deg['score']:.3f}, confidence {fmt(deg['decision']['confidence'])}")
    layouts = {d: tuple(session.engine(d).slot_names) for d, _, _, _ in DEMOS}
    if len(set(layouts.values())) != len(layouts):          # widths may coincide (8 and 8); layouts may not
        raise RuntimeError('domains share a feature layout: the engine is not deriving it from the frame')
    print('\nwidths:', {d: len(v) for d, v in layouts.items()}, '| layouts all distinct')

    # 3. Components wired into the system
    hr_orch = session.domains['hr'].orchestrator
    print('\nintegrated components in action:')
    print('  monitor:', hr_orch.monitor.summary().groupby('metric')['value'].last().round(4).to_dict())
    wf = QuantumWorkflow().add_gate('H', [0]).add_gate('X', [1]).add_gate('X', [1]).add_gate('CNOT', [0, 1])
    compiler = QuantumMathCompilerSuite()
    compiled = compiler.compile_workflow(wf)
    print('  optimizer: 4 gates ->', len(compiled[0].instructions), f'gates (depth {compiled[1]})')
    reg = QuantumRegister(2)
    for op in QuantumFirstPrinciplesDemo.bell_state_pipeline().build():
        reg.apply(op)
    bell_m = reg.measure()
    print(f'  Bell state: index={bell_m["index"]}, Born distribution {bell_m["probabilities"][:4]}')
    print('  agnostic intent run:', QuantumAgnosticAdapter(QuantumMathEngine()).run(
        {'basis': 'computational'}, QuantumMath.ket0()))
    print('  demo BellPrep unitary:', QuantumMathValidation.is_unitary(QuantumDemo.bell_like_operator()))
    import tempfile as _tf
    _ck = os.path.join(_tf.mkdtemp(), 'ck.json')
    StateCheckpoint.save(reg, _ck)
    _back = StateCheckpoint.load(_ck)
    print('  golden-folded checkpoint: steps=10**9+7 (Pisano-reduced mod 3*2^63), header Fibonacci-coded,',
          'round trip bit-exact:', bool((np.asarray(_back.state.amplitudes) == np.asarray(reg.state.amplitudes)).all()))

    # 3b. Spectral discrimination demo
    print('\nspectral discrimination layer:')
    _rng = np.random.default_rng(99)
    _P = _rng.uniform(0.1, 0.9, (200, 5))
    _true = _rng.uniform(0.2, 0.8, 200)
    _phases = _rng.uniform(-np.pi, np.pi, 5)
    _t1 = SpectralDiscrimination.rank_correlation_protocol(_P, _true, _phases)
    _t2 = SpectralDiscrimination.capture_rate_protocol(_P, _true, _phases, 0.1)
    print('  T1 rank correlation:', {k: round(v, 4) for k, v in _t1['spearman_vs_error'].items()})
    print(f'  T1 strongest classical: {_t1["strongest_classical"]} (rho={_t1["strongest_classical_rho"]:.4f})')
    print('  T2 capture at 10% budget:', {k: round(v, 3) for k, v in _t2['captures'].items()})
    _sr = SpectralCertificateRegistry()
    _sr.ingest_protocol_result(_t1, domain='demo')
    print('  registry summary:', _sr.summary())

    # 4. Regression suite
    print('\nregression suite (engine warnings muted here: these checks exercise failure paths on purpose):')
    logging.getLogger().setLevel(logging.ERROR)
    reg_t = RegressionSuite.run()
    logging.getLogger().setLevel(logging.WARNING)
    for name, ok in reg_t:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    assert all(ok for _, ok in reg_t), 'regression suite failed'

    # 5. The open question, with transfer
    print('\ncommittee experiment: Spearman(uncertainty, |pooled - truth|); calibrate-world -> test-world')
    for calib, test_sign in ((-1.0, -1.0), (1.0, 1.0), (1.0, -1.0), (-1.0, 1.0)):
        r = committee_experiment(cluster_sign=test_sign, calib_sign=calib)
        tag = 'matched' if calib == test_sign else 'SHIFTED'
        print(f'  calibrated on sign={calib:+.0f}, tested on sign={test_sign:+.0f} [{tag}]')
        for k, v in r['spearman_vs_error'].items():
            if k.startswith('S,'):
                continue
            print(f'    {k:<28s} {v:+.4f}' + ('  (constant input)' if k in r['degenerate'] else ''))
