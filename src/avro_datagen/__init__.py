"""Schema-driven data generator for Avro schemas with arg.properties hints."""

from avro_datagen.generator import generate
from avro_datagen.resolver import RecordResolver, load_schema
from avro_datagen.validator import SchemaValidationError, validate

__all__ = [
    "RecordResolver",
    "SchemaValidationError",
    "generate",
    "load_schema",
    "validate",
]
