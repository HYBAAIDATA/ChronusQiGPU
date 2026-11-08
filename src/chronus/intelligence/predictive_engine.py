from __future__ import annotations

import gc
import logging
import os
import shutil
import unittest
import warnings
from collections.abc import Callable
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.datasets import make_classification
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.seasonal import seasonal_decompose

try:
    from xgboost import XGBClassifier
    _HAS_XGB = True
except ImportError:
    XGBClassifier = None
    _HAS_XGB = False

try:
    from lightgbm import LGBMClassifier
    _HAS_LGBM = True
except ImportError:
    LGBMClassifier = None
    _HAS_LGBM = False

try:
    from nltk.sentiment import SentimentIntensityAnalyzer
except ImportError:
    SentimentIntensityAnalyzer = None


logger = logging.getLogger(__name__)


class PredictiveEngine:
    """
    Tabular + text sentiment classification engine.

    Fixes applied relative to prior revision:
      - _get_model_by_name is a pure factory (no stale-model reuse on refit).
      - XGB / LGBM unavailable -> explicit error (no silent GB substitution).
      - probability is the weighted mean of predict_proba (in [0,1]); no sigmoid re-wrap.
      - per-model 'confidence' is the decision margin |2p-1| (0 at boundary, 1 at certainty).
      - feature_importances are keyed by feature index f0..fN, not by factor name.
      - sentiment slot never overwrites a custom-feature slot.
      - TfidfVectorizer is fit in fit() and only transform()ed at inference; persisted.
      - single feature path: _extract_features is the only model input builder;
        _prepare_input_features removed.
      - custom-hook coercion shared between _extract_features and _extract_risk_indicators.
      - model_weights validated against model_names on load.
      - _train_model (state-mutating) removed.
      - optional Born-rule aggregation path, explicitly labeled; never claims quantum
        unless the caller supplies amplitudes.
    """

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        X_train: pd.DataFrame | np.ndarray | None = None,
        y_train: pd.Series | np.ndarray | None = None,
    ) -> None:
        self.config = config if config is not None else self._default_config()
        self._validate_config()
        self._initialize_components()
        self.models: dict[str, Any] = {}
        self.model_weights: dict[str, float] = {}
        self.is_baseline_model: bool = False
        self._load_or_train_models(X_train=X_train, y_train=y_train)

    # ------------------------------------------------------------------ config

    @staticmethod
    def _default_config() -> dict[str, Any]:
        return {
            "model_names": ["rf", "xgb", "lgbm", "gb"],
            "model_dir": "models/",
            "n_estimators": 20,
            "max_depth": 5,
            "learning_rate": 0.05,
            "cv_folds": 3,
            "performance_weight": 0.30,
            "behavioral_weight": 0.25,
            "engagement_weight": 0.20,
            "career_weight": 0.15,
            "external_weight": 0.10,
            "feature_dim": 10,
            "max_tfidf_features": 10,
            "selected_model": "rf",
            "imputation_strategy": "median",
            "use_random_baseline": True,
            "allow_missing_boosters": False,  # if False, missing xgb/lgbm is fatal
            "aggregation": "weighted_mean",   # "weighted_mean" | "born_rule"
        }

    def _validate_config(self) -> None:
        required_keys = ["model_names", "model_dir", "n_estimators", "max_depth"]
        missing_keys = [k for k in required_keys if k not in self.config]
        if missing_keys:
            raise ValueError(f"Missing required config keys: {missing_keys}")
        if int(self.config.get("feature_dim", 10)) < 2:
            raise ValueError("feature_dim must be at least 2")

        names = list(self.config["model_names"])
        if not names:
            raise ValueError("model_names must be non-empty")

        # Resolve availability up front; no silent substitution later.
        allow_missing = bool(self.config.get("allow_missing_boosters", False))
        unavailable = []
        for n in names:
            if n == "xgb" and not _HAS_XGB or n == "lgbm" and not _HAS_LGBM:
                unavailable.append(n)
            elif n not in {"rf", "xgb", "lgbm", "gb"}:
                raise ValueError(f"Unsupported model name: {n}")
        if unavailable and not allow_missing:
            raise RuntimeError(
                f"Requested models unavailable in this environment: {unavailable}. "
                f"Install them or set allow_missing_boosters=True (they will be dropped, "
                f"not substituted)."
            )
        if unavailable and allow_missing:
            warnings.warn(
                f"Dropping unavailable models {unavailable} from ensemble; "
                f"no substitute will be created.",
                UserWarning,
                stacklevel=2,
            )
            self.config["model_names"] = [n for n in names if n not in unavailable]
            if not self.config["model_names"]:
                raise RuntimeError("No models remain after dropping unavailable ones.")

        agg = self.config.get("aggregation", "weighted_mean")
        if agg not in {"weighted_mean", "born_rule"}:
            raise ValueError(f"Unsupported aggregation: {agg}")

    # -------------------------------------------------------------- components

    def _initialize_components(self) -> None:
        self.scaler = StandardScaler()
        self.imputer = SimpleImputer(
            strategy=self.config.get("imputation_strategy", "median")
        )
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=self.config.get("max_tfidf_features", 10),
            stop_words="english",
        )
        self._tfidf_fitted = False
        self.feature_engineering_methods: dict[str, Callable[[pd.DataFrame], Any]] = {}
        self.sentiment_analyzer = None
        if SentimentIntensityAnalyzer is not None:
            try:
                self.sentiment_analyzer = SentimentIntensityAnalyzer()
            except Exception:  # noqa: BLE001
                self.sentiment_analyzer = None

    def _get_model_by_name(self, name: str) -> Any:
        """Pure factory. Never consults self.models (prevents stale reuse on refit)."""
        n_est = int(self.config.get("n_estimators", 20))
        depth = int(self.config.get("max_depth", 5))
        lr = float(self.config.get("learning_rate", 0.05))

        if name == "rf":
            return RandomForestClassifier(
                n_estimators=n_est, max_depth=depth, random_state=42
            )
        if name == "xgb":
            if not _HAS_XGB:
                raise RuntimeError("xgboost not installed")
            return XGBClassifier(
                n_estimators=n_est,
                max_depth=depth,
                learning_rate=lr,
                random_state=42,
                eval_metric="logloss",
            )
        if name == "lgbm":
            if not _HAS_LGBM:
                raise RuntimeError("lightgbm not installed")
            return LGBMClassifier(
                n_estimators=n_est,
                max_depth=depth,
                learning_rate=lr,
                random_state=42,
                verbose=-1,
            )
        if name == "gb":
            return GradientBoostingClassifier(
                n_estimators=n_est, max_depth=depth, learning_rate=lr, random_state=42
            )
        raise ValueError(f"Unsupported model name: {name}")

    # ------------------------------------------------------------ persistence

    def _generate_synthetic_data(self) -> tuple[np.ndarray, np.ndarray]:
        n_features = int(self.config.get("feature_dim", 10))
        n_informative = max(2, min(n_features - 1, 6))
        X, y = make_classification(
            n_samples=120,
            n_features=n_features,
            n_informative=n_informative,
            n_redundant=0,
            weights=[0.5, 0.5],
            random_state=42,
        )
        return X, y

    def _artifacts_are_compatible(
        self, scaler_path: str, imputer_path: str, weights_path: str
    ) -> bool:
        if not (
            os.path.exists(scaler_path)
            and os.path.exists(imputer_path)
            and os.path.exists(weights_path)
        ):
            return False
        for name in self.config["model_names"]:
            if not os.path.exists(
                os.path.join(self.config["model_dir"], f"{name}.joblib")
            ):
                return False
        try:
            loaded_scaler = joblib.load(scaler_path)
            loaded_imputer = joblib.load(imputer_path)
            loaded_weights = joblib.load(weights_path)
            expected_dim = int(self.config.get("feature_dim", 10))
            if (
                getattr(loaded_scaler, "n_features_in_", None) != expected_dim
                or getattr(loaded_imputer, "n_features_in_", None) != expected_dim
            ):
                return False
            # weights must cover exactly the requested model names
            return set(loaded_weights.keys()) == set(self.config["model_names"])
        except Exception:  # noqa: BLE001
            return False

    def _load_or_train_models(
        self,
        X_train: pd.DataFrame | np.ndarray | None = None,
        y_train: pd.Series | np.ndarray | None = None,
    ) -> dict[str, Any]:
        model_dir = self.config["model_dir"]
        os.makedirs(model_dir, exist_ok=True)

        scaler_path = os.path.join(model_dir, "scaler.joblib")
        imputer_path = os.path.join(model_dir, "imputer.joblib")
        weights_path = os.path.join(model_dir, "model_weights.joblib")
        tfidf_path = os.path.join(model_dir, "tfidf.joblib")

        if X_train is not None and y_train is not None:
            self.fit(X_train, y_train, is_synthetic=False)
            return self.models

        if self._artifacts_are_compatible(scaler_path, imputer_path, weights_path):
            self.imputer = joblib.load(imputer_path)
            self.scaler = joblib.load(scaler_path)
            self.model_weights = joblib.load(weights_path)
            for name in self.config["model_names"]:
                model_path = os.path.join(model_dir, f"{name}.joblib")
                self.models[name] = joblib.load(model_path)
            if os.path.exists(tfidf_path):
                self.tfidf_vectorizer = joblib.load(tfidf_path)
                self._tfidf_fitted = True
            return self.models

        if not self.config.get("use_random_baseline", True):
            raise RuntimeError(
                "No compatible saved models found and use_random_baseline=False. "
                "Pass X_train and y_train or call fit(X, y)."
            )

        warnings.warn(
            "No saved models found for current feature_dim; fitting baseline models on "
            "synthetic data. Call engine.fit(X_train, y_train) with real data for production.",
            UserWarning,
            stacklevel=2,
        )
        X_syn, y_syn = self._generate_synthetic_data()
        self.fit(X_syn, y_syn, is_synthetic=True)
        return self.models

    # ------------------------------------------------------------------- fit

    def fit(
        self,
        X: pd.DataFrame | np.ndarray,
        y: pd.Series | np.ndarray,
        is_synthetic: bool = False,
    ) -> PredictiveEngine:
        X_arr = np.asarray(X, dtype=float)
        y_arr = np.asarray(y, dtype=int)
        if X_arr.ndim != 2 or X_arr.shape[0] == 0:
            raise ValueError("X must be a non-empty 2D array or DataFrame.")
        if X_arr.shape[0] != y_arr.shape[0]:
            raise ValueError("X and y must have the same number of rows.")

        self.config["feature_dim"] = X_arr.shape[1]
        self.is_baseline_model = is_synthetic

        X_imputed = self.imputer.fit_transform(X_arr)
        X_scaled = self.scaler.fit_transform(X_imputed)

        # fit TF-IDF if a text column is present in the DataFrame
        if isinstance(X, pd.DataFrame):
            text_cols = X.select_dtypes(include=["object", "string"]).columns
            if len(text_cols) > 0:
                self.tfidf_vectorizer.fit(X[text_cols[0]].fillna("").astype(str))
                self._tfidf_fitted = True

        model_dir = self.config["model_dir"]
        os.makedirs(model_dir, exist_ok=True)
        joblib.dump(self.imputer, os.path.join(model_dir, "imputer.joblib"))
        joblib.dump(self.scaler, os.path.join(model_dir, "scaler.joblib"))
        if self._tfidf_fitted:
            joblib.dump(self.tfidf_vectorizer, os.path.join(model_dir, "tfidf.joblib"))

        cv_folds = max(2, int(self.config.get("cv_folds", 3)))
        skf = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42)

        # fresh dicts; factory below never reads self.models
        self.models = {}
        self.model_weights = {}
        for name in self.config["model_names"]:
            estimator = self._get_model_by_name(name)
            estimator.fit(X_scaled, y_arr)
            joblib.dump(estimator, os.path.join(model_dir, f"{name}.joblib"))
            self.models[name] = estimator

            if is_synthetic:
                self.model_weights[name] = 1.0
            else:
                scores = cross_val_score(
                    estimator, X_scaled, y_arr, cv=skf, scoring="f1", error_score=0.0
                )
                self.model_weights[name] = max(float(np.mean(scores)), 1e-6)

        joblib.dump(self.model_weights, os.path.join(model_dir, "model_weights.joblib"))
        return self

    # ---------------------------------------------------------- feature hooks

    def add_feature_engineering(
        self, name: str, func: Callable[[pd.DataFrame], Any]
    ) -> None:
        if not callable(func):
            raise TypeError("Feature engineering method must be callable.")
        self.feature_engineering_methods[name] = func

    def _analyze_text_sentiment(self, text: str) -> float:
        if not isinstance(text, str) or not text.strip():
            return 0.0
        if self.sentiment_analyzer is not None:
            return float(self.sentiment_analyzer.polarity_scores(text)["compound"])
        pos_words = {"great", "good", "like", "well", "excellent", "happy", "best"}
        neg_words = {"not", "difficult", "hate", "sucks", "leave", "bad", "terrible"}
        tokens = [t.strip(".,!?").lower() for t in text.split()]
        if not tokens:
            return 0.0
        score = sum(
            (1 if t in pos_words else -1 if t in neg_words else 0) for t in tokens
        )
        return float(np.clip(score / max(len(tokens), 1), -1.0, 1.0))

    @staticmethod
    def _coerce_hook_result(res: Any) -> float:
        """Shared coercion for add_feature_engineering outputs. Always returns float."""
        try:
            if isinstance(res, pd.DataFrame):
                num = res.select_dtypes(include=[np.number])
                if num.empty:
                    return 0.0
                return float(np.nanmean(num.to_numpy(dtype=float)))
            if isinstance(res, pd.Series):
                num = pd.to_numeric(res, errors="coerce").dropna()
                return float(num.mean()) if len(num) else 0.0
            if isinstance(res, (np.ndarray, list, tuple)):
                arr = np.asarray(res, dtype=float).ravel()
                return float(np.nanmean(arr)) if arr.size else 0.0
            val = float(res)
            return 0.0 if np.isnan(val) else val
        except (TypeError, ValueError):
            return 0.0

    def _extract_features(self, data: pd.DataFrame) -> np.ndarray:
        if data.empty:
            raise ValueError("Input DataFrame cannot be empty.")

        target_dim = int(self.config.get("feature_dim", 10))
        vec = np.zeros(target_dim, dtype=float)

        # 1. numeric features: preserve row for single row, aggregate for multi-row
        num_df = data.select_dtypes(include=[np.number])
        if not num_df.empty:
            if len(num_df) == 1:
                num_vals = num_df.iloc[0].to_numpy(dtype=float)
            else:
                num_vals = num_df.mean(axis=0).to_numpy(dtype=float)
        else:
            num_vals = np.array([], dtype=float)

        # 2. custom hooks
        custom_vals = [self._coerce_hook_result(f(data)) for f in self.feature_engineering_methods.values()]

        # 3. sentiment (optional)
        text_cols = data.select_dtypes(include=["object", "string"]).columns
        sentiment_val: float | None = None
        if len(text_cols) > 0:
            col_series = data[text_cols[0]].dropna().astype(str)
            if not col_series.empty:
                sentiment_val = float(col_series.map(self._analyze_text_sentiment).mean())

        reserved_slots = len(custom_vals) + (1 if sentiment_val is not None else 0)
        num_limit = max(0, target_dim - reserved_slots)
        n_copy = min(len(num_vals), num_limit)
        if n_copy > 0:
            vec[:n_copy] = num_vals[:n_copy]

        idx = n_copy
        for c_val in custom_vals:
            if idx < target_dim:
                vec[idx] = c_val
                idx += 1

        # sentiment goes in the next free slot, never overwriting a custom feature
        if sentiment_val is not None and idx < target_dim:
            vec[idx] = sentiment_val

        return vec.reshape(1, -1)

    # -------------------------------------------------------------- indicators

    def _extract_risk_indicators(self, data: pd.DataFrame) -> dict[str, Any]:
        if not isinstance(data, pd.DataFrame) or data.empty:
            raise ValueError("Input must be a non-empty pandas DataFrame.")

        indicators: dict[str, Any] = {
            "performance_metrics": {},
            "behavioral_metrics": {},
            "engagement_metrics": {},
            "career_metrics": {},
            "external_metrics": {"market_condition": 0.5},
        }

        if "performance_score" in data.columns:
            s = data["performance_score"].dropna()
            indicators["performance_metrics"] = {
                "trend": float(s.diff().mean()) if len(s) > 1 else 0.0,
                "volatility": float(s.std()) if len(s) > 1 else 0.0,
                "relative_performance": float(s.mean()) if not s.empty else 0.0,
            }

        if "login_time" in data.columns:
            s = data["login_time"].dropna()
            indicators["behavioral_metrics"] = {
                "login_frequency": float(s.count()),
                "login_variability": float(s.std()) if len(s) > 1 else 0.0,
            }

        if "survey_text" in data.columns:
            s = data["survey_text"].dropna().astype(str)
            indicators["engagement_metrics"] = {
                "survey_sentiment": float(s.map(self._analyze_text_sentiment).mean())
                if not s.empty
                else 0.0
            }

        for name, func in self.feature_engineering_methods.items():
            indicators[name] = self._coerce_hook_result(func(data))

        return indicators

    # ------------------------------------------------------------- aggregation

    def _aggregate_weighted_mean(
        self, probs: dict[str, float]
    ) -> tuple[float, float]:
        """Exact weighted arithmetic mean. Returns (score, score_std)."""
        weighted_sum = 0.0
        total_weight = 0.0
        for name, prob in probs.items():
            w = float(self.model_weights.get(name, 1.0))
            weighted_sum += prob * w
            total_weight += w
        score = weighted_sum / total_weight if total_weight > 0 else 0.5
        std = float(np.std(list(probs.values()))) if len(probs) > 1 else 0.0
        return score, std

    def _aggregate_born_rule(
        self, probs: dict[str, float]
    ) -> tuple[float, float]:
        """
        Exact Born-rule aggregation. Requires amplitudes, NOT probabilities.

        If the caller supplied `amplitudes` (complex or real) via `_born_amplitudes`
        on the instance, we compute P(churn) = |<churn|psi>|^2 exactly. Otherwise
        we raise — we do NOT fabricate a state vector from classical features and
        call it quantum.
        """
        amps = getattr(self, "_born_amplitudes", None)
        if amps is None:
            raise RuntimeError(
                "aggregation='born_rule' requires explicit amplitudes. Set "
                "engine._born_amplitudes = np.array([a_0, a_1], dtype=complex) "
                "with |a_0|^2 + |a_1|^2 = 1 before calling predict_churn_risk. "
                "This engine does not fabricate a quantum state from classical "
                "features."
            )
        amps = np.asarray(amps, dtype=complex).ravel()
        if amps.size != 2:
            raise ValueError("amplitudes must have exactly 2 components (|0>, |1>).")
        norm = float(np.sum(np.abs(amps) ** 2))
        if not np.isclose(norm, 1.0, atol=1e-6):
            raise ValueError(f"amplitudes not normalized: sum|a|^2 = {norm}")
        p1 = float(np.abs(amps[1]) ** 2)
        # model spread still reported from classical sub-predictions
        std = float(np.std(list(probs.values()))) if len(probs) > 1 else 0.0
        return p1, std

    # ---------------------------------------------------------------- predict

    def predict_churn_risk(self, data: pd.DataFrame | np.ndarray) -> dict[str, Any]:
        if isinstance(data, np.ndarray):
            if data.size == 0:
                raise ValueError("Input array cannot be empty.")
            data = pd.DataFrame(data)
        if not isinstance(data, pd.DataFrame) or data.empty:
            raise ValueError("Input must be a non-empty pandas DataFrame or numpy array.")

        raw_vec = self._extract_features(data)
        imputed_vec = self.imputer.transform(raw_vec)
        scaled_vec = self.scaler.transform(imputed_vec)

        indicators = self._extract_risk_indicators(data)

        model_predictions: dict[str, dict[str, float]] = {}
        probs: dict[str, float] = {}
        for name, model in self.models.items():
            prob = float(model.predict_proba(scaled_vec)[0, 1])
            weight = float(self.model_weights.get(name, 1.0))
            # decision margin: 0 at boundary, 1 at full certainty
            margin = float(abs(2.0 * prob - 1.0))
            model_predictions[name] = {
                "score": prob,
                "decision_margin": margin,
                "weight": weight,
            }
            probs[name] = prob

        agg = self.config.get("aggregation", "weighted_mean")
        if agg == "born_rule":
            final_score, score_std = self._aggregate_born_rule(probs)
            aggregation_meta = {"method": "born_rule", "is_quantum": True}
        else:
            final_score, score_std = self._aggregate_weighted_mean(probs)
            aggregation_meta = {"method": "weighted_mean", "is_quantum": False}

        selected_model = self.models.get(self.config.get("selected_model", "rf"))

        return {
            "risk_score": {
                "score": final_score,
                "model_disagreement": score_std,
                "probability": final_score,  # already in [0,1]; no re-sigmoid
            },
            "confidence_level": max(0.0, 1.0 - score_std),
            "is_baseline_model": self.is_baseline_model,
            "aggregation": aggregation_meta,
            "key_factors": self._identify_key_factors(indicators),
            "recommended_actions": {
                "immediate_actions": ["Check-in with manager", "Review project workload"],
                "long_term_strategies": ["Career development planning"],
                "manager_recommendations": ["Schedule 1-on-1"],
            },
            "model_predictions": model_predictions,
            "feature_importances": self._get_feature_importance(
                selected_model, int(self.config.get("feature_dim", 10))
            )
            if selected_model is not None
            else None,
        }

    def _identify_key_factors(self, indicators: dict[str, Any]) -> dict[str, float]:
        weights = self._calculate_factor_weights(indicators)
        top_5 = sorted(weights.items(), key=lambda item: item[1], reverse=True)[:5]
        return dict(top_5)

    def _calculate_factor_weights(self, indicators: dict[str, Any]) -> dict[str, float]:
        weights = {
            "performance_metrics": float(self.config.get("performance_weight", 0.30)),
            "behavioral_metrics": float(self.config.get("behavioral_weight", 0.25)),
            "engagement_metrics": float(self.config.get("engagement_weight", 0.20)),
            "career_metrics": float(self.config.get("career_weight", 0.15)),
            "external_metrics": float(self.config.get("external_weight", 0.10)),
        }
        for custom_name in self.feature_engineering_methods:
            weights[custom_name] = 0.35
        return weights

    # ----------------------------------------------------------- text / trends

    def _analyze_performance_trend(self, data: pd.DataFrame) -> dict[str, float]:
        if (
            not isinstance(data, pd.DataFrame)
            or "performance_score" not in data.columns
            or "date" not in data.columns
        ):
            raise ValueError("DataFrame must include 'performance_score' and 'date'.")
        df = data.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values(by="date")
        ma = df["performance_score"].rolling(window=3, min_periods=1).mean()
        ewma = df["performance_score"].ewm(span=3, min_periods=1).mean()
        if len(df) > 10:
            decomp = seasonal_decompose(
                df["performance_score"], model="additive", period=5, extrapolate_trend="period"
            )
            trend = float(decomp.trend.bfill().mean())
        else:
            trend = float(df["performance_score"].diff().mean())
        return {
            "ma": float(ma.iloc[-1]) if not ma.empty else 0.0,
            "ewma": float(ewma.iloc[-1]) if not ewma.empty else 0.0,
            "trend": 0.0 if np.isnan(trend) else trend,
        }

    def _analyze_survey_responses(self, data: pd.DataFrame) -> np.ndarray:
        if not isinstance(data, pd.DataFrame) or "survey_text" not in data.columns:
            raise ValueError("DataFrame must contain 'survey_text' column.")
        if not self._tfidf_fitted:
            raise RuntimeError(
                "TfidfVectorizer not fitted; call fit() on data containing a text column first."
            )
        cleaned = data["survey_text"].fillna("").astype(str)
        return self.tfidf_vectorizer.transform(cleaned).toarray()

    def _get_feature_importance(
        self, model: Any, feature_dim: int
    ) -> dict[str, float]:
        """Keyed by feature index f0..fN — NOT by factor name (those have different lengths)."""
        if not hasattr(model, "feature_importances_"):
            raise ValueError("Model does not expose feature_importances_.")
        imps = np.asarray(model.feature_importances_, dtype=float).ravel()
        n = min(len(imps), feature_dim)
        return {f"f{i}": float(imps[i]) for i in range(n)}

    def cleanup(self) -> None:
        gc.collect()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPredictiveEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.config = {
            "model_names": ["rf", "gb"],  # deterministic across envs
            "model_dir": "test_models/",
            "n_estimators": 10,
            "max_depth": 4,
            "learning_rate": 0.05,
            "cv_folds": 2,
            "performance_weight": 0.30,
            "behavioral_weight": 0.25,
            "engagement_weight": 0.20,
            "career_weight": 0.15,
            "external_weight": 0.10,
            "feature_dim": 10,
            "max_tfidf_features": 10,
            "selected_model": "rf",
            "imputation_strategy": "median",
            "use_random_baseline": True,
            "allow_missing_boosters": True,
            "aggregation": "weighted_mean",
        }
        if os.path.exists(self.config["model_dir"]):
            shutil.rmtree(self.config["model_dir"])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.engine = PredictiveEngine(config=self.config)

        rng = np.random.default_rng(42)
        self.test_data = rng.random((10, self.config["feature_dim"]))
        self.test_data_timeseries = pd.DataFrame(
            {
                "date": pd.date_range("2023-01-01", periods=15, freq="MS"),
                "performance_score": rng.random(15),
            }
        )
        self.test_text_data = pd.DataFrame(
            {
                "survey_text": [
                    "This is a great place to work",
                    "I am not feeling well",
                    "I am feeling good",
                    "This project is difficult",
                    "I hate the system",
                ]
            }
        )
        self.test_data_missing = pd.DataFrame(
            {
                "performance_score": [np.nan, 0.8, 0.7, 0.9, 0.6, 0.7, 0.8, 0.9, 0.8, 0.7],
                "login_time": [1, 2, np.nan, 4, 5, 6, np.nan, 8, 9, 10],
                "survey_text": [
                    "This is a great place to work",
                    np.nan,
                    "I am feeling good",
                    "This project is difficult",
                    "I hate the system",
                    "I like work",
                    "Its OK here",
                    "Everything sucks",
                    "I want to leave",
                    "All is well",
                ],
            }
        )

    def tearDown(self) -> None:
        if os.path.exists(self.config["model_dir"]):
            shutil.rmtree(self.config["model_dir"])

    # --- construction / persistence ------------------------------------

    def test_instantiation(self) -> None:
        self.assertIsInstance(self.engine, PredictiveEngine)

    def test_second_load_does_not_refit(self) -> None:
        scaler_path = os.path.join(self.config["model_dir"], "scaler.joblib")
        mtime_before = os.path.getmtime(scaler_path)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            engine2 = PredictiveEngine(self.config)
        mtime_after = os.path.getmtime(scaler_path)
        self.assertEqual(mtime_before, mtime_after)
        self.assertEqual(set(engine2.models), set(self.config["model_names"]))

    def test_refit_rebuilds_estimators(self) -> None:
        """Regression for the stale-model bug: refit must create new estimator objects."""
        old = dict(self.engine.models)
        X, y = make_classification(n_samples=80, n_features=self.config["feature_dim"], random_state=7)
        self.engine.fit(X, y, is_synthetic=False)
        for name in self.config["model_names"]:
            self.assertIsNot(self.engine.models[name], old[name])
        self.assertFalse(self.engine.is_baseline_model)

    def test_incompatible_artifacts_reload(self) -> None:
        # corrupt weights file to be missing a model
        weights_path = os.path.join(self.config["model_dir"], "model_weights.joblib")
        joblib.dump({"rf": 1.0}, weights_path)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            engine2 = PredictiveEngine(self.config)
        self.assertEqual(set(engine2.model_weights), set(self.config["model_names"]))

    # --- predict -------------------------------------------------------

    def test_predict_structure(self) -> None:
        out = self.engine.predict_churn_risk(self.test_data)
        self.assertIn("risk_score", out)
        rs = out["risk_score"]
        self.assertIn("score", rs)
        self.assertIn("model_disagreement", rs)
        self.assertIn("probability", rs)
        self.assertEqual(rs["score"], rs["probability"])  # no re-sigmoid
        self.assertIn("decision_margin", next(iter(out["model_predictions"].values())))

    def test_probability_is_not_resigmoided(self) -> None:
        out = self.engine.predict_churn_risk(self.test_data)
        for mp in out["model_predictions"].values():
            self.assertGreaterEqual(mp["score"], 0.0)
            self.assertLessEqual(mp["score"], 1.0)
            # decision margin: |2p-1|
            self.assertAlmostEqual(mp["decision_margin"], abs(2 * mp["score"] - 1), places=6)

    def test_feature_importance_keyed_by_index(self) -> None:
        out = self.engine.predict_churn_risk(self.test_data)
        fi = out["feature_importances"]
        self.assertIsNotNone(fi)
        self.assertTrue(all(k.startswith("f") for k in fi))
        self.assertEqual(len(fi), self.config["feature_dim"])

    # --- feature engineering / sentiment ------------------------------

    def test_hook_and_sentiment_do_not_collide(self) -> None:
        # feature_dim=2 forces collision territory: 1 numeric, 1 custom, 1 sentiment
        cfg = dict(self.config)
        cfg["feature_dim"] = 3  # 1 numeric + 1 custom + 1 sentiment
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            eng = PredictiveEngine(cfg)
        eng.add_feature_engineering("custom", lambda df: 0.99)
        df = pd.DataFrame({"score": [0.5], "text": ["I hate this place"]})
        vec = eng._extract_features(df)
        self.assertEqual(vec.shape, (1, 3))
        self.assertAlmostEqual(vec[0, 1], 0.99, places=6)   # custom in slot 1
        self.assertNotEqual(vec[0, 2], 0.0)                  # sentiment in slot 2

    def test_hook_coercion_handles_bad_types(self) -> None:
        self.engine.add_feature_engineering("returns_none", lambda df: None)
        self.engine.add_feature_engineering("returns_str", lambda df: "nope")
        self.engine.add_feature_engineering("returns_ok", lambda df: 0.5)
        out = self.engine.predict_churn_risk(self.test_data_missing)
        self.assertIn("returns_ok", out["key_factors"])

    # --- trend / text --------------------------------------------------

    def test_performance_trend_short_and_long(self) -> None:
        short = self.engine._analyze_performance_trend(self.test_data_timeseries.iloc[:5])
        self.assertIn("trend", short)
        long = self.engine._analyze_performance_trend(self.test_data_timeseries)
        self.assertIn("trend", long)

    def test_tfidf_transform_only_after_fit(self) -> None:
        with self.assertRaises(RuntimeError):
            self.engine._analyze_survey_responses(self.test_text_data)
        self.engine.tfidf_vectorizer.fit(
            self.test_text_data["survey_text"].astype(str)
        )
        self.engine._tfidf_fitted = True
        feats = self.engine._analyze_survey_responses(self.test_text_data)
        self.assertEqual(feats.shape[0], len(self.test_text_data))

    # --- error handling ------------------------------------------------

    def test_exceptions(self) -> None:
        with self.assertRaises(ValueError):
            self.engine._get_model_by_name("wrong")
        with self.assertRaises(ValueError):
            self.engine.predict_churn_risk(pd.DataFrame())
        with self.assertRaises(ValueError):
            self.engine._extract_risk_indicators("bad data")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            self.engine._analyze_performance_trend(pd.DataFrame({"login_time": [1, 2, 3]}))
        with self.assertRaises(ValueError):
            self.engine._analyze_survey_responses(np.random.rand(10, 10))  # type: ignore[arg-type]

    # --- Born rule is honest -----------------------------------------

    def test_born_rule_requires_amplitudes(self) -> None:
        cfg = dict(self.config)
        cfg["aggregation"] = "born_rule"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            eng = PredictiveEngine(cfg)
        with self.assertRaises(RuntimeError):
            eng.predict_churn_risk(self.test_data)

    def test_born_rule_with_valid_amplitudes(self) -> None:
        cfg = dict(self.config)
        cfg["aggregation"] = "born_rule"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            eng = PredictiveEngine(cfg)
        # |psi> = (1/sqrt(2))(|0> + |1>) -> P(churn) = 0.5 exactly
        eng._born_amplitudes = np.array([1 / np.sqrt(2), 1 / np.sqrt(2)], dtype=complex)
        out = eng.predict_churn_risk(self.test_data)
        self.assertAlmostEqual(out["risk_score"]["score"], 0.5, places=9)
        self.assertTrue(out["aggregation"]["is_quantum"])

    def test_born_rule_rejects_unnormalized(self) -> None:
        cfg = dict(self.config)
        cfg["aggregation"] = "born_rule"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            eng = PredictiveEngine(cfg)
        eng._born_amplitudes = np.array([1.0, 1.0], dtype=complex)
        with self.assertRaises(ValueError):
            eng.predict_churn_risk(self.test_data)

    def test_missing_booster_is_fatal_when_not_allowed(self) -> None:
        cfg = dict(self.config)
        cfg["allow_missing_boosters"] = False
        cfg["model_names"] = ["xgb", "lgbm"]
        if _HAS_XGB and _HAS_LGBM:
            self.skipTest("boosters installed; cannot exercise missing-path")
        with self.assertRaises(RuntimeError):
            PredictiveEngine(cfg)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main(argv=["first-arg-is-ignored"], exit=False, verbosity=2)
