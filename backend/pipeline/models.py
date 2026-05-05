from django.db import models
import uuid 

class PatientAnalysis(models.Model):
    STATUS_CHOICES=[
        ('PENDING','Pending'),
        ('RUNNING','Running'),
        ('COMPLETE','Complete'),
        ('FAILED','Failed'),
    ]
    
    id=models.UUIDField(primary_key=True, default=uuid.uuid4,editable=False)
    patient_id=models.CharField(max_length=100)
    status=models.CharField(max_length=20, choices=STATUS_CHOICES,default='PENDING')
    predicted_subtype=models.CharField(max_length=20,null=True,blank=True)
    luad_confidence=models.FloatField(null=True,blank=True)
    lusc_confidence=models.FloatField(null=True,blank=True)
    total_genes_analyzed=models.IntegerField(default=0)
    current_step=models.CharField(max_length=255, blank=True)
    current_step_number=models.IntegerField(default=0)
    created_at=models.DateTimeField(auto_now_add=True)
    completed_at=models.DateTimeField(null=True,blank=True)
    error_message=models.TextField(blank=True)
    results=models.JSONField(default=dict, null=True, blank=True)
    
class XAIResult(models.Model):
    analysis=models.ForeignKey(PatientAnalysis, on_delete=models.CASCADE)
    gene_index=models.IntegerField()
    gene_symbol=models.CharField(max_length=50)
    shap_value=models.FloatField()
    lime_weight=models.FloatField()
    shap_direction=models.CharField(max_length=10)
    lime_direction=models.CharField(max_length=10)
    high_confidence=models.BooleanField(default=False)

class DrugCandidate(models.Model):
    analysis=models.ForeignKey(PatientAnalysis,on_delete=models.CASCADE)
    gene_symbol=models.CharField(max_length=50)
    drug_name=models.CharField(max_length=100)
    chembl_id=models.CharField(max_length=50, blank=True)
    mechanism=models.TextField(blank=True)
    action_type=models.CharField(max_length=100, blank=True)
    max_phase=models.IntegerField(default=0)
    created_at=models.DateTimeField(auto_now_add=True)

class AgentReport(models.Model):
    analysis = models.ForeignKey(PatientAnalysis, on_delete=models.CASCADE)
    gene_symbol = models.CharField(max_length=50)
    agent_name = models.CharField(max_length=50)  # 'Gene Agent', 'Aggregator' etc.
    report_text = models.TextField()
    sections = models.JSONField(default=list)

class PatientSummaryReport(models.Model):
    analysis = models.ForeignKey(PatientAnalysis, on_delete=models.CASCADE)
    summary_text = models.TextField()
    top_genes = models.JSONField()
    top_drugs = models.JSONField()
    clinical_recommendations = models.TextField()

