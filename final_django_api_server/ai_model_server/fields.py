from django.db import models
from pgvector.django import VectorField as PgVectorField


class VectorField(PgVectorField):
    """pgvector를 사용하는 벡터 필드"""

    def __init__(self, *args, dimensions=None, **kwargs):
        self.dimensions = dimensions
        super().__init__(*args, dimensions=dimensions, **kwargs)
