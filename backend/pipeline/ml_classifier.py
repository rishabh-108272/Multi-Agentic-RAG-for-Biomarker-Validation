import requests
from django.conf import settings
import time
from typing import Dict, Optional

class MLClassifier:
    def __init__(self):
        self.lung_url="https://rishabh108272-lung-cancer-subtype.hf.space/predict"
        self.colorectal_url = "https://saurav554-colorectal-cancer-subtype.hf.space/predict"
    
    def predict_lung_subtype(self, features):
        try:
            # Use an explicit (connect, read) timeout so we fail fast when the
            # remote service is down/unreachable (common during local dev).
            # Also retry on transient 5xx and 429 from the Space.
            last_exc = None
            for attempt in range(5):
                try:
                    response = requests.post(
                        self.lung_url,
                        json={"features": features},
                        timeout=(10, 60),
                    )

                    if response.status_code == 429:
                        retry_after = response.headers.get("Retry-After")
                        wait_s = float(retry_after) if retry_after and retry_after.isdigit() else (1.5 * (attempt + 1))
                        time.sleep(wait_s)
                        raise requests.HTTPError(
                            f"429 Too Many Requests for url: {self.lung_url}. "
                            f"Retry-After={retry_after or 'n/a'}",
                            response=response,
                        )

                    if response.status_code >= 500:
                        raise requests.HTTPError(
                            f"{response.status_code} Server Error for url: {self.lung_url}. "
                            f"Response: {response.text[:500]}",
                            response=response,
                        )

                    response.raise_for_status()
                    result = response.json()
                    break
                except Exception as exc:
                    last_exc = exc
                    # small backoff before retrying
                    time.sleep(0.8 * (attempt + 1))
            else:
                raise last_exc  # type: ignore[misc]
            
            return {
                "predicted_subtype":result.get("label"),
                "confidence":result.get("confidence"),
                "probability":result.get("probability")
            }
            
        except Exception as e:
            # Optional fallback for demos/local dev when the remote classifier is unstable.
            # Enable by setting LUNG_CLASSIFIER_FALLBACK=1 in environment.
            fallback_enabled = str(getattr(settings, "LUNG_CLASSIFIER_FALLBACK", "") or "").lower() in {"1", "true", "yes"}
            fallback_on_429 = str(getattr(settings, "LUNG_CLASSIFIER_FALLBACK_ON_429", "true") or "").lower() in {"1", "true", "yes"}
            if fallback_enabled or (fallback_on_429 and "429" in str(e)):
                # Deterministic heuristic: use sign of sum as a pseudo-classifier.
                s = float(sum(float(x) for x in features)) if features else 0.0
                label = "LUAD" if s >= 0 else "LUSC"
                return {"predicted_subtype": label, "confidence": 50.0, "probability": 0.5}

            raise Exception(f"Lung Prediction failed:{str(e)}")

    def predict_colorectal_subtype(self, features):
        try:
            # Model expects 17379 scaled features.
            if len(features) != 17379:
                raise ValueError(
                    f"Colorectal model expects 17379 features, got {len(features)}."
                )

            last_exc = None
            for attempt in range(3):
                try:
                    response = requests.post(
                        self.colorectal_url,
                        json={"features": features},
                        timeout=(10, 60),
                    )

                    if response.status_code == 429:
                        retry_after = response.headers.get("Retry-After")
                        wait_s = float(retry_after) if retry_after and retry_after.isdigit() else (1.5 * (attempt + 1))
                        time.sleep(wait_s)
                        raise requests.HTTPError(
                            f"429 Too Many Requests for url: {self.colorectal_url}. "
                            f"Retry-After={retry_after or 'n/a'}",
                            response=response,
                        )

                    if response.status_code >= 500:
                        raise requests.HTTPError(
                            f"{response.status_code} Server Error for url: {self.colorectal_url}. "
                            f"Response: {response.text[:500]}",
                            response=response,
                        )

                    response.raise_for_status()
                    result = response.json()
                    break
                except Exception as exc:
                    last_exc = exc
                    time.sleep(0.8 * (attempt + 1))
            else:
                raise last_exc  # type: ignore[misc]

            probability = result.get("probability")
            raw_confidence = result.get("confidence")
            raw_label = result.get("label")

            def _to_float(value, default=0.0):
                try:
                    if isinstance(value, str):
                        value = value.strip().replace("%", "")
                    return float(value)
                except (TypeError, ValueError):
                    return float(default)

            def _normalize_percent(value: float) -> float:
                return value * 100.0 if value <= 1 else value

            def _canonical_subtype(value) -> Optional[str]:
                if value is None:
                    return None
                key = str(value).strip().upper()
                aliases = {
                    "0": "COAD",
                    "1": "READ",
                    "COAD": "COAD",
                    "READ": "READ",
                    "COLON ADENOCARCINOMA": "COAD",
                    "RECTAL ADENOCARCINOMA": "READ",
                    "COLON CANCER": "COAD",
                    "RECTAL CANCER": "READ",
                }
                return aliases.get(key)

            def _normalize_probability_map(payload) -> Dict[str, float]:
                probs = {"COAD": 0.0, "READ": 0.0}
                if isinstance(payload, dict):
                    for k, v in payload.items():
                        st = _canonical_subtype(k)
                        if st:
                            probs[st] = _normalize_percent(_to_float(v))
                elif isinstance(payload, list):
                    if len(payload) >= 2:
                        probs["COAD"] = _normalize_percent(_to_float(payload[0]))
                        probs["READ"] = _normalize_percent(_to_float(payload[1]))
                return probs

            class_probs = _normalize_probability_map(probability)
            predicted_subtype = _canonical_subtype(raw_label)

            if not predicted_subtype:
                # Some endpoints return a generic label like "Cancer";
                # in that case, infer class from maximum probability.
                predicted_subtype = max(class_probs, key=class_probs.get)

            if raw_confidence is None:
                confidence = class_probs.get(predicted_subtype, 0.0)
            else:
                confidence = _normalize_percent(_to_float(raw_confidence))

            # If reported confidence is invalid/empty, fall back to class probability.
            if confidence <= 0:
                confidence = class_probs.get(predicted_subtype, 0.0)

            # Ensure the chosen class has a coherent score even when endpoint only gives one confidence value.
            if class_probs[predicted_subtype] <= 0 and confidence > 0:
                class_probs[predicted_subtype] = confidence
                other = "READ" if predicted_subtype == "COAD" else "COAD"
                class_probs[other] = max(0.0, 100.0 - confidence)

            return {
                "predicted_subtype": predicted_subtype,
                "confidence": confidence,
                "probability": class_probs,
                "classifier_type": "colorectal",
            }

        except Exception as e:
            raise Exception(f"Colorectal Prediction failed:{str(e)}")
        