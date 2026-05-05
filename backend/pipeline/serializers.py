from rest_framework import serializers
from .models import *

class AgentReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentReport
        fields = '__all__'

class PatientSummaryReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientSummaryReport
        fields = '__all__'

class XAIResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = XAIResult
        fields = '__all__'

class DrugCandidateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DrugCandidate
        fields = '__all__'

class PatientAnalysisSerializer(serializers.ModelSerializer):
    xai_results = XAIResultSerializer(source='xaresult_set', many=True, read_only=True)
    drug_candidates = DrugCandidateSerializer(source='drugcandidate_set', many=True, read_only=True)
    agent_reports = AgentReportSerializer(source='agentreport_set', many=True, read_only=True)
    summary_report = PatientSummaryReportSerializer(read_only=True)

    class Meta:
        model = PatientAnalysis
        fields = [
            'id', 'patient_id', 'status', 'predicted_subtype', 'luad_confidence', 
            'lusc_confidence', 'total_genes_analyzed', 'current_step', 
            'current_step_number', 'created_at', 'completed_at', 'error_message', 
            'results', 'xai_results', 'drug_candidates', 'agent_reports', 'summary_report'
        ]
        