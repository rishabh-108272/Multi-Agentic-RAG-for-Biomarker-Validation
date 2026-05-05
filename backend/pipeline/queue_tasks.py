from celery import shared_task


@shared_task
def run_full_pipeline_queued(analysis_id, csv_data, classifier_type="lung"):
    # Lazy import so web processes can enqueue without importing heavy ML modules.
    from .tasks import run_full_pipeline

    return run_full_pipeline(analysis_id, csv_data, classifier_type)

