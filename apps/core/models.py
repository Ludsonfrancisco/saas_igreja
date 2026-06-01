from django.db import models


class BaseModel(models.Model):
    """Base abstrata. Auditoria temporal nao e opcional (P-ARQ-02)."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ('-created_at',)
