import io
import numpy as np
import pandas as pd
from celery import shared_task
from django.utils import timezone
import os
import concurrent.futures

from .models import (
    PatientAnalysis,
    XAIResult,
    DrugCandidate,
    AgentReport,
    PatientSummaryReport
)

from .ml_classifier import MLClassifier
from .xai_engine import XAIEngine
from .gene_mapper import GeneMapper
from .drug_engine import DrugRepurposingEngine


@shared_task
def run_full_pipeline(analysis_id, csv_data, classifier_type="lung"):
    try:
        analysis = PatientAnalysis.objects.get(id=analysis_id)

        # =========================
        # STEP 1: Parse CSV
        # =========================
        analysis.status = "RUNNING"
        analysis.current_step = "Parsing CSV"
        analysis.current_step_number = 1
        analysis.save()

        def _preprocess_rna_seq_like_model(df_matrix: pd.DataFrame):
            """
            Match the user's preprocessing:
            - drop rows with any NaN
            - transpose
            - ensure 2D output

            Expects df_matrix with:
            - rows = genes/features
            - columns = samples (typically 1 column for a single patient)
            """
            df_clean = df_matrix.dropna(axis=0, how="any")
            df_transposed = df_clean.transpose()

            input_vector = df_transposed.values
            if input_vector.ndim == 1:
                input_vector = input_vector.reshape(1, -1)

            return input_vector, df_clean.index.tolist()

        def _parse_patient_csv(raw_csv: str):
            """
            Build a gene-by-sample matrix, then apply preprocessing above.

            Supported layouts:
            1) Long format (20518 x 2): gene, expression
            2) Wide format: one row with many gene columns (optionally multiple rows -> first row)
            """
            df_local = pd.read_csv(io.StringIO(raw_csv), sep=None, engine="python")
            if df_local is None or df_local.empty:
                raise Exception("Uploaded CSV is empty.")

            # Normalize column names for matching.
            columns_local = list(df_local.columns)
            lowered = {str(c).strip().lower(): c for c in columns_local}

            patient_id_col_candidates = ["patientid", "patient_id", "patient", "patient id"]
            patient_id_col = next((lowered.get(k) for k in patient_id_col_candidates if k in lowered), None)

            patient_id_value_local = None
            if patient_id_col:
                v = df_local.iloc[0][patient_id_col]
                if pd.notna(v) and str(v).strip():
                    patient_id_value_local = str(v).strip()

            # Remove patient id column from parsing if present.
            df_no_pid = df_local.drop(columns=[patient_id_col]) if patient_id_col else df_local

            # --- Case A: long format gene/expression pairs (e.g. 20518 x 2)
            if df_no_pid.shape[1] == 2 and df_no_pid.shape[0] >= 1000:
                c1, c2 = list(df_no_pid.columns)
                n1 = pd.to_numeric(df_no_pid[c1], errors="coerce")
                n2 = pd.to_numeric(df_no_pid[c2], errors="coerce")
                n1_ratio = float(n1.notna().mean())
                n2_ratio = float(n2.notna().mean())

                if (n1_ratio < 0.5 and n2_ratio >= 0.9) or (n2_ratio < 0.5 and n1_ratio >= 0.9):
                    gene_col = c1 if n1_ratio < n2_ratio else c2
                    expr_col = c2 if gene_col == c1 else c1

                    genes = df_no_pid[gene_col].astype(str).str.strip()
                    expr = pd.to_numeric(df_no_pid[expr_col], errors="coerce")

                    # Build gene-by-sample matrix with genes as index, one sample column.
                    matrix = pd.DataFrame({"expr": expr.values}, index=genes.values)
                    # Drop empty / nan gene names
                    matrix = matrix[~matrix.index.astype(str).str.strip().isin(["", "nan", "None"])]
                    matrix.index = matrix.index.astype(str)

                    input_vector, gene_list = _preprocess_rna_seq_like_model(matrix)

                    expected_feature_count = 20518 if classifier_type == "lung" else 17379
                    if input_vector.shape[1] != expected_feature_count:
                        raise Exception(
                            f"Expected {expected_feature_count} gene expression values but got {input_vector.shape[1]}. "
                            "Ensure your CSV contains the required number of (gene, expression) rows with numeric expression values."
                        )

                    return patient_id_value_local, gene_list, input_vector

            # --- Case B: wide format (gene columns)
            # Use the first row as the patient sample, coerce to numeric, then transpose to genes-as-rows.
            wide_first_row = df_no_pid.iloc[[0]].copy()
            wide_first_row = wide_first_row.apply(pd.to_numeric, errors="coerce")
            wide_first_row = wide_first_row.dropna(axis=1, how="all")

            if wide_first_row.empty:
                raise Exception(
                    "CSV parsing failed: could not find numeric expression data. "
                    "Expected either (gene, expression) pairs or a wide numeric feature row."
                )

            gene_by_sample = wide_first_row.transpose()
            gene_by_sample.index = gene_by_sample.index.astype(str)

            input_vector, gene_list = _preprocess_rna_seq_like_model(gene_by_sample)
            return patient_id_value_local, gene_list, input_vector

        patient_id_value, feature_names, feature_vector = _parse_patient_csv(csv_data)

        if patient_id_value:
            analysis.patient_id = patient_id_value
            analysis.save(update_fields=["patient_id"])

        # =========================
        # STEP 2: ML Prediction
        # =========================
        analysis.current_step = "Predicting subtype"
        analysis.current_step_number = 2
        analysis.save()

        classifier = MLClassifier()
        features = feature_vector.flatten().tolist()
        if classifier_type == "colorectal":
            prediction = classifier.predict_colorectal_subtype(features)
        else:
            prediction = classifier.predict_lung_subtype(features)

        analysis.predicted_subtype = prediction["predicted_subtype"]
        analysis.luad_confidence = float(prediction["confidence"])
        analysis.lusc_confidence = max(0.0, 100.0 - float(prediction["confidence"]))

        analysis.save()

        # =========================
        # STEP 3: SHAP + LIME
        # =========================
        analysis.current_step = "Running SHAP + LIME Analysis"
        analysis.current_step_number = 3
        analysis.save()

        classifier = MLClassifier()
        def real_predict(features):
            if classifier_type == "colorectal":
                return classifier.predict_colorectal_subtype(features)['confidence']
            return classifier.predict_lung_subtype(features)['confidence']

        xai_engine = XAIEngine(lambda x: np.array([[real_predict(row.tolist())] for row in x]))

        shap_results = xai_engine.run_shap_analysis(
            feature_vector,
            feature_names
        )

        lime_results = xai_engine.run_lime_analysis(
            feature_vector,
            feature_names
        )

        merged_results = xai_engine.merge_results(
            shap_results,
            lime_results
        )

        # =========================
        # STEP 4: Gene Mapping
        # =========================
        analysis.current_step = "Mapping genes"
        analysis.current_step_number = 4
        analysis.save()

        mapper = GeneMapper()
        mapped_results = mapper.map_xai_results(merged_results)

        for item in mapped_results:
            XAIResult.objects.create(
                analysis=analysis,
                gene_index=feature_names.index(item["gene"]),
                gene_symbol=item["gene_symbol"],
                shap_value=item["shap_value"],
                lime_weight=item["lime_weight"],
                shap_direction="up" if item["shap_value"] > 0 else "down",
                lime_direction="positive" if item["lime_weight"] > 0 else "negative",
                high_confidence=item["high_confidence"]
            )

        analysis.total_genes_analyzed = len(mapped_results)
        analysis.save()

        # =========================
        # STEP 5: Drug Repurposing
        # =========================
        analysis.current_step = "Finding Drug Candidates"
        analysis.current_step_number = 5
        analysis.save()

        top_genes = [x["gene_symbol"] for x in mapped_results[:10]]

        drug_engine = DrugRepurposingEngine()
        drug_candidates = drug_engine.get_top_drug_candidates(top_genes)

        for gene, drugs in drug_candidates.items():
            for drug in drugs:
                DrugCandidate.objects.create(
                    analysis=analysis,
                    gene_symbol=gene,
                    drug_name=drug.get("drug_name"),
                    chembl_id=drug.get("concept_id", ""),
                    mechanism=", ".join(drug.get("types", [])),
                    action_type="Drug-Gene Interaction",
                    max_phase=0
                )

        # =========================
        # STEP 6: Multi-Agentic RAG
        # =========================
        analysis.current_step = "Running Multi-Agentic RAG"
        analysis.current_step_number = 6
        analysis.save()

        reports = []

        rag_top_n = int(os.getenv("RAG_TOP_GENES", "2"))
        rag_timeout_s = int(os.getenv("RAG_GENE_TIMEOUT_S", "90"))

        rag_items = mapped_results[:rag_top_n]
        top_genes_for_rag = [x["gene_symbol"] for x in rag_items]
        top_drugs_for_rag = list({
            d.get("drug_name")
            for gene_name in top_genes_for_rag
            for d in drug_candidates.get(gene_name, [])
            if d.get("drug_name")
        })

        for idx, item in enumerate(rag_items, start=1):
            gene = item["gene_symbol"]

            analysis.current_step = f"Running Multi-Agentic RAG ({idx}/{len(rag_items)}): {gene}"
            analysis.save(update_fields=["current_step"])

            drugs_for_gene = [
                d.get("drug_name")
                for d in drug_candidates.get(gene, [])
            ]

            try:
                from .langgraph_pipeline import run_langgraph_pipeline

                # Run with a hard timeout so a single stuck network/LLM call doesn't hang the pipeline.
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    fut = ex.submit(
                        run_langgraph_pipeline,
                        gene=gene,
                        shap_score=item["shap_value"],
                        drug_candidates=drugs_for_gene,
                        top_genes=top_genes_for_rag,
                        top_drugs=top_drugs_for_rag,
                        cancer_type=classifier_type,
                    )
                    rag_output = fut.result(timeout=rag_timeout_s)
                    final_report = rag_output.get("final_report", "")
                    sections = rag_output.get("sections", [])
            except Exception as rag_exc:
                rag_err_text = str(rag_exc).strip() or rag_exc.__class__.__name__
                rag_err = rag_err_text.lower()
                if "decommissioned" in rag_err or "model_decommissioned" in rag_err:
                    rag_hint = "Configured Groq model is decommissioned; switch RAG_MODEL_* to active Groq models."
                elif "rate limit" in rag_err or "429" in rag_err or "tokens per minute" in rag_err:
                    rag_hint = "Groq rate limit may be hit; reduce RAG_TOP_GENES or increase retry delay."
                elif "timeout" in rag_err:
                    rag_hint = "RAG timeout reached; increase RAG_GENE_TIMEOUT_S or reduce per-gene agent workload."
                else:
                    rag_hint = "Check GROQ_API_KEY and RAG_MODEL_* configuration."
                final_report = (
                    f"RAG report unavailable for {gene}: {rag_err_text}. "
                    f"{rag_hint}"
                )
                sections = [
                    {"title": "Gene Agent", "content": final_report},
                    {"title": "Pathway Agent", "content": final_report},
                    {"title": "Drug Agent", "content": final_report},
                    {"title": "Literature Agent", "content": final_report},
                    {"title": "Aggregator Agent", "content": final_report},
                ]

            AgentReport.objects.create(
                analysis=analysis,
                gene_symbol=gene,
                agent_name="multi_agentic_rag",
                report_text=final_report,
                sections=sections
            )

            reports.append({
                "gene": gene,
                "sections": sections
            })

        # =========================
        # STEP 7: Summary
        # =========================
        analysis.current_step = "Generating Summary"
        analysis.current_step_number = 7
        analysis.save()

        summary_text = f"""
        Predicted subtype: {analysis.predicted_subtype}
        Total biomarkers analyzed: {analysis.total_genes_analyzed}
        Top genes: {top_genes[:5]}
        """

        # Build results matching frontend AnalysisResults shape
        driver_genes = []
        for xai in XAIResult.objects.filter(analysis=analysis)[:8]:
            driver_genes.append({
                "index": xai.gene_index,
                "symbol": xai.gene_symbol,
                "shap": float(xai.shap_value),
                "lime": float(xai.lime_weight),
                "confidence": 0.85 if xai.high_confidence else 0.75,
                "direction": xai.shap_direction
            })

        drug_candidates_list = []
        for dc in DrugCandidate.objects.filter(analysis=analysis):
            drug_candidates_list.append({
                "gene": dc.gene_symbol,
                "drug": dc.drug_name,
                "mechanism": dc.mechanism,
                "phase": "FDA Approved" if dc.max_phase >= 3 else f"Phase {dc.max_phase}",
                "chemblId": dc.chembl_id
            })

        agent_reports = reports
        aggregator_summaries = []
        for report in reports:
            gene_name = report.get("gene", "")
            sections = report.get("sections", [])
            agg_section = next((s for s in sections if s.get("title") == "Aggregator Agent"), None)
            if agg_section and agg_section.get("content"):
                aggregator_summaries.append(f"{gene_name}\n{agg_section.get('content')}")
        combined_aggregator_summary = "\n\n".join(aggregator_summaries) if aggregator_summaries else "No aggregator summary available."

        if classifier_type == "colorectal":
            probs = prediction.get("probability") if isinstance(prediction.get("probability"), dict) else {}
            coad_score = float(probs.get("COAD", 0.0))
            read_score = float(probs.get("READ", 0.0))
            # Fallback when remote endpoint returns only one scalar confidence.
            if coad_score <= 0 and read_score <= 0:
                winner = "COAD" if analysis.predicted_subtype == "COAD" else "READ"
                winner_score = float(prediction["confidence"])
                loser_score = max(0.0, 100.0 - winner_score)
                coad_score = winner_score if winner == "COAD" else loser_score
                read_score = winner_score if winner == "READ" else loser_score

            subtype_scores = [
                {"name": "COAD", "value": coad_score},
                {"name": "READ", "value": read_score},
            ]
        else:
            subtype_scores = [
                {"name": "LUAD", "value": float(prediction["confidence"]) if analysis.predicted_subtype == "LUAD" else float(100 - prediction["confidence"])},
                {"name": "LUSC", "value": float(prediction["confidence"]) if analysis.predicted_subtype == "LUSC" else float(100 - prediction["confidence"])},
            ]

        results_data = {
            "subtype": analysis.predicted_subtype,
            "confidence": float(prediction["confidence"]),
            "subtypeScores": subtype_scores,
            "driverGenes": driver_genes,
            "drugCandidates": drug_candidates_list,
            "agentReports": agent_reports,
            "summary": {
                "patientId": analysis.patient_id,
                "subtype": analysis.predicted_subtype,
                "topGenes": top_genes[:5] if 'top_genes' in locals() else [],
                "topDrugs": list(set([d.drug_name for d in DrugCandidate.objects.filter(analysis=analysis)[:5]])),
                "aggregatorSummary": combined_aggregator_summary
            }
        }

        analysis.results = results_data
        analysis.status = "COMPLETE"
        analysis.completed_at = timezone.now()
        analysis.current_step = "Completed"
        analysis.save()

        PatientSummaryReport.objects.create(
            analysis=analysis,
            summary_text=summary_text,
            top_genes=top_genes[:5] if 'top_genes' in locals() else [],
            top_drugs=dict(drug_candidates) if 'drug_candidates' in locals() else {},
            clinical_recommendations=combined_aggregator_summary
        )

        return {
            "status": "COMPLETE",
            "analysis_id": str(analysis.id)
        }

    except Exception as e:
        try:
            analysis = PatientAnalysis.objects.get(id=analysis_id)
            analysis.status = "FAILED"
            analysis.error_message = str(e)
            analysis.save()
        except:
            pass

        return {
            "status": "FAILED",
            "error": str(e)
        }