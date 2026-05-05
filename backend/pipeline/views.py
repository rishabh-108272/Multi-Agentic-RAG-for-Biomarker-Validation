import logging
import os
import threading
import uuid
from datetime import timedelta

from django.db import close_old_connections
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import DrugCandidate, PatientAnalysis
from .serializers import PatientAnalysisSerializer

logger = logging.getLogger(__name__)


def _run_pipeline_in_thread(analysis_id: str, csv_content: str, classifier_type: str) -> None:
    """Run heavy pipeline off the request thread (avoids Gunicorn/Render timeouts when Celery is down)."""
    close_old_connections()
    try:
        from .queue_tasks import run_full_pipeline_queued

        run_full_pipeline_queued(analysis_id, csv_content, classifier_type)
    except Exception:
        logger.exception("Background pipeline failed for analysis_id=%s", analysis_id)
    finally:
        close_old_connections()


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def analyze_csv(request):
    try:
        file = request.FILES.get("file")
        classifier_type = str(request.data.get("classifier_type", "lung")).strip().lower()
        if not file or not file.name.endswith(".csv"):
            return Response({"error": "CSV file required"}, status=400)
        if classifier_type not in {"lung", "colorectal"}:
            return Response(
                {"error": "Invalid classifier_type. Use 'lung' or 'colorectal'."},
                status=400,
            )

        patient_id = f"PATIENT-{uuid.uuid4().hex[:8]}"
        analysis = PatientAnalysis.objects.create(
            patient_id=patient_id,
            status="PENDING",
            current_step="Queued",
        )

        try:
            csv_content = file.read().decode("utf-8")
        except UnicodeDecodeError:
            analysis.delete()
            return Response(
                {"error": "CSV must be valid UTF-8 text."},
                status=400,
            )

        from .queue_tasks import run_full_pipeline_queued

        # In cloud deploys, avoid running the heavy ML/RAG pipeline inside web workers by default.
        # Use Celery + Redis for production, or explicitly allow thread fallback.
        _is_deployed = bool(os.getenv("RENDER") or os.getenv("RAILWAY_ENVIRONMENT"))
        allow_thread_fallback = os.getenv(
            "ALLOW_THREAD_PIPELINE_FALLBACK",
            "true",
        ).lower() in ("1", "true", "yes")

        try:
            run_full_pipeline_queued.delay(str(analysis.id), csv_content, classifier_type)
        except Exception as exc:
            if not allow_thread_fallback:
                analysis.status = "FAILED"
                analysis.current_step = "Queue unavailable"
                analysis.error_message = (
                    f"Celery broker unavailable: {exc}. "
                    "Configure CELERY_BROKER_URL and run a Celery worker."
                )
                analysis.save(update_fields=["status", "current_step", "error_message"])
                return Response(
                    {
                        "error": "Background queue unavailable. Configure Celery/Redis worker.",
                        "analysis_id": str(analysis.id),
                    },
                    status=503,
                )

            analysis.current_step = "Processing (background)"
            analysis.error_message = f"Celery unavailable, running in background thread: {exc}"
            analysis.save(update_fields=["current_step", "error_message"])
            threading.Thread(
                target=_run_pipeline_in_thread,
                args=(str(analysis.id), csv_content, classifier_type),
                daemon=True,
            ).start()

        serializer = PatientAnalysisSerializer(analysis)
        return Response(serializer.data)
    except Exception as exc:
        logger.exception("analyze_csv failed")
        return Response({"error": str(exc)}, status=500)
    
@api_view(['GET'])
def analysis_status(request, analysis_id):
    try:
        analysis = PatientAnalysis.objects.get(id=analysis_id)
        serializer = PatientAnalysisSerializer(analysis)
        return Response({
            "status": analysis.status,
            "current_step": analysis.current_step,
            "current_step_number": analysis.current_step_number,
            "total_steps": 7,
            "analysis": serializer.data
        })
    except PatientAnalysis.DoesNotExist:
        return Response({"error": "Analysis not found"}, status=404)

@api_view(['GET'])
def list_analyses(request):
    analyses = PatientAnalysis.objects.all().order_by('-created_at')[:10]
    serializer = PatientAnalysisSerializer(analyses, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def analyses_summary(request):
    analyses = PatientAnalysis.objects.all()

    analyses_run = analyses.count()
    genes_profiled = analyses.exclude(total_genes_analyzed__isnull=True).values_list('total_genes_analyzed', flat=True)
    total_genes_profiled = sum(value for value in genes_profiled if value)
    # Count from normalized relational rows to avoid JSON key mismatches (drugCandidates vs drug_candidates).
    drug_candidates = DrugCandidate.objects.count()

    completed = analyses.filter(status='COMPLETE').exclude(completed_at__isnull=True)
    durations = [
        (analysis.completed_at - analysis.created_at)
        for analysis in completed.only('created_at', 'completed_at')
        if analysis.completed_at and analysis.created_at
    ]
    avg_duration = sum(durations, timedelta()) / len(durations) if durations else None
    avg_pipeline_minutes = round(avg_duration.total_seconds() / 60, 1) if avg_duration else None

    return Response(
        {
            "analyses_run": analyses_run,
            "genes_profiled": total_genes_profiled,
            "drug_candidates": drug_candidates,
            "avg_pipeline_minutes": avg_pipeline_minutes,
        }
    )

@api_view(['DELETE'])
def clear_analyses(request):
    # Deletes all analyses; related rows are removed via FK cascade.
    deleted, _ = PatientAnalysis.objects.all().delete()
    return Response({"deleted": deleted})

@api_view(['GET'])
def analysis_results(request, analysis_id):
    try:
        analysis = PatientAnalysis.objects.get(id=analysis_id)
        serializer = PatientAnalysisSerializer(analysis)
        return Response(serializer.data)
    except PatientAnalysis.DoesNotExist:
        return Response({"error": "Analysis not found"}, status=404)

