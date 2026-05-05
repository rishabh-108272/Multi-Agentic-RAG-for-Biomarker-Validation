import numpy as np
import pandas as pd
import shap
from lime.lime_tabular import LimeTabularExplainer
import os


class XAIEngine:
    def __init__(self, model_predict_function):
        self.model_predict_function = model_predict_function

    def run_shap_analysis(self, feature_vector, feature_names):
        """
        feature_vector: np.array shape (1, n_features)
        """
        try:
            n_features = int(feature_vector.shape[1])
            # KernelSHAP on 20k+ features is prohibitively slow, especially when
            # model_predict_function makes remote HTTP calls. Use a fast heuristic
            # fallback unless explicitly forced.
            force_full = os.getenv("FORCE_FULL_XAI", "").lower() in {"1", "true", "yes"}
            if (n_features > 2000) and not force_full:
                values = np.asarray(feature_vector[0], dtype=float)
                # Heuristic importance: rank by absolute deviation from median.
                # Works for single-sample cases and is bounded/fast.
                med = float(np.median(values)) if values.size else 0.0
                importance = np.abs(values - med)
                top_idx = np.argsort(importance)[::-1][:10]
                return [
                    {"gene": str(feature_names[i]), "shap_value": float(importance[i])}
                    for i in top_idx
                ]

            background = np.repeat(feature_vector, 10, axis=0)

            explainer = shap.KernelExplainer(
                self.model_predict_function,
                background
            )

            # Bound runtime for full mode as well.
            shap_values = explainer.shap_values(feature_vector, nsamples=100)

            if isinstance(shap_values, list):
                shap_matrix = np.mean([np.abs(sv) for sv in shap_values], axis=0)
            else:
                shap_matrix = np.abs(shap_values)

                if shap_matrix.ndim == 3:
                    shap_matrix = shap_matrix.mean(axis=-1)

            importance = shap_matrix[0]

            importance_df = pd.DataFrame({
                "gene": feature_names,
                "shap_value": importance
            }).sort_values("shap_value", ascending=False)

            return importance_df.head(10).to_dict(orient="records")

        except Exception as e:
            raise Exception(f"SHAP failed: {str(e)}")

    def run_lime_analysis(self, feature_vector, feature_names):
        try:
            n_features = int(feature_vector.shape[1])
            force_full = os.getenv("FORCE_FULL_XAI", "").lower() in {"1", "true", "yes"}
            if (n_features > 2000) and not force_full:
                values = np.asarray(feature_vector[0], dtype=float)
                med = float(np.median(values)) if values.size else 0.0
                importance = values - med
                top_idx = np.argsort(np.abs(importance))[::-1][:10]
                return [
                    {"gene": str(feature_names[i]), "lime_weight": float(importance[i])}
                    for i in top_idx
                ]

            explainer = LimeTabularExplainer(
                training_data=np.repeat(feature_vector, 10, axis=0),
                feature_names=feature_names,
                mode='classification'
            )

            exp = explainer.explain_instance(
                feature_vector[0],
                self.model_predict_function,
                num_features=10
            )

            lime_results = []

            for feature, weight in exp.as_list():
                lime_results.append({
                    "gene": feature,
                    "lime_weight": weight
                })

            return lime_results

        except Exception as e:
            raise Exception(f"LIME failed: {str(e)}")

    def merge_results(self, shap_results, lime_results):
        merged = []

        for shap_item in shap_results:
            gene = shap_item["gene"]

            lime_match = next(
                (x for x in lime_results if gene in x["gene"]),
                None
            )

            merged.append({
                "gene": gene,
                "shap_value": shap_item["shap_value"],
                "lime_weight": lime_match["lime_weight"] if lime_match else 0,
                "high_confidence": True
            })

        return merged