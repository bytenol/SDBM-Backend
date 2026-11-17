from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ExaminationViewSet,
    AssessmentComponentViewSet,
    GradingScaleViewSet,
    StudentScoreViewSet,
    StudentResultViewSet,
    StudentTermSummaryViewSet,
    ResultWorkflowAuditViewSet,
)

router = DefaultRouter()
router.register(r'exams', ExaminationViewSet, basename='examination')
router.register(r'components', AssessmentComponentViewSet, basename='assessment-component')
router.register(r'grading-scales', GradingScaleViewSet, basename='grading-scale')
router.register(r'scores', StudentScoreViewSet, basename='student-score')
router.register(r'subject-results', StudentResultViewSet, basename='student-result')
router.register(r'term-summaries', StudentTermSummaryViewSet, basename='term-summary')
router.register(r'audits', ResultWorkflowAuditViewSet, basename='result-audit')

app_name = 'examinations'

urlpatterns = [
    path('', include(router.urls)),
]